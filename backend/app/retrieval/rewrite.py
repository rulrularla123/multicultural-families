"""질의 재작성: 베트남어·한국어 질문 → 한국 출입국·체류 법령 용어로 된 검색 질의."""

import logging
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app import llm
from app.core.glossary import glossary_text
from app.core.lang import Lang, today_kr

log = logging.getLogger(__name__)

Domain = Literal["stay", "registration", "family", "nationality", "departure", "support", "other"]


Intent = Literal["legal", "smalltalk", "unclear"]


class RewrittenQuery(BaseModel):
    intent: Intent = Field(
        description="legal = a question about Korean residence/immigration/nationality law or procedure; "
                    "smalltalk = greeting, thanks, chit-chat, or text with no question (e.g. 'hi', 'ㅎㅇ', 'cảm ơn'); "
                    "unclear = too vague to search (e.g. '알려줘', 'help') with no usable earlier context")
    queries_ko: list[str] = Field(description="1-3 search queries in Korean legal terminology")
    domains: list[Domain]
    as_of: str | None = Field(description="ISO date (YYYY-MM-DD) if the user asks about a specific date, else null")
    standalone_question: str = Field(description="The user's question rewritten to be self-contained, same language")


INSTRUCTIONS = f"""You turn a question from a Vietnamese marriage migrant (or their Korean spouse) about living in Korea — residence status (F-6), extension of stay, alien registration, reporting duties, re-entry, nationality/naturalisation, multicultural family support — into search queries for a database of Korean statutes: 출입국관리법 and its 시행령·시행규칙, 재한외국인 처우 기본법, 다문화가족지원법, 국적법.
- Write queries_ko in formal Korean legal terminology as used in Korean statutes (e.g. 체류기간 연장허가, 외국인등록사항 변경신고), not colloquial words.
- Produce 1-3 queries that cover different angles (the requirement/procedure, the deadline/obligation, the sanction or exception).
- First decide intent. For smalltalk or unclear, return queries_ko as an empty list and standalone_question equal to the user's message.
- If earlier conversation turns are given, resolve pronouns and follow-ups into a standalone question. Never add topics the user did not ask about: earlier assistant messages (lists of example topics, suggestions) are not the user's question.
- Pick domains from the allowed list; use "other" if unsure.
Vietnamese → Korean immigration-law glossary:
{glossary_text()}"""


async def rewrite_query(question: str, lang: Lang, history: list[dict]) -> RewrittenQuery:
    try:
        return await llm.parse(
            RewrittenQuery,
            INSTRUCTIONS,
            [*history[-6:], {"role": "user", "content": question}],
            fast=True,
        )
    except Exception:  # LLM 실패 시 원문 그대로 검색
        log.exception("질의 재작성 실패, 원문으로 검색")
        return RewrittenQuery(intent="legal", queries_ko=[question], domains=[], as_of=None,
                              standalone_question=question)


def resolve_as_of(q: RewrittenQuery, explicit: date | None) -> date:
    if explicit:
        return explicit
    if q.as_of:
        try:
            return date.fromisoformat(q.as_of)
        except ValueError:
            pass
    return today_kr()
