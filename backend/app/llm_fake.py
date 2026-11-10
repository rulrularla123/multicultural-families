"""개발용 가짜 LLM (LLM_FAKE=true). API 키 없이 화면 흐름을 확인하기 위한 것이다.

- 모든 답변 문구에 '[DEV FAKE RESPONSE]'를 붙인다. 시연·운영에서는 켜지 않는다.
- 인용은 실제로 검색된 조문 원문에서 잘라 쓰므로 인용 검증 로직은 그대로 동작한다.
"""

import asyncio
import hashlib
import math
import re

from app.core.glossary import TERMS

TAG = "[DEV FAKE RESPONSE]"
_PROVISION = re.compile(r'<provision id="([^"]+)"[^>]*>\n([^\n]*)\n(.*?)(?:\n<summary_vi>.*?</summary_vi>)?\n</provision>', re.S)
_SEGMENT = re.compile(r"\[(C\d+)\] (.*?)(?=\n\n\[C\d+\] |\n</document>|\Z)", re.S)


def _user_text(messages: list[dict]) -> str:
    return "\n".join(m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str))


def _is_ko(instructions: str) -> bool:
    """프롬프트에 들어간 응답 언어 이름(LANG_NAME)으로 판단한다."""
    from app.core.lang import LANG_NAME

    return LANG_NAME["ko"] in instructions and LANG_NAME["vi"] not in instructions


def _first_sentence(text: str) -> str:
    """조문 본문에서 인용할 한 줄 (제목 줄 다음, 번호 표시 제외)"""
    for line in text.split("\n")[1:]:
        line = re.sub(r"^([①-⑳]|\d+\.|[가-힣]\.)\s*", "", line.strip())
        line = re.sub(r"\s*<[^>]*>\s*$", "", line)
        if len(line) > 15:
            return line[:60].rsplit(" ", 1)[0]
    return text.split("\n")[0][:40]


def _provisions(content: str) -> list[tuple[str, str, str]]:
    return [(m.group(1), m.group(2), m.group(3)) for m in _PROVISION.finditer(content)]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """토큰 해시 벡터. 의미 검색은 안 되지만 벡터 검색 경로가 실행되는지는 확인할 수 있다."""
    out = []
    for t in texts:
        v = [0.0] * 1536
        for tok in re.findall(r"\w+", t.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 1536] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


async def complete(instructions: str, prompt: str) -> str:
    return f"{TAG} {prompt[:120]}"


_SMALLTALK = re.compile(r"^\s*(ㅎㅇ|안녕\S*|하이|hi|hello|xin chào|chào\S*|cảm ơn|감사\S*|고마워\S*|ㄳ|ㅋ+|ㅎ+)\s*[!.?~]*\s*$", re.I)


def _rewrite(output_type, messages: list[dict]):
    q = messages[-1]["content"]
    if _SMALLTALK.match(q):
        return output_type(intent="smalltalk", queries_ko=[], domains=[], as_of=None, standalone_question=q)
    low = q.lower()
    ko = [k.split(" / ")[0] for vi, k in TERMS
          if any(w in low for w in re.split(r"[ /()]", vi.lower()) if len(w) >= 4)]
    if re.search(r"[가-힣]", q):
        ko.insert(0, q)
    queries = [" ".join(dict.fromkeys(ko[:3]))] if ko else [q]
    return output_type(intent="legal", queries_ko=queries, domains=[], as_of=None, standalone_question=q)


def _answer(output_type, instructions: str, messages: list[dict]):
    from app.generation.answer import AnswerCitation

    provs = _provisions(_user_text(messages))[:2]
    cits = [AnswerCitation(provision_id=pid, quote_ko=_first_sentence(txt),
                           quote_translation=f"{TAG} {_first_sentence(txt)}", marker=i + 1)
            for i, (pid, _path, txt) in enumerate(provs)]
    if _is_ko(instructions):
        body = f"{TAG} 검색된 조문으로 만든 예시 답변입니다. 실제 답변은 OpenAI API 키를 넣고 LLM_FAKE=false로 실행하세요."
        follow = "지금 체류자격은 무엇인가요?"
    else:
        body = (f"{TAG} Câu trả lời mẫu được tạo từ các điều luật đã tìm thấy. "
                "Hãy đặt OpenAI API key và LLM_FAKE=false để nhận câu trả lời thật.")
        follow = "Tư cách lưu trú hiện tại của bạn là gì?"
    body += "".join(f"\n\n- {path} [{i + 1}]" for i, (_pid, path, _t) in enumerate(provs))
    return output_type(answer=body, citations=cits, confidence="medium", needs_expert=False,
                       follow_up_questions=[follow])


def _intake(output_type, instructions: str, messages: list[dict]):
    from app.documents.facts import parse_date
    from app.documents.intake import FactItem, InfoItem, Option, Question

    ko = _is_ko(instructions)
    content = _user_text(messages)

    def opts(*xs: str) -> list[Option]:
        return [Option(id=chr(97 + i), label=x) for i, x in enumerate(xs)]

    if ko:
        qs = [
            Question(id="q1", text="지금 체류자격은 무엇인가요?", why="체류자격에 따라 연장 요건과 서류가 달라집니다.",
                     options=opts("F-6-1 (한국인 배우자)", "F-6-2 (자녀 양육)", "F-6-3 (혼인 단절)", "잘 모름"), allow_free_text=True),
            Question(id="q2", text="지금 배우자와 함께 살고 있나요?", why="동거 여부는 결혼이민 체류 심사에서 확인하는 사항입니다.",
                     options=opts("예", "아니요", "잠시 떨어져 지냄"), allow_free_text=False),
            Question(id="q3", text="연장 신청을 이미 했나요?", why="신청 전후에 따라 해야 할 일이 다릅니다.",
                     options=opts("아직 안 함", "이미 신청함", "잘 모름"), allow_free_text=False),
        ]
        label, title, summary = "체류기간 연장 안내", "체류기간 연장 안내문", f"{TAG} 체류기간 연장 안내문이라고 가정한 예시 요약입니다."
        expiry = "체류기간 만료일"
    else:
        qs = [
            Question(id="q1", text="Tư cách lưu trú hiện tại của bạn là gì?",
                     why="Điều kiện và hồ sơ gia hạn khác nhau theo tư cách lưu trú.",
                     options=opts("F-6-1 (vợ/chồng người Hàn)", "F-6-2 (nuôi con)", "F-6-3 (hôn nhân chấm dứt)", "Không chắc"),
                     allow_free_text=True),
            Question(id="q2", text="Bạn có đang sống cùng vợ/chồng không?",
                     why="Việc chung sống được xem xét khi gia hạn lưu trú kết hôn.",
                     options=opts("Có", "Không", "Tạm thời sống riêng"), allow_free_text=False),
            Question(id="q3", text="Bạn đã nộp đơn gia hạn chưa?", why="Việc cần làm khác nhau trước và sau khi nộp đơn.",
                     options=opts("Chưa", "Đã nộp", "Không chắc"), allow_free_text=False),
        ]
        label, title = "Thông báo gia hạn lưu trú", "Thông báo gia hạn thời gian lưu trú"
        summary = f"{TAG} Tóm tắt mẫu, giả định đây là thông báo gia hạn lưu trú."
        expiry = "Ngày hết hạn lưu trú"
    facts = [FactItem(key="doc_type", label=label, value="체류기간 연장 안내")]
    if d := parse_date(content):
        facts.append(FactItem(key="expiry_date", label=expiry, value=d.isoformat()))
    return output_type(
        doc_kind="extension_notice", doc_type_label=label, title=title, summary=summary,
        basic_info=[InfoItem(key="doc_type", label=label, value="체류기간 연장 안내")],
        facts=facts, questions=qs,
        search_queries_ko=["체류기간 연장허가 신청", "결혼이민 체류자격 연장 서류", "체류기간 연장허가 신청 기한"],
    )


async def _analysis(output_type, instructions: str, messages: list[dict]):
    await asyncio.sleep(3)  # 진행 화면을 확인할 수 있도록 실제 분석처럼 시간을 둔다
    from app.documents.analyze import ActionItem, CautionItem, ClauseFinding, OpenQuestion
    from app.generation.answer import Citation

    ko = _is_ko(instructions)
    content = _user_text(messages)
    segs = [(m.group(1), m.group(2)) for m in _SEGMENT.finditer(content)]
    provs = _provisions(content)
    cit = [Citation(provision_id=provs[0][0], quote_ko=_first_sentence(provs[0][2]),
                    quote_translation=f"{TAG} {_first_sentence(provs[0][2])}")] if provs else []
    t = (lambda k, v: k) if ko else (lambda k, v: v)
    findings = []
    for i, (sid, text) in enumerate(segs[:8]):
        cat = "must_check" if re.search(r"기한|만료|이내|서류|과태료|출국", text) and i < 4 else (
            "caution" if i % 3 == 1 else "general")
        words = text.split()
        findings.append(ClauseFinding(
            clause_id=sid, title=text.split("\n")[0][:40], category=cat,
            explanation_simple=f"{TAG} " + t("이 부분을 쉽게 풀어 쓴 설명입니다.", "Giải thích đơn giản cho đoạn này."),
            explanation_detail=f"{TAG} " + t("이 부분의 예시 분석입니다.", "Phân tích mẫu cho đoạn này."),
            highlights=[" ".join(words[:5])] if len(words) > 5 else [], citations=cit if cat == "must_check" else []))
    first = segs[0][0] if segs else None
    return output_type(
        summary=f"{TAG} " + t("문서 전체의 예시 요약입니다.", "Tóm tắt mẫu của toàn bộ tài liệu."),
        summary_simple=f"{TAG} " + t("쉬운 말 요약입니다.", "Tóm tắt bằng lời đơn giản."),
        situation_note=f"{TAG} " + t("고른 답변을 반영했습니다.", "Đã xét đến câu trả lời bạn chọn."),
        clauses=findings,
        cautions=[CautionItem(
            title=t("체류기간 만료 전에 신청하세요", "Hãy nộp đơn trước khi hết hạn lưu trú"),
            explanation_simple=f"{TAG} " + t("만료일이 지나면 체류기간 초과가 됩니다.", "Quá ngày hết hạn sẽ bị xem là quá hạn lưu trú."),
            explanation_detail=f"{TAG} " + t("예시 주의점입니다.", "Lưu ý mẫu."),
            kind="deadline", clause_ids=[first] if first else [], citations=cit)],
        next_actions=[
            ActionItem(text=t("체류기간 만료일을 확인하기", "Kiểm tra ngày hết hạn lưu trú"), clause_id=first,
                       due=t("체류기간 만료 전", "trước ngày hết hạn lưu trú")),
            ActionItem(text=t("혼인관계증명서 등 필요 서류 준비하기", "Chuẩn bị giấy chứng nhận quan hệ hôn nhân và hồ sơ cần thiết"),
                       clause_id=None, due=None),
            ActionItem(text=t("하이코리아에서 방문 예약 또는 전자민원 신청하기", "Đặt lịch hẹn hoặc nộp đơn điện tử trên HiKorea"),
                       clause_id=None, due=None),
        ],
        open_questions=[OpenQuestion(
            question=t("자녀가 한국에 있나요?", "Bạn có con đang sống ở Hàn Quốc không?"),
            why=f"{TAG} " + t("자녀 양육 여부에 따라 체류자격이 달라질 수 있습니다.", "Việc nuôi con có thể thay đổi tư cách lưu trú."))],
        confidence="medium", needs_expert=False,
    )


async def parse(output_type, instructions: str, messages: list[dict]):
    name = output_type.__name__
    if name == "RewrittenQuery":
        return _rewrite(output_type, messages)
    if name == "LegalAnswer":
        return _answer(output_type, instructions, messages)
    if name == "Intake":
        return _intake(output_type, instructions, messages)
    if name == "DocumentAnalysis":
        return await _analysis(output_type, instructions, messages)
    raise NotImplementedError(f"가짜 모드에서 지원하지 않는 출력 타입: {name}")
