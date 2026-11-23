"""공개 법령 텍스트 전용 번역. 질문·개인 서류는 이 모듈에 보내지 않는다.

Azure Translator 표준 NMT를 사용한다 (리소스는 F0로 생성). 키 미설정·API 장애·한도 초과 시
LLM으로 대체하지 않는다. 성공만 원문 해시·언어·구현 버전별로 메모리에 캐시한다.
"""

import asyncio
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import get_settings
from app.core.lang import Lang

log = logging.getLogger(__name__)
TranslationStatus = Literal["translated", "original", "unavailable", "not_verified", "development"]
PROVIDER = "azure_translator"
SUMMARY_KIND = "azure_translated_summary"  # 기존 LLM·다른 제공자의 베트남어 요약과 구분
ENDPOINT = "https://api.cognitive.microsofttranslator.com/translate"
_CACHE_VERSION = "azure-nmt-v1"
_CACHE_LIMIT = 1024
_cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()


@dataclass(frozen=True)
class Translation:
    text: str = ""
    status: TranslationStatus = "unavailable"
    provider: str | None = None

    def citation_fields(self) -> dict:
        return {"quote_translation": self.text, "translation_status": self.status,
                "translation_provider": self.provider}


def require_translation() -> None:
    """유료 요약 작업을 시작하기 전에 번역 설정을 확인한다 (비밀 값 출력 금지)."""
    if not get_settings().azure_translator_key:
        raise RuntimeError("AZURE_TRANSLATOR_KEY를 설정해야 법령 번역을 생성할 수 있습니다.")


def _parts(text: str) -> list[str]:
    """긴 인용도 자르지 않고 모두 번역한다. 가능하면 문단·어절 경계로 나눈다."""
    parts = []
    while len(text) > 4500:
        cut = max(text.rfind("\n", 2250, 4500), text.rfind(" ", 2250, 4500))
        cut = cut + 1 if cut >= 0 else 4500
        parts.append(text[:cut])
        text = text[cut:]
    return [*parts, text]


async def translate_texts(texts: list[str], target: Lang) -> list[Translation]:
    """한국어 법령 인용·요약 → 대상 언어. 중복은 한 번 요청하고 순서를 보존한다."""
    if target == "ko":
        return [Translation(text, "original") for text in texts]
    if not texts:
        return []
    settings = get_settings()
    if settings.llm_fake:
        return [Translation(f"[DEV FAKE TRANSLATION] {text}", "development") for text in texts]
    if not settings.azure_translator_key:
        return [Translation() for _ in texts]

    headers = {"Ocp-Apim-Subscription-Key": settings.azure_translator_key}
    if settings.azure_translator_region:
        headers["Ocp-Apim-Subscription-Region"] = settings.azure_translator_region
    results: dict[str, Translation] = {}
    sem = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=settings.translation_timeout_seconds) as client:
        async def one(source: str) -> None:
            if not source.strip():
                results[source] = Translation()
                return
            key = (hashlib.sha256(source.encode()).hexdigest(), target, _CACHE_VERSION)
            if key in _cache:
                _cache.move_to_end(key)
                results[source] = Translation(_cache[key], "translated", PROVIDER)
                return
            try:
                async with sem:
                    parts = _parts(source)
                    response = await client.post(
                        ENDPOINT,
                        headers=headers,
                        params={"api-version": "3.0", "from": "ko", "to": target, "textType": "plain",
                                "category": "general"},
                        json=[{"Text": part} for part in parts],
                    )
                    response.raise_for_status()
                    rows = response.json()
                    if not isinstance(rows, list) or len(rows) != len(parts):
                        raise ValueError("Invalid NMT response")
                    texts = []
                    for row in rows:
                        targets = row["translations"]
                        if len(targets) != 1 or targets[0].get("to") != target:
                            raise ValueError("Invalid translation language")
                        value = targets[0]["text"]
                        if not isinstance(value, str) or not value.strip():
                            raise ValueError("Empty translation")
                        texts.append(value)
                    translated = "\n".join(texts)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError):
                # HTTP 오류 본문·예외에는 키나 원문이 포함될 수 있으므로 출력하지 않는다.
                log.warning("법령 번역 실패 (provider=azure_translator)")
                results[source] = Translation()
                return
            _cache[key] = translated
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_LIMIT:
                _cache.popitem(last=False)
            results[source] = Translation(translated, "translated", PROVIDER)

        await asyncio.gather(*(one(source) for source in dict.fromkeys(texts)))
    return [results[source] for source in texts]
