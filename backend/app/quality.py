import asyncio
import json

from app.core.config import Settings
from app.db.session import database
from app.services.quality_service import QualityService


async def run():
    engine, factory = database(Settings().database_url)
    try:
        print(json.dumps(await QualityService(factory).report(), ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
