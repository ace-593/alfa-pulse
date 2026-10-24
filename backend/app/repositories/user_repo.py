from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import User
from app.models.users import UserRow


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def entity(row):
        return User(row.id, row.email, row.display_name, row.password_hash, row.admin) if row else None

    async def get(self, user_id):
        return self.entity(await self.session.get(UserRow, user_id))

    async def by_email(self, email):
        return self.entity(await self.session.scalar(select(UserRow).where(UserRow.email == email)))

    async def add(self, user):
        self.session.add(UserRow(**vars(user)))
        await self.session.flush()
