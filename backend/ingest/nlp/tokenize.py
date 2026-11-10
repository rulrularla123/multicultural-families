"""BM25용 토큰화. 한국어 법령 원문과 베트남어·한국어 요약·질문을 같은 함수로 토큰화한다.

- 한글: 조사·어미가 붙어 어절 단위로는 잘 맞지 않으므로 글자 2-gram을 쓴다.
  "체류기간을" → 체류, 류기, 기간, 간을. 한 글자 어절은 그대로 둔다.
- 그 밖의 글자(베트남어·영문·숫자): 소문자 어절. 베트남어는 음절이 띄어 쓰여 있어 어절이 곧 음절이다.
색인과 질의에 반드시 같은 함수를 써야 한다.
"""

import re
import unicodedata

_HANGUL_RUN = re.compile(r"[가-힣]+")
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

VI_STOPWORDS = {
    "của", "và", "các", "những", "được", "là", "có", "trong", "theo", "cho", "với",
    "này", "đó", "thì", "mà", "để", "khi", "về", "từ", "tại", "do", "bị", "một",
    "như", "sau", "đây", "hoặc", "nếu", "đã", "sẽ", "đến", "trên", "dưới", "ra", "tôi", "em", "anh", "chị",
}


def tokenize_ko(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower()
    out: list[str] = []
    for word in _WORD.findall(text):
        runs = _HANGUL_RUN.findall(word)
        if not runs:
            if word not in VI_STOPWORDS:
                out.append(word)
            continue
        rest = _HANGUL_RUN.sub(" ", word).split()
        out.extend(rest)  # "10일" → "10", "일"은 한글 쪽에서 처리
        for run in runs:
            if len(run) == 1:
                out.append(run)
            else:
                out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out


def to_index_text(text: str) -> str:
    return " ".join(tokenize_ko(text))


def to_tsquery_or(text: str, limit: int = 40) -> str:
    """OR로 묶은 tsquery 문자열. 토큰은 글자·숫자만 남으므로 to_tsquery에 안전하다."""
    seen: list[str] = []
    for tkn in tokenize_ko(text):
        if tkn not in seen:
            seen.append(tkn)
        if len(seen) >= limit:
            break
    return " | ".join(seen)
