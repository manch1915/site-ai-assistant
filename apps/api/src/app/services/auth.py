import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import AuthSession, User

password_hash = PasswordHash.recommended()


class InvalidCredentialsError(Exception):
    pass


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession, ttl_hours: int) -> None:
        self.session = session
        self.ttl = timedelta(hours=ttl_hours)

    async def login(self, email: str, password: str) -> tuple[User, str]:
        user = await self.session.scalar(select(User).where(User.email == email.strip().lower()))
        # Verify against a dummy hash for unknown emails so timing doesn't reveal accounts.
        stored = user.password_hash if user else password_hash.hash("timing-equaliser")
        if not password_hash.verify(password, stored) or user is None:
            raise InvalidCredentialsError
        return user, await self.start_session(user)

    async def start_session(self, user: User) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        await self.session.execute(delete(AuthSession).where(AuthSession.expires_at < now))
        self.session.add(
            AuthSession(token_hash=_digest(token), user_id=user.id, expires_at=now + self.ttl)
        )
        await self.session.commit()
        return token

    async def user_for(self, token: str) -> User | None:
        record = await self.session.get(AuthSession, _digest(token))
        if record is None or record.expires_at < datetime.now(UTC):
            return None
        return await self.session.get(User, record.user_id)

    async def logout(self, token: str) -> None:
        await self.session.execute(
            delete(AuthSession).where(AuthSession.token_hash == _digest(token))
        )
        await self.session.commit()
