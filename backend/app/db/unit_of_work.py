from sqlalchemy import text

from app.repositories.resource_repo import ResourceRepository
from app.repositories.session_repo import SessionRepository
from app.repositories.user_repo import UserRepository


class SqlUnitOfWork:
    def __init__(self, sessions):
        self.factory = sessions

    async def __aenter__(self):
        self.session = self.factory()
        await self.session.begin()
        self.resources = ResourceRepository(self.session)
        self.users = UserRepository(self.session)
        self.sessions = SessionRepository(self.session)
        return self

    async def lock(self, key):
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})

    async def __aexit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            await self.session.close()
