from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.entities import Actor
from app.core.exceptions import AppError
from app.schemas.contracts import SPEC, check_request


def contract_route(router: APIRouter, operation_id: str):
    """Bind one endpoint to the existing versioned OpenAPI contract."""
    for path, methods in SPEC["paths"].items():
        for method, operation in methods.items():
            if operation["operationId"] == operation_id:
                return router.api_route(
                    path,
                    methods=[method.upper()],
                    name=operation_id,
                    openapi_extra={"contract": operation},
                    include_in_schema=False,
                )
    raise ValueError(f"Unknown operation: {operation_id}")


@dataclass
class RequestContext:
    request: Request
    actor: Actor | None
    body: Any

    @property
    def services(self):
        return self.request.app.state.services

    @property
    def path(self):
        return self.request.path_params

    @property
    def query(self):
        return self.request.query_params

    @property
    def limit(self):
        return int(self.query.get("limit", 20))

    @property
    def cursor(self):
        return self.query.get("cursor")


async def get_request_context(request: Request):
    operation = request.scope["route"].openapi_extra["contract"]
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
        actor = await request.app.state.services["auth"].authenticate(header[7:])
    return RequestContext(request, actor, body)


ContextDep = Annotated[RequestContext, Depends(get_request_context)]


async def enqueue(context: RequestContext, kind: str, payload: dict):
    result = await context.services["jobs"].enqueue(
        context.actor,
        kind,
        payload,
        context.request.headers["Idempotency-Key"],
        context.request.url.path,
        context.path.get("companyId"),
    )
    result.pop("companyId", None)
    return JSONResponse(
        result, status_code=202, headers={"Location": f"/api/v1/jobs/{result['id']}", "Retry-After": "1"}
    )
