import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import ContainerDep, SessionDep
from app.infra.db.models import Site, User
from app.services.auth import AuthService

SESSION_COOKIE = "relay_session"
CSRF_HEADER = "x-relay-csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_auth_service(session: SessionDep, container: ContainerDep) -> AuthService:
    return AuthService(session, container.settings.session_ttl_hours)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def current_user(
    request: Request,
    auth: AuthServiceDep,
    relay_session: Annotated[str | None, Cookie()] = None,
) -> User:
    # SameSite cookies plus a custom header: a cross-site form can't send either.
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")
    user = await auth.user_for(relay_session) if relay_session else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


UserDep = Annotated[User, Depends(current_user)]


async def owned_site(site_id: uuid.UUID, user: UserDep, session: SessionDep) -> Site:
    site = await session.scalar(
        select(Site).where(Site.id == site_id, Site.workspace_id == user.workspace_id)
    )
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Site not found")
    return site


SiteDep = Annotated[Site, Depends(owned_site)]


def forbid_in_demo(user: User, action: str) -> None:
    if user.is_demo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{action} is turned off in the public demo")
