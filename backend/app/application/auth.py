import asyncio
import secrets
from datetime import timedelta

from app.application.common import fingerprint, identifier
from app.application.ports import Security, UowFactory
from app.domain.models import Actor, AppError, Session, User, now
from app.domain.policies import normalize_email


class AuthService:
    def __init__(self, uow: UowFactory, security: Security, demo: bool):
        self.uow = uow
        self.security = security
        self.demo = demo

    @staticmethod
    def user_view(user):
        permissions = ["analytics:read", "analytics:write", "traces:read"]
        if user.admin:
            permissions.append("ingestion:write")
        return {"id": user.id, "email": user.email, "displayName": user.display_name, "permissions": permissions}

    async def tokens(self, uow, session):
        refresh = secrets.token_urlsafe(48)
        await uow.sessions.save(session)
        await uow.sessions.add_refresh(fingerprint(refresh.encode()), session.id)
        return {
            "accessToken": self.security.access_token(session.user_id, session.id),
            "refreshToken": refresh,
            "tokenType": "Bearer",
            "expiresIn": 900,
            "refreshExpiresIn": max(1, int((session.expires_at - now()).total_seconds())),
        }

    async def register(self, email, password, display_name):
        email = normalize_email(email)
        encoded = await asyncio.to_thread(self.security.password_hash, password)
        user = User(identifier(), email, display_name.strip(), encoded)
        async with self.uow() as uow:
            await uow.lock(f"email:{email}")
            if await uow.users.by_email(email):
                raise AppError(409, "EMAIL_ALREADY_REGISTERED", "Email уже зарегистрирован")
            await uow.users.add(user)
            if self.demo:
                for company in await uow.resources.list("company", {"_demo": True}):
                    await uow.resources.put(
                        "membership", f"{user.id}:{company['id']}", {"userId": user.id, "companyId": company["id"]}
                    )
            tokens = await self.tokens(uow, Session(identifier(), user.id, now() + timedelta(days=30)))
        return {"user": self.user_view(user), "tokens": tokens}

    async def login(self, email, password, ip):
        email = normalize_email(email)
        denied = False
        async with self.uow() as uow:
            key = fingerprint(ip.encode())
            await uow.lock(f"login:{key}")
            rate = await uow.resources.get("login_rate", key) or {
                "count": 0,
                "until": (now() + timedelta(minutes=15)).timestamp(),
            }
            if rate["until"] <= now().timestamp():
                rate = {"count": 0, "until": (now() + timedelta(minutes=15)).timestamp()}
            if rate["count"] >= 10:
                raise AppError(429, "LOGIN_RATE_LIMIT", "Слишком много попыток входа")
            user = await uow.users.by_email(email)
            encoded = (
                user.password_hash if user else await asyncio.to_thread(self.security.password_hash, "dummy-password")
            )
            matches = await asyncio.to_thread(self.security.password_matches, password, encoded)
            if user is None or not matches:
                rate["count"] += 1
                await uow.resources.put("login_rate", key, rate)
                denied = True
            else:
                await uow.resources.delete("login_rate", key)
                tokens = await self.tokens(uow, Session(identifier(), user.id, now() + timedelta(days=30)))
        if denied:
            raise AppError(401, "INVALID_CREDENTIALS", "Неверный email или пароль")
        return {"user": self.user_view(user), "tokens": tokens}

    async def refresh(self, token):
        denied = False
        key = fingerprint(token.encode())
        async with self.uow() as uow:
            await uow.lock(f"refresh:{key}")
            record = await uow.sessions.refresh_record(key)
            session = await uow.sessions.get(record[0]) if record else None
            if not session or session.revoked or session.expires_at <= now():
                denied = True
            elif record[1]:
                session.revoked = True
                await uow.sessions.save(session)
                denied = True
            else:
                await uow.sessions.consume(key)
                result = await self.tokens(uow, session)
        if denied:
            raise AppError(401, "INVALID_REFRESH_TOKEN", "Refresh-токен недействителен")
        return result

    async def authenticate(self, token):
        claims = self.security.decode(token)
        async with self.uow() as uow:
            session = await uow.sessions.get(claims["sid"])
            if not session or session.revoked or session.expires_at <= now() or session.user_id != claims["sub"]:
                raise AppError(401, "INVALID_TOKEN", "Сессия недействительна")
            user = await uow.users.get(session.user_id)
            if not user:
                raise AppError(401, "INVALID_TOKEN", "Сессия недействительна")
        return Actor(user.id, session.id, user.admin)

    async def me(self, actor):
        async with self.uow() as uow:
            return self.user_view(await uow.users.get(actor.id))

    async def logout(self, actor):
        async with self.uow() as uow:
            session = await uow.sessions.get(actor.session_id)
            session.revoked = True
            await uow.sessions.save(session)
