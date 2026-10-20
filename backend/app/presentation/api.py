import base64

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.domain.models import AppError
from app.domain.policies import date
from app.presentation.contracts import SPEC, check_request

router = APIRouter()


async def dispatch(request: Request):
    services = request.app.state.services
    operation = request.scope["route"].openapi_extra["contract"]
    name = operation["operationId"]
    auth = services["auth"]
    body = None
    if "application/json" in operation.get("requestBody", {}).get("content", {}):
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise AppError(400, "INVALID_JSON", "Некорректный JSON") from exc
    check_request(request, operation, body)
    actor = None
    if operation.get("security") != []:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            raise AppError(401, "MISSING_TOKEN", "Войди в сервис")
        actor = await auth.authenticate(header[7:])
    p, q = request.path_params, request.query_params
    company = p.get("companyId")
    digest = p.get("digestId")
    limit, cursor = int(q.get("limit", 20)), q.get("cursor")
    catalog, jobs, analytics = services["catalog"], services["jobs"], services["analytics"]
    status, headers = 200, {}
    if name == "register":
        if not body["displayName"].strip():
            raise AppError(422, "INVALID_NAME", "Укажи имя")
        result = await auth.register(body["email"], body["password"], body["displayName"])
        status, headers = 201, {"Cache-Control": "no-store"}
    elif name == "login":
        result = await auth.login(body["email"], body["password"], request.client.host)
        headers = {"Cache-Control": "no-store"}
    elif name == "refreshTokens":
        result = await auth.refresh(body["refreshToken"])
        headers = {"Cache-Control": "no-store"}
    elif name == "logout":
        await auth.logout(actor)
        return Response(status_code=204)
    elif name == "getCurrentUser":
        result = await auth.me(actor)
    elif name == "listCompanies":
        result = await catalog.companies(actor, limit, cursor, q.get("q"), q.get("groupId"))
    elif name == "getCompany":
        result = await catalog.company(actor, company)
    elif name in {"getPreferences", "replacePreferences"}:
        result = await catalog.preferences(actor, company, body)
    elif name == "getCompanyContext":
        result = await catalog.context(actor, company, q.get("scope", "company"))
    elif name == "listCompanyRelations":
        result = await catalog.relations(actor, company, limit, cursor, q.get("type"))
    elif name == "listDigests":
        result = await analytics.list(actor, company, limit, cursor)
    elif name == "getDigest":
        result = await analytics.get(actor, company, digest)
    elif name == "getAnswer":
        result = await analytics.get_answer(actor, company, digest, p["answerId"])
    elif name == "createFeedback":
        result = await analytics.feedback(actor, company, digest, body)
        status = 201
    elif name == "listMaterials":
        result = await catalog.materials(
            actor, limit, cursor, q.get("q"), q.get("kind"), q.get("publishedFrom"), q.get("publishedTo")
        )
    elif name == "getMaterial":
        result = await catalog.material(actor, p["materialId"], q.get("version"))
    elif name == "getJob":
        result = await jobs.get(actor, p["jobId"])
    elif name == "getRunTrace":
        result = await jobs.trace(actor, p["runId"])
        result.pop("companyId", None)
    elif name == "listIngestionSources":
        result = await catalog.sources(actor, limit, cursor)
    elif name == "getIngestionReport":
        result = await jobs.report(actor, p["reportId"])
    elif name in {"createDigest", "askDigestQuestion", "startMaterialIngestion", "importClientDatasets"}:
        key = request.headers["Idempotency-Key"]
        if name == "createDigest":
            if date(body["period"]["from"]) >= date(body["period"]["to"]):
                raise AppError(422, "INVALID_PERIOD", "Начало периода должно быть раньше конца")
            kind, payload = "digest_generation", body
        elif name == "askDigestQuestion":
            if not body["question"].strip():
                raise AppError(422, "EMPTY_QUESTION", "Вопрос не должен быть пустым")
            kind, payload = "question_answering", {**body, "_digestId": digest}
        elif name == "startMaterialIngestion":
            kind, payload = "material_ingestion", body
        else:
            form = await request.form(max_files=3, max_fields=1, max_part_size=50 * 1024 * 1024)
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
            kind, payload = "dataset_import", {"datasetVersion": version, "files": files}
        result = await jobs.enqueue(actor, kind, payload, key, request.url.path, company)
        result.pop("companyId", None)
        status, headers = 202, {"Location": f"/api/v1/jobs/{result['id']}", "Retry-After": "1"}
    else:
        raise AppError(404, "NOT_FOUND", "Маршрут не найден")
    return JSONResponse(result, status_code=status, headers=headers)


for path, methods in SPEC["paths"].items():
    for method, operation in methods.items():
        router.add_api_route(
            "/api/v1" + path,
            dispatch,
            methods=[method.upper()],
            name=operation["operationId"],
            openapi_extra={"contract": operation},
            include_in_schema=False,
        )
