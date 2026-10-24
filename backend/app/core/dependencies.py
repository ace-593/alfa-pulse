from app.core.bootstrap import bootstrap
from app.db.session import database
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.ingestion_service import IngestionService
from app.services.jobs_service import JobService
from app.services.llm_service import HttpModel
from app.services.source_service import HttpSourceFetcher


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
