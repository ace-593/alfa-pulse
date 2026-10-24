from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import now
from app.models.resources import ResourceRow


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
        data = {**row.data, "status": "running", "updatedAt": now().isoformat(), "_lease": str(uuid4())}
        row.data = data
        row.updated_at = now()
        await self.session.flush()
        return data
