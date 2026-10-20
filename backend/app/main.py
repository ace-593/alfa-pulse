import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.application.analytics import AnalyticsService
from app.application.auth import AuthService
from app.application.catalog import CatalogService
from app.application.ingestion import IngestionService
from app.application.jobs import JobService
from app.domain.models import AppError
from app.infrastructure.bootstrap import bootstrap
from app.infrastructure.config import Settings
from app.infrastructure.database import database
from app.infrastructure.model import HttpModel
from app.infrastructure.sources import HttpSourceFetcher
from app.presentation.api import router
from app.presentation.contracts import SPEC


async def build_services(settings):
    engine, factory = database(settings.database_url)
    security = await bootstrap(factory, settings)
    catalog = CatalogService(factory)
    model = HttpModel(factory, settings)
    return engine, {
        "auth": AuthService(factory, security, settings.demo_data),
        "catalog": catalog,
        "jobs": JobService(factory, catalog),
        "analytics": AnalyticsService(factory, model),
        "ingestion": IngestionService(factory, HttpSourceFetcher()),
    }


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        engine, services = await build_services(settings)
        app.state.services = services
        app.state.engine = engine
        yield
        await engine.dispose()

    app = FastAPI(
        title="Alfa Pulse",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )
    app.openapi = lambda: SPEC
    app.include_router(router)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logging.getLogger("pulse").exception("request_failed")
            response = JSONResponse(
                {
                    "code": "INTERNAL_ERROR",
                    "message": "Внутренняя ошибка сервиса",
                    "requestId": request.state.request_id,
                },
                status_code=500,
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        logging.getLogger("pulse").info(
            "request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000),
            },
        )
        return response

    @app.exception_handler(AppError)
    async def application_error(request, error):
        headers = {"Retry-After": "60"} if error.status in {429, 503} else {}
        if error.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            {"code": error.code, "message": error.message, "requestId": request.state.request_id},
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request, error):
        return JSONResponse(
            {"code": "CONFLICT", "message": "Конфликт записи", "requestId": request.state.request_id}, status_code=409
        )

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(request, error):
        return JSONResponse(
            {
                "code": "DATABASE_UNAVAILABLE",
                "message": "База данных недоступна",
                "requestId": request.state.request_id,
            },
            status_code=503,
        )

    @app.get("/healthz", include_in_schema=False)
    async def health():
        async with app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app


app = create_app()
