"""US-04 서류 분석 결과 · US-05 체크리스트 테스트.

기대값은 docs/requirements/backlog.md의 US-04·US-05 인수 조건, docs/API.md 3절, CLAUDE.md 도메인 핵심에서만 가져온다.
test_documents_api.py·test_acceptance_regression.py가 이미 다루는 경로(분석 실패 후 같은 답변으로 재시도,
분석중 취소 뒤 결과 버림, 체크리스트 422·질문 대기 409·새로고침 유지)는 반복하지 않는다.
LLM은 conftest의 LLM_FAKE를 쓰고, 오류·지연·특정 응답은 테스트 안에서 분석 함수를 바꿔 재현한다.
"""
import asyncio
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.documents.analyze import DocumentAnalysis
from app.generation.answer import Citation
from app.generation.verify import quote_in_text
from tests.document_payload import document_payload

CID = "us0405-client-0001"
OTHER = "us0405-client-0002"
H = {"X-Client-Id": CID}
DEMO_DOC = Path(__file__).resolve().parents[1] / "data" / "demo" / "demo-extension-supplement-notice.docx"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
STAGES = {"extracted", "searching", "analyzing", "verifying"}
FAKE_PROVISION = "출입국관리법:J9999"  # 적재되지 않은 조문


@pytest.fixture
def client():
    from app.core.db import engine
    from app.main import app

    with TestClient(app) as c:
        yield c
        c.portal.call(engine.dispose)


@pytest.fixture
def svc():
    from app.services import documents

    return documents


def _sample(c, headers=H, lang="ko"):
    """시연용 가상 서류를 일반 업로드로 올려 질문 대기 건을 만든다."""
    r = c.post("/api/v1/documents", headers=headers, json=document_payload(DEMO_DOC.name, DOCX_MIME, DEMO_DOC.read_bytes(), lang))
    assert r.status_code == 201, r.text
    return r.json()


def _answers(analysis):
    return [{"question_id": q["id"], "option_id": q["options"][0]["id"]} if q["options"]
            else {"question_id": q["id"], "text": "예"} for q in analysis["intake"]["questions"]]


def _get(c, aid, headers=H):
    return c.get(f"/api/v1/documents/{aid}", headers=headers).json()


def _wait(c, aid, cond, timeout=30):
    body = None
    for _ in range(timeout * 10):
        body = _get(c, aid)
        if cond(body):
            return body
        time.sleep(0.1)
    raise AssertionError(f"조건을 만족하지 않음: status={body and body['status']}, stage={body and body['stage']}")


def _start(c, headers=H):
    a = _sample(c, headers)
    r = c.post(f"/api/v1/documents/{a['id']}/answers", headers=headers, json={"answers": _answers(a)})
    assert r.status_code == 202, r.text
    return a


def _reviewed(c):
    a = _start(c)
    body = _wait(c, a["id"], lambda b: b["status"] in ("review", "failed"))
    assert body["status"] == "review", body["error"]
    return body


def _job_id(c, aid):
    from app.core.db import SessionLocal

    async def read():
        async with SessionLocal() as s:
            return (await s.execute(text("SELECT job_id FROM analyses WHERE id = :id"), {"id": uuid.UUID(aid)})).scalar()

    return c.portal.call(read)


def _slow(real, seconds=2.0):
    async def slow(*args, **kwargs):
        await asyncio.sleep(seconds)
        return await real(*args, **kwargs)

    return slow


async def _broken(*args, **kwargs):
    raise RuntimeError("LLM 오류 재현")


def _patched(real, **update):
    """실제(가짜 LLM) 분석 결과를 받아 일부 필드만 바꿔 돌려준다."""
    async def run(*args, **kwargs):
        a: DocumentAnalysis = await real(*args, **kwargs)
        return a.model_copy(update={k: (v(a) if callable(v) else v) for k, v in update.items()})

    return run


# --- US-04 분석 진행과 결과 ----------------------------------------------------------------

@pytest.mark.db
def test_us04_analysis_shows_progress_stage_then_review(client, svc, monkeypatch):
    """US-04 (정상): 분석을 시작하면 분석중이 되고 진행 단계가 보인다. 끝나면 결과 확인이 된다."""
    monkeypatch.setattr(svc, "run_analysis", _slow(svc.run_analysis))
    a = _start(client)
    seen = set()
    body = _get(client, a["id"])
    for _ in range(300):
        body = _get(client, a["id"])
        if body["status"] != "analyzing":
            break
        seen.add(body["stage"])
        time.sleep(0.1)
    assert body["status"] == "review", body["error"]
    assert seen and seen <= STAGES
    assert "analyzing" in seen  # 2초 늦춘 분석 단계를 화면이 볼 수 있다
    assert body["result"] is not None and body["error"] is None


@pytest.mark.db
def test_us04_result_has_summary_classified_clauses_cautions_actions(client):
    """US-04 (정상): 결과에 쉬운 요약, 조항별 분류(꼭 확인/주의/일반)와 설명, 주의점, 다음 행동, 근거 조문이 있다."""
    result = _reviewed(client)["result"]
    assert result["summary_simple"].strip()
    assert result["clauses"]
    for clause in result["clauses"]:
        assert clause["category"] in ("must_check", "caution", "general")
        assert clause["text"].strip()
        if clause["category"] != "general":
            assert (clause["explanation_simple"] or "").strip()
    for caution in result["cautions"]:
        assert caution["kind"] in ("risk", "missing", "deadline", "ambiguity", "outdated")
        assert caution["explanation_simple"].strip()
    assert result["next_actions"]
    clause_ids = {c["id"] for c in result["clauses"]}
    for action in result["next_actions"]:
        assert action["text"].strip() and "due" in action
        assert action["clause_id"] is None or action["clause_id"] in clause_ids
    cited = [c for x in result["clauses"] + result["cautions"] for c in x["citations"]]
    assert cited, "근거 조문이 하나도 없음"
    assert all(c["provision_id"] and c["quote_ko"] for c in cited)
    assert result["disclaimer"]  # 법률 정보이며 자문·허가가 아니라는 안내


@pytest.mark.db
def test_us04_highlights_are_verbatim_phrases_of_the_clause(client, svc, monkeypatch):
    """US-04 (정상): 형광펜 문구는 그 조항 원문에 있는 문구만 남는다. 원문에 없는 문구는 표시하지 않는다."""
    def with_highlights(a: DocumentAnalysis):
        return [f.model_copy(update={"highlights": [*f.highlights, "원문에 없는 형광펜 문구"]}) for f in a.clauses]

    monkeypatch.setattr(svc, "run_analysis", _patched(svc.run_analysis, clauses=with_highlights))
    result = _reviewed(client)["result"]
    highlights = [(h, c["text"]) for c in result["clauses"] for h in c["highlights"]]
    assert all(quote_in_text(h, t) for h, t in highlights)
    assert "원문에 없는 형광펜 문구" not in {h for h, _ in highlights}


@pytest.mark.db
def test_us04_format_error_sets_failed_with_message(client, svc, monkeypatch):
    """US-04 (실패): LLM 형식 오류면 분석 실패가 되고 사용자에게 보여 줄 이유가 저장된다. 결과는 저장되지 않는다."""
    async def bad_format(*args, **kwargs):
        return DocumentAnalysis.model_validate({"summary": "형식이 틀린 응답"})  # 필수 필드 빠짐 → ValidationError

    monkeypatch.setattr(svc, "run_analysis", bad_format)
    a = _start(client)
    body = _wait(client, a["id"], lambda b: b["status"] != "analyzing")
    assert body["status"] == "failed"
    assert body["error"] and body["result"] is None and body["checklist"] is None


@pytest.mark.db
def test_us04_analysis_over_90_seconds_sets_failed(client, svc, monkeypatch):
    """US-04 (실패): 분석이 90초를 넘기면 분석 실패가 된다."""
    async def hang(*args, **kwargs):
        await asyncio.sleep(3600)

    monkeypatch.setattr(svc, "run_analysis", hang)
    a = _start(client)
    body = _wait(client, a["id"], lambda b: b["status"] != "analyzing", timeout=100)
    assert body["status"] == "failed" and body["error"]


@pytest.mark.db
def test_us04_unverifiable_citation_is_not_shown_as_verified(client, svc, monkeypatch):
    """US-04 (LLM): 적재되지 않은 조문·원문과 다른 인용은 검증된 근거로 보여 주지 않는다 (US-01과 같은 검증)."""
    bad = [Citation(provision_id=FAKE_PROVISION, quote_ko="없는 조문의 문장", quote_translation="x"),
           Citation(provision_id="출입국관리법:J25", quote_ko="원문에 전혀 없는 지어낸 문장입니다", quote_translation="x")]

    def with_bad(a: DocumentAnalysis):
        return [f.model_copy(update={"citations": [*f.citations, *bad]}) for f in a.clauses]

    monkeypatch.setattr(svc, "run_analysis", _patched(svc.run_analysis, clauses=with_bad))
    result = _reviewed(client)["result"]
    cited = [c for x in result["clauses"] + result["cautions"] for c in x["citations"]]
    for c in cited:
        if c["provision_id"] == FAKE_PROVISION or c["quote_ko"] == bad[1].quote_ko:
            assert c.get("verified") is False  # 보여 준다면 "원문 확인 필요"로만


@pytest.mark.db
@pytest.mark.parametrize("second_fails", [False, True])
def test_us04_failed_citation_regenerates_analysis_once(client, svc, monkeypatch, second_fails):
    """US-04 (LLM): 인용 검증에 실패하면 분석을 한 번 다시 생성한다 (CLAUDE.md 도메인 핵심, US-01과 같은 방식)."""
    real = svc.run_analysis
    calls = []

    async def first_bad(*args, **kwargs):
        calls.append(kwargs)
        a = await real(*args, **kwargs)
        if len(calls) > 1 and not second_fails:
            return a
        bad = Citation(provision_id=FAKE_PROVISION, quote_ko="없는 조문의 문장", quote_translation="x")
        return a.model_copy(update={"clauses": [f.model_copy(update={"citations": [bad]}) for f in a.clauses]})

    monkeypatch.setattr(svc, "run_analysis", first_bad)
    result = _reviewed(client)["result"]
    assert len(calls) == 2
    assert not calls[0].get("feedback")
    assert FAKE_PROVISION in calls[1]["feedback"]
    assert FAKE_PROVISION not in str(result)
    assert ("원문 확인 필요" in (result["notice"] or "")) is second_fails
    if second_fails:
        assert result["confidence"] == "low" and result["needs_expert"]


@pytest.mark.db
def test_us04_low_confidence_adds_expert_flag_and_at_most_3_open_questions(client, svc, monkeypatch):
    """US-04 (LLM): 판단이 어려우면 확신도와 전문가 상담 필요 표시를 붙이고, 추가 질문은 0~3개만 보여 준다."""
    from app.documents.analyze import OpenQuestion

    many = [OpenQuestion(question=f"추가 질문 {i}", why="판단에 필요") for i in range(5)]
    monkeypatch.setattr(svc, "run_analysis", _patched(svc.run_analysis, confidence="low", needs_expert=False,
                                                      open_questions=many))
    result = _reviewed(client)["result"]
    assert result["confidence"] == "low"
    assert result["needs_expert"] is True
    assert result["notice"]
    assert len(result["open_questions"]) == 3
    assert all(q["question"] and q["why"] for q in result["open_questions"])


@pytest.mark.db
def test_us04_confidence_is_one_of_three_levels(client):
    """US-04 (LLM): 결과의 확신도는 높음·보통·낮음 중 하나이고 전문가 상담 필요 여부가 있다."""
    result = _reviewed(client)["result"]
    assert result["confidence"] in ("high", "medium", "low")
    assert isinstance(result["needs_expert"], bool)
    assert 0 <= len(result["open_questions"]) <= 3


# --- 늦게 온 결과 버리기 (job_id) -----------------------------------------------------------

@pytest.mark.db
def test_us04_late_result_of_previous_job_is_discarded_after_retry(client, svc, monkeypatch):
    """US-04·CLAUDE.md: 재시도하면 job_id가 바뀌고, 이전 작업의 결과가 늦게 와도 저장하지 않는다. 지금 작업 결과만 저장한다."""
    real_run, real_analyze = svc.run_analysis, svc._analyze
    monkeypatch.setattr(svc, "run_analysis", _broken)
    a = _start(client)
    aid = a["id"]
    assert _wait(client, aid, lambda b: b["status"] != "analyzing")["status"] == "failed"
    old_job = _job_id(client, aid)

    monkeypatch.setattr(svc, "run_analysis", _slow(real_run, 3.0))
    r = client.post(f"/api/v1/documents/{aid}/answers", headers=H, json={"answers": []})
    assert r.status_code == 202 and r.json()["status"] == "analyzing"
    new_job = _job_id(client, aid)
    assert old_job and new_job and new_job != old_job
    _wait(client, aid, lambda b: b["stage"] == "analyzing")  # 지금 작업은 분석 단계에서 기다리는 중

    async def stale(*args, **kwargs):
        return {"summary": "이전 작업의 늦은 결과", "next_actions": [{"id": "a1", "text": "x"}]}

    monkeypatch.setattr(svc, "_analyze", stale)
    client.portal.call(svc._run, aid, old_job)
    body = _get(client, aid)
    assert body["status"] == "analyzing" and body["result"] is None and body["checklist"] is None

    monkeypatch.setattr(svc, "_analyze", real_analyze)
    body = _wait(client, aid, lambda b: b["status"] != "analyzing")
    assert body["status"] == "review"
    assert body["result"]["summary"] != "이전 작업의 늦은 결과"


@pytest.mark.db
def test_us04_late_result_does_not_overwrite_reviewed_analysis(client, svc, monkeypatch):
    """US-04·CLAUDE.md: 분석중이 아닌 건(결과 확인)에는 어떤 작업의 결과도 덮어쓰지 않는다."""
    body = _reviewed(client)
    aid = body["id"]
    job = _job_id(client, aid)

    async def stale(*args, **kwargs):
        return {"summary": "늦게 온 결과", "next_actions": []}

    monkeypatch.setattr(svc, "_analyze", stale)
    client.portal.call(svc._run, aid, job)
    after = _get(client, aid)
    assert after["status"] == "review"
    assert after["result"] == body["result"] and after["checklist"] == body["checklist"]


# --- US-05 체크리스트 ----------------------------------------------------------------------

@pytest.mark.db
def test_us05_each_next_action_has_a_checklist_item(client):
    """US-05 (정상): 다음 행동마다 체크 항목(처음엔 체크 안 됨)과 기한 칸이 있다."""
    body = _reviewed(client)
    actions, checklist = body["result"]["next_actions"], body["checklist"]
    assert [c["index"] for c in checklist] == list(range(len(actions)))
    assert all(c["done"] is False for c in checklist)
    assert all("due" in a for a in actions)


@pytest.mark.db
def test_us05_all_checked_is_done_and_unchecking_returns_to_review(client):
    """US-05 (정상): 모두 체크하면 완료, 하나라도 풀면 결과 확인으로 돌아간다. 다시 모두 체크하면 완료."""
    body = _reviewed(client)
    aid, n = body["id"], len(body["checklist"])
    url = f"/api/v1/documents/{aid}/checklist"
    for i in range(n):
        r = client.post(url, headers=H, json={"index": i, "done": True})
        assert r.status_code == 200
        assert r.json()["status"] == ("done" if i == n - 1 else "review")

    r = client.post(url, headers=H, json={"index": n - 1, "done": False})
    assert r.status_code == 200 and r.json()["status"] == "review"
    assert [c["done"] for c in r.json()["checklist"]] == [True] * (n - 1) + [False]

    r = client.post(url, headers=H, json={"index": n - 1, "done": True})
    assert r.json()["status"] == "done"
    assert _get(client, aid)["status"] == "done"


@pytest.mark.db
@pytest.mark.parametrize("state", ["analyzing", "failed", "canceled"])
def test_us05_checklist_is_409_unless_review_or_done(client, svc, monkeypatch, state):
    """US-05 (실패): 결과 확인·완료가 아닌 건(분석중·분석 실패·취소됨)의 체크리스트는 바꿀 수 없다(409)."""
    if state == "analyzing":
        monkeypatch.setattr(svc, "run_analysis", _slow(svc.run_analysis, 5.0))
        aid = _start(client)["id"]
    elif state == "failed":
        monkeypatch.setattr(svc, "run_analysis", _broken)
        aid = _start(client)["id"]
        _wait(client, aid, lambda b: b["status"] == "failed")
    else:
        aid = _reviewed(client)["id"]
        assert client.post(f"/api/v1/documents/{aid}/cancel", headers=H).status_code == 200
    before = _get(client, aid)
    assert before["status"] == state

    r = client.post(f"/api/v1/documents/{aid}/checklist", headers=H, json={"index": 0, "done": True})
    assert r.status_code == 409 and r.json()["detail"]
    after = _get(client, aid)
    assert after["status"] == state and after["checklist"] == before["checklist"]


@pytest.mark.db
def test_us05_other_client_cannot_change_checklist(client):
    """US-05·공통 (실패): 다른 익명 ID는 체크리스트를 바꿀 수 없다(404). 저장된 체크는 그대로다."""
    body = _reviewed(client)
    r = client.post(f"/api/v1/documents/{body['id']}/checklist", headers={"X-Client-Id": OTHER},
                    json={"index": 0, "done": True})
    assert r.status_code == 404
    assert _get(client, body["id"])["checklist"] == body["checklist"]
