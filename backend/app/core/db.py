from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def vector_literal(vec: list[float]) -> str:
    """pgvector 입력 문자열. SQL에서 CAST(:v AS vector)로 사용."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
