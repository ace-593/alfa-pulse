import os

import httpx
import pytest_asyncio

from app.core.config import Settings
from app.db.base import Base
from app.db.session import database
from app.main import create_app


@pytest_asyncio.fixture
async def client():
    url = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://pulse@127.0.0.1:55432/pulse_test")
    if not url.rsplit("/", 1)[-1].startswith("pulse_test"):
        raise RuntimeError("Tests require a dedicated pulse_test database")
    settings = Settings(
        database_url=url,
        demo_data=True,
        admin_email="operator@example.com",
        admin_password="Operator-password-321",
        secret_key="test-only-secret-key-with-more-than-32-characters",
        llm_base_url="",
        llm_api_key="",
    )
    engine, _ = database(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as value:
            value.application = app
            yield value


@pytest_asyncio.fixture
async def signed_in(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "Example-password-321", "displayName": "Анастасия"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    client.headers["Authorization"] = "Bearer " + data["tokens"]["accessToken"]
    return data
