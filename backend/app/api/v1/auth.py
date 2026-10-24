from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.api.v1.common import ContextDep, contract_route
from app.core.exceptions import AppError

router = APIRouter()


@contract_route(router, "register")
async def register(context: ContextDep):
    body = context.body
    if not body["displayName"].strip():
        raise AppError(422, "INVALID_NAME", "Укажи имя")
    result = await context.services["auth"].register(body["email"], body["password"], body["displayName"])
    return JSONResponse(result, status_code=201, headers={"Cache-Control": "no-store"})


@contract_route(router, "login")
async def login(context: ContextDep):
    result = await context.services["auth"].login(
        context.body["email"], context.body["password"], context.request.client.host
    )
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@contract_route(router, "refreshTokens")
async def refresh_tokens(context: ContextDep):
    result = await context.services["auth"].refresh(context.body["refreshToken"])
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@contract_route(router, "logout")
async def logout(context: ContextDep):
    await context.services["auth"].logout(context.actor)
    return Response(status_code=204)


@contract_route(router, "getCurrentUser")
async def current_user(context: ContextDep):
    return await context.services["auth"].me(context.actor)
