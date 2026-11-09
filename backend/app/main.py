import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from .database import build_engine, session_factory
from .routers import cancellation, case_detail, criteria, rejection


def create_app(engine: Engine | None = None, demo_mode: bool | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        enabled = demo_mode if demo_mode is not None else os.environ.get("DEMO_MODE") == "1"
        if not enabled:
            raise RuntimeError("로컬 모의 계정 시연 전용입니다. DEMO_MODE=1로 실행하세요.")
        db_engine = engine if engine is not None else build_engine()
        app.state.demo_mode = enabled
        app.state.session_factory = session_factory(db_engine)
        try:
            yield
        finally:
            if engine is None:
                db_engine.dispose()

    app = FastAPI(title="준비 건 담당자 반려 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Demo-Account"],
    )

    app.include_router(case_detail.router)
    app.include_router(rejection.router)
    app.include_router(cancellation.router)
    app.include_router(criteria.router)

    return app


app = create_app()
