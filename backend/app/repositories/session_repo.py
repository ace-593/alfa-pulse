from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Session
from app.models.sessions import RefreshRow, SessionRow


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, session_id):
        row = await self.session.get(SessionRow, session_id, populate_existing=True)
        return Session(row.id, row.user_id, row.expires_at, row.revoked) if row else None

    async def save(self, entity):
        await self.session.merge(SessionRow(**vars(entity)))
        await self.session.flush()

    async def add_refresh(self, token_hash, session_id):
        self.session.add(RefreshRow(token_hash=token_hash, session_id=session_id, used=False))
        await self.session.flush()

    async def refresh_record(self, token_hash):
        row = await self.session.get(RefreshRow, token_hash, populate_existing=True)
        return (row.session_id, row.used) if row else None

    async def consume(self, token_hash):
        row = await self.session.get(RefreshRow, token_hash)
        row.used = True
        await self.session.flush()
