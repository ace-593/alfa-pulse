import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.infrastructure.config import Settings
from app.infrastructure.database import Base


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
