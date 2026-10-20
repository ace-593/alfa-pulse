from datetime import datetime, timedelta

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, and_, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import Session, User, now


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(512))
    admin: Mapped[bool] = mapped_column(Boolean, default=False)


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class RefreshRow(Base):
    __tablename__ = "refresh_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class ResourceRow(Base):
    __tablename__ = "resources"
    kind: Mapped[str] = mapped_column(String(40), primary_key=True)
    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (Index("ix_resource_data", "data", postgresql_using="gin"),)


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


class ResourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, kind, key):
        row = await self.session.get(ResourceRow, (kind, key), populate_existing=True)
        return row.data if row else None

    async def put(self, kind, key, data, create=False):
        statement = insert(ResourceRow).values(kind=kind, key=key, data=data, updated_at=now())
        if not create:
            statement = statement.on_conflict_do_update(
                index_elements=[ResourceRow.kind, ResourceRow.key], set_={"data": data, "updated_at": now()}
            )
        await self.session.execute(statement)

    async def list(self, kind, filters=None):
        statement = select(ResourceRow.data).where(ResourceRow.kind == kind)
        if filters:
            statement = statement.where(ResourceRow.data.contains(filters))
        return list((await self.session.scalars(statement.order_by(ResourceRow.key))).all())

    async def delete(self, kind, key):
        row = await self.session.get(ResourceRow, (kind, key))
        if row:
            await self.session.delete(row)

    async def claim_job(self):
        row = await self.session.scalar(
            select(ResourceRow)
            .where(
                ResourceRow.kind == "job",
                or_(
                    ResourceRow.data["status"].astext == "queued",
                    and_(
                        ResourceRow.data["status"].astext == "running",
                        ResourceRow.updated_at < now() - timedelta(minutes=10),
                    ),
                ),
            )
            .order_by(ResourceRow.updated_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        data = {**row.data, "status": "running", "updatedAt": now().isoformat()}
        row.data = data
        row.updated_at = now()
        await self.session.flush()
        return data


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


def database(url):
    engine = create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=10)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return engine, lambda: SqlUnitOfWork(sessions)
