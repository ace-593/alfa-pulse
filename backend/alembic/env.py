import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 -- register mapped tables before inspecting metadata
from alembic import context
from app.core.config import Settings
from app.db.base import Base


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    engine = create_async_engine(Settings().database_url)
    async with engine.connect() as connection:
        await connection.exec_driver_sql("SELECT pg_advisory_lock(8247613)")
        await connection.commit()
        try:
            await connection.run_sync(run)
        finally:
            await connection.exec_driver_sql("SELECT pg_advisory_unlock(8247613)")
            await connection.commit()
    await engine.dispose()


asyncio.run(migrate())
