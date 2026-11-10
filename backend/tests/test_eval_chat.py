"""평가셋 실행기(scripts/eval_chat.py)의 사례 검사와 합계 계산. DB·서버 없이 돈다."""
import json

import pytest

from scripts.eval_chat import FIELDS, load_cases, summarize


def _write(tmp_path, cases):
    p = tmp_path / "cases.json"
    p.write_text(json.dumps({"cases": cases}, ensure_ascii=False), encoding="utf-8")
    return p


def test_example_cases_file_is_valid():
    from pathlib import Path

    cases = load_cases(Path(__file__).resolve().parents[1] / "data" / "eval" / "cases.example.json")
    assert cases and all(c["id"] and c["message"] for c in cases)


@pytest.mark.parametrize("cases", [
    [{"id": "a", "message": "x"}, {"id": "a", "message": "y"}],
    [{"id": "a", "message": ""}],
    [{"id": "a", "message": "가" * 1001}],
    [{"id": "a", "message": "x", "lang": "en"}],
], ids=["duplicate-id", "empty", "1001-chars", "bad-lang"])
def test_invalid_cases_are_rejected(tmp_path, cases):
    with pytest.raises(SystemExit):
        load_cases(_write(tmp_path, cases))


def _row(**kw):
    return {k: "" for k in FIELDS} | kw


def test_summary_counts_citation_pass_rate_and_marks_fake(tmp_path):
    rows = [
        _row(id="a", http_status=200, latency_s=1.0, citations=2, verified=2, numbers_not_found=0,
             needs_expert=False, cost_usd=0.01),
        _row(id="b", http_status=200, latency_s=3.0, citations=2, verified=1, numbers_not_found=1,
             needs_expert=True, cost_usd=0.02),
        _row(id="c", http_status=502, latency_s=0.5),
    ]
    md = summarize(rows, {"llm_fake": True, "documents": 11}, tmp_path / "cases.json")
    assert "품질 평가 아님" in md
    assert "3/4 (75.0%)" in md
    assert "성공 2, 실패 1" in md
    assert "$0.0300" in md
