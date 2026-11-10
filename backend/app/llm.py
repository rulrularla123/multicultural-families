"""OpenAI 호출 래퍼. 모델명은 설정에서 읽는다.

LLM_FAKE=true 이면 app.llm_fake의 개발용 가짜 응답을 쓴다 (API 키 없이 UI 흐름 확인용).
"""

import contextvars
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger(__name__)

# 모델별 단가 (USD / 1M 토큰). 추정치이므로 반드시 OpenAI 공식 가격 페이지(https://openai.com/api/pricing)와
# 대조해 갱신할 것. 캐시 입력 할인은 반영하지 않는다 (비용을 약간 높게 잡는 쪽).
# 모델명은 접두사로 찾는다 ('gpt-5-mini-2025-08-07' → 'gpt-5-mini'), 가장 긴 접두사가 우선.
PRICES_PER_1M: dict[str, dict[str, float]] = {
    "gpt-5": {"input": 1.25, "output": 10.0},
    "gpt-5-mini": {"input": 0.25, "output": 2.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
}


def _price(model: str) -> dict[str, float]:
    keys = [k for k in PRICES_PER_1M if model.startswith(k)]
    if not keys:
        log.warning("가격표에 없는 모델: %s (비용 0으로 계산)", model)
        return {"input": 0.0, "output": 0.0}
    return PRICES_PER_1M[max(keys, key=len)]


@dataclass
class Usage:
    """한 요청(채팅 답변·문서 분석) 동안의 OpenAI 사용량 누계. reasoning 토큰은 output에 포함돼 과금된다."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, model: str, input_tokens: int, output_tokens: int = 0, reasoning_tokens: int = 0) -> None:
        p = _price(model)
        cost = (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.reasoning_tokens += reasoning_tokens
        self.cost_usd += cost
        self.calls += 1
        m = self.by_model.setdefault(
            model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "cost_usd": 0.0}
        )
        m["calls"] += 1
        m["input_tokens"] += input_tokens
        m["output_tokens"] += output_tokens
        m["reasoning_tokens"] += reasoning_tokens
        m["cost_usd"] = round(m["cost_usd"] + cost, 6)

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "calls": self.calls,
        }


# 현재 활성화된 누계기들 (중첩되면 바깥 것에도 함께 더한다). asyncio 태스크는 생성 시점 컨텍스트를 복사하므로
# with 블록 안에서 만든 태스크의 호출도 같은 Usage 객체에 쌓인다.
_USAGE: contextvars.ContextVar[tuple[Usage, ...]] = contextvars.ContextVar("llm_usage", default=())


@contextmanager
def track_usage() -> Iterator[Usage]:
    """with llm.track_usage() as usage: … 블록 안의 모든 OpenAI 호출 토큰·비용을 모은다 (async 코드 안에서도 사용 가능)."""
    usage = Usage()
    token = _USAGE.set((*_USAGE.get(), usage))
    try:
        yield usage
    finally:
        try:
            _USAGE.reset(token)
        except ValueError:  # 비동기 제너레이터가 다른 컨텍스트에서 닫힌 경우
            _USAGE.set(tuple(u for u in _USAGE.get() if u is not usage))


def _record(model: str, usage_obj: Any) -> None:
    """Responses/Embeddings API 응답의 usage를 활성 누계기에 더한다."""
    trackers = _USAGE.get()
    if not trackers or usage_obj is None:
        return
    inp = getattr(usage_obj, "input_tokens", None)
    if inp is None:  # embeddings: prompt_tokens
        inp = getattr(usage_obj, "prompt_tokens", 0)
    out = getattr(usage_obj, "output_tokens", 0) or 0
    details = getattr(usage_obj, "output_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", 0) or 0
    for u in trackers:
        u.add(model, inp or 0, out, reasoning)


async def record_usage(session: AsyncSession, kind: str, ref: str | None, usage: Usage) -> None:
    """usage_log에 한 줄 기록한다 (kind: 'chat' | 'analysis'). 실패해도 본 요청은 막지 않는다."""
    if usage.calls == 0:
        return
    try:
        await session.execute(
            text(
                "INSERT INTO usage_log (kind, ref, model_breakdown, input_tokens, output_tokens, cost_usd) "
                "VALUES (:kind, :ref, CAST(:mb AS jsonb), :inp, :out, :cost)"
            ),
            {
                "kind": kind, "ref": ref, "mb": json.dumps(usage.by_model), "inp": usage.input_tokens,
                "out": usage.output_tokens, "cost": round(usage.cost_usd, 6),
            },
        )
        await session.commit()
    except Exception:
        log.exception("usage_log 기록 실패")
        await session.rollback()


@lru_cache
def client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(api_key=s.openai_api_key or None)


def _fake():
    if get_settings().llm_fake:
        from app import llm_fake

        return llm_fake
    return None


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if f := _fake():
        return await f.embed_texts(texts)
    s = get_settings()
    # 입력이 너무 길면 임베딩 API가 거부하므로 대략 8k 토큰 이내로 자른다
    inputs = [t[:24000] for t in texts]
    res = await client().embeddings.create(
        model=s.openai_embedding_model, input=inputs, dimensions=s.embedding_dim
    )
    _record(s.openai_embedding_model, res.usage)
    return [d.embedding for d in res.data]


def _reasoning(fast: bool, effort: str | None = None) -> dict:
    s = get_settings()
    model = s.openai_fast_model if fast else s.openai_chat_model
    if not model.startswith(("gpt-5", "o")):
        return {}
    return {"reasoning": {"effort": effort or (s.openai_fast_reasoning_effort if fast else s.openai_reasoning_effort)}}


async def parse(
    output_type: type[T],
    instructions: str,
    messages: list[dict],
    *,
    fast: bool = False,
    effort: str | None = None,
) -> T:
    """Responses API + Structured Outputs. 스키마에 맞는 Pydantic 객체를 돌려준다."""
    if f := _fake():
        return await f.parse(output_type, instructions, messages)
    s = get_settings()
    model = s.openai_fast_model if fast else s.openai_chat_model
    res = await client().responses.parse(
        model=model,
        instructions=instructions,
        input=messages,
        text_format=output_type,
        **_reasoning(fast, effort),
    )
    _record(model, res.usage)
    if res.output_parsed is None:
        raise RuntimeError("LLM이 구조화된 응답을 반환하지 않았습니다")
    return res.output_parsed


def partial_json_string(buf: str, key: str) -> str | None:
    """생성 중인 JSON 앞부분에서 문자열 필드 값을 지금까지 나온 만큼 꺼낸다 (스트리밍 표시용)."""
    marker = f'"{key}"'
    i = buf.find(marker)
    if i < 0:
        return None
    j = buf.find('"', buf.find(":", i + len(marker)) + 1)
    if j < 0:
        return None
    out, k = [], j + 1
    while k < len(buf):
        ch = buf[k]
        if ch == "\\":
            if k + 1 >= len(buf):
                break
            nxt = buf[k + 1]
            if nxt == "u":
                if k + 6 > len(buf):
                    break
                out.append(chr(int(buf[k + 2 : k + 6], 16)))
                k += 6
                continue
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/", "r": "", "b": "", "f": ""}.get(nxt, nxt))
            k += 2
            continue
        if ch == '"':
            break
        out.append(ch)
        k += 1
    return "".join(out)


async def parse_stream(
    output_type: type[T],
    instructions: str,
    messages: list[dict],
    on_text,
    *,
    field: str = "answer",
    effort: str | None = None,
) -> T:
    """parse()와 같지만, 생성되는 동안 field 문자열을 on_text(현재까지 텍스트)로 넘긴다."""
    if f := _fake():
        result = await f.parse(output_type, instructions, messages)
        await on_text(getattr(result, field, ""))
        return result
    s = get_settings()
    buf, last = "", ""
    async with client().responses.stream(
        model=s.openai_chat_model,
        instructions=instructions,
        input=messages,
        text_format=output_type,
        **_reasoning(False, effort),
    ) as stream:
        async for event in stream:
            if event.type == "response.output_text.delta":
                buf += event.delta
                text = partial_json_string(buf, field)
                if text and len(text) - len(last) >= 12:  # 너무 잘게 보내지 않는다
                    last = text
                    await on_text(text)
        final = await stream.get_final_response()
    _record(s.openai_chat_model, final.usage)
    if final.output_parsed is None:
        raise RuntimeError("LLM이 구조화된 응답을 반환하지 않았습니다")
    return final.output_parsed


async def complete(instructions: str, prompt: str, *, fast: bool = True) -> str:
    if f := _fake():
        return await f.complete(instructions, prompt)
    s = get_settings()
    model = s.openai_fast_model if fast else s.openai_chat_model
    res = await client().responses.create(
        model=model,
        instructions=instructions,
        input=prompt,
        **_reasoning(fast),
    )
    _record(model, res.usage)
    return res.output_text
