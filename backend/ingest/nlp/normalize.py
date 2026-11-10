"""법령·서류 텍스트 정규화.

- 유니코드 NFC 통일 (자모가 분리된 한글, 조합형 베트남어 성조가 섞이면 검색·대조가 깨진다)
- 원문 저장용(normalize_text)은 공백·줄바꿈만 정리하고 내용은 바꾸지 않는다
- 비교용(fold)은 문장부호·가운뎃점 표기 차이(ㆍ·・)와 공백을 없앤다
"""

import re
import unicodedata

_SPACES = re.compile("[ \\t\\u00a0\\u2000-\\u200b\\u3000]+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
# 법령 원문은 가운뎃점을 ㆍ(U+318D)로, 모델은 ·(U+00B7)로 쓰는 경우가 많다
_MIDDOTS = str.maketrans({"ㆍ": " ", "·": " ", "・": " ", "‧": " "})
# legalize-kr 마크다운의 이스케이프(1\. 가\.)와 굵게 표시(**①**)
_MD_ESCAPE = re.compile(r"\\([.\-*_#()\[\]])")


def normalize_text(text: str) -> str:
    """원문 저장용 정규화. 내용은 바꾸지 않고 공백·유니코드 형태만 정리한다."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    # 줄 앞 들여쓰기는 남긴다 (법령 마크다운에서 호·목을 구분하는 표시다)
    lines = []
    for line in text.split("\n"):
        body = line.lstrip(" \t")
        indent = line[: len(line) - len(body)].replace("\t", "  ")
        lines.append(indent + _SPACES.sub(" ", body).rstrip())
    out: list[str] = []
    for line in lines:
        if line.strip() or (out and out[-1].strip()):
            out.append(line)
    return "\n".join(out).strip("\n")


def unescape_markdown(text: str) -> str:
    return _MD_ESCAPE.sub(r"\1", text).replace("**", "")


def fold(text: str) -> str:
    """비교용 정규화: 소문자, 가운뎃점·문장부호 제거, 공백 축약."""
    text = unicodedata.normalize("NFC", unescape_markdown(text)).lower().translate(_MIDDOTS)
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text.replace("\n", " ")).strip()
