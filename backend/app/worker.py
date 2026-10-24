import asyncio
import logging
import signal

from app.infrastructure.config import Settings
from app.main import build_services


async def run():
    settings = Settings()
    engine, services = await build_services(settings)
    stopped = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stopped.set)
    try:
        while not stopped.is_set():
            try:
                worked = await services["jobs"].execute_one(services["analytics"], services["ingestion"])
                if worked:
                    continue
            except Exception:
                logging.getLogger("pulse.worker").exception("worker_iteration_failed")
            try:
                await asyncio.wait_for(stopped.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
