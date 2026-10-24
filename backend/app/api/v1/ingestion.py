import base64

from fastapi import APIRouter

from app.api.v1.common import ContextDep, contract_route, enqueue
from app.core.exceptions import AppError
from app.services.common import admin_access

router = APIRouter()


@contract_route(router, "listIngestionSources")
async def list_sources(context: ContextDep):
    return await context.services["catalog"].sources(context.actor, context.limit, context.cursor)


@contract_route(router, "getIngestionReport")
async def get_report(context: ContextDep):
    return await context.services["jobs"].report(context.actor, context.path["reportId"])


@contract_route(router, "startMaterialIngestion")
async def start_material_ingestion(context: ContextDep):
    admin_access(context.actor)
    return await enqueue(context, "material_ingestion", context.body)


@contract_route(router, "importClientDatasets")
async def import_datasets(context: ContextDep):
    admin_access(context.actor)
    form = await context.request.form(max_files=3, max_fields=1, max_part_size=50 * 1024 * 1024)
    if set(form) != {"companies", "personLinks", "payments", "datasetVersion"}:
        raise AppError(422, "INVALID_FORM", "Некорректные поля формы")
    version = form.get("datasetVersion", "")
    if not isinstance(version, str) or not 1 <= len(version) <= 100:
        raise AppError(422, "INVALID_VERSION", "Укажи версию набора")
    files = {}
    for field in ["companies", "personLinks", "payments"]:
        uploaded = form.get(field)
        if uploaded is None or not hasattr(uploaded, "read"):
            raise AppError(422, "MISSING_FILE", f"Не указан файл: {field}")
        data = await uploaded.read(50 * 1024 * 1024 + 1)
        await uploaded.close()
        if len(data) > 50 * 1024 * 1024:
            raise AppError(413, "FILE_TOO_LARGE", "Файл превышает 50 МиБ")
        files[field] = base64.b64encode(data).decode()
    return await enqueue(context, "dataset_import", {"datasetVersion": version, "files": files})
