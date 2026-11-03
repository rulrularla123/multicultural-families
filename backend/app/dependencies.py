from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request


@dataclass(frozen=True)
class DemoActor:
    id: str
    role: str


DEMO_ACTORS = {
    "demo-officer": DemoActor("demo-officer", "officer"),
    "demo-user-1": DemoActor("demo-user-1", "user"),
    "demo-user-2": DemoActor("demo-user-2", "user"),
}


def get_actor(
    request: Request,
    account: Annotated[str | None, Header(alias="X-Demo-Account")] = None,
) -> DemoActor:
    if not request.app.state.demo_mode:
        raise HTTPException(503, "모의 계정 모드가 활성화되지 않았습니다.")
    actor = DEMO_ACTORS.get(account or "")
    if actor is None:
        raise HTTPException(401, "유효한 모의 계정을 선택하세요.")
    return actor


def require_officer(actor: Annotated[DemoActor, Depends(get_actor)]) -> DemoActor:
    if actor.role != "officer":
        raise HTTPException(403, "지원 담당자만 반려할 수 있습니다.")
    return actor


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


