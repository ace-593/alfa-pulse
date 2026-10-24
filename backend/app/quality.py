import asyncio
import json

from app.application.quality import QualityService
from app.infrastructure.config import Settings
from app.infrastructure.database import database


async def run():
    engine, factory = database(Settings().database_url)
    try:
        print(json.dumps(await QualityService(factory).report(), ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
