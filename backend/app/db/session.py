from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.unit_of_work import SqlUnitOfWork


def database(url):
    engine = create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=10)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return engine, lambda: SqlUnitOfWork(sessions)
