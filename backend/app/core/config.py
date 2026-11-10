from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://legal:legal@localhost:5433/legal"

    openai_api_key: str = ""
    # 모델명은 환경변수로 교체한다. fast 모델은 질의 재작성·조문 요약에 사용.
    openai_chat_model: str = "gpt-5"
    openai_fast_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-large"
    # GPT-5 계열 추론 강도 (minimal | low | medium | high). 응답 속도와 품질의 균형
    # 챗봇 답변. minimal은 빠르지만 "법 제n조"·"영 제n조" 같은 교차 참조를 잘못 읽는 경우가 있어 low를 쓴다
    openai_reasoning_effort: str = "low"
    openai_analysis_reasoning_effort: str = "minimal"  # 문서 분석
    openai_fast_reasoning_effort: str = "minimal"
    # pgvector HNSW 인덱스는 vector 타입 기준 2,000차원까지라 1536으로 줄여 쓴다.
    # 바꾸면 alembic 마이그레이션의 vector(1536)도 같이 바꿔야 한다.
    embedding_dim: int = 1536

    reranker: Literal["none", "cross-encoder"] = "none"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    retrieval_k: int = 50        # BM25 / 벡터 각각 가져올 후보 수
    context_k: int = 10          # LLM에 넘길 최종 조문 수
    graph_hops: int = 2
    graph_frontier: int = 20     # hop마다 확장할 최대 노드 수

    # 개발용: OpenAI 대신 app.llm_fake의 고정 응답을 쓴다. 시연·운영에서는 반드시 false
    llm_fake: bool = False

    # true면 '_' 샘플(테스트) 법령도 검색한다. 개발 초기 확인용
    include_samples: bool = False

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
