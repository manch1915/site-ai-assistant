import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.admin.deps import SESSION_COOKIE, AuthServiceDep, UserDep
from app.api.deps import ContainerDep, SessionDep
from app.infra.db.models import Site, User, Workspace
from app.services.auth import InvalidCredentialsError

router = APIRouter(prefix="/v1/admin", tags=["admin: auth"])


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class SiteBrief(BaseModel):
    id: uuid.UUID
    name: str
    public_key: str


class MeOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_demo: bool
    workspace: str
    sites: list[SiteBrief]


def set_session_cookie(response: Response, token: str, secure: bool, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


async def me_payload(user: User, session: SessionDep) -> MeOut:
    workspace = await session.get(Workspace, user.workspace_id)
    sites = await session.scalars(
        select(Site).where(Site.workspace_id == user.workspace_id).order_by(Site.created_at)
    )
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_demo=user.is_demo,
        workspace=workspace.name if workspace else "",
        sites=[SiteBrief(id=s.id, name=s.name, public_key=s.public_key) for s in sites],
    )


@router.post("/auth/login")
async def login(
    body: LoginIn,
    response: Response,
    auth: AuthServiceDep,
    session: SessionDep,
    container: ContainerDep,
) -> MeOut:
    try:
        user, token = await auth.login(body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password") from None
    settings = container.settings
    set_session_cookie(response, token, settings.env == "prod", settings.session_ttl_hours * 3600)
    return await me_payload(user, session)


@router.post("/auth/demo")
async def demo_login(
    response: Response,
    auth: AuthServiceDep,
    session: SessionDep,
    container: ContainerDep,
) -> MeOut:
    user = await session.scalar(select(User).where(User.is_demo.is_(True)).limit(1))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo account is not set up")
    token = await auth.start_session(user)
    settings = container.settings
    set_session_cookie(response, token, settings.env == "prod", 6 * 3600)
    return await me_payload(user, session)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth: AuthServiceDep,
    relay_session: Annotated[str | None, Cookie()] = None,
) -> None:
    if relay_session:
        await auth.logout(relay_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
async def me(user: UserDep, session: SessionDep) -> MeOut:
    return await me_payload(user, session)
