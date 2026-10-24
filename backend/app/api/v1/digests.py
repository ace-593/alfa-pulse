from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.v1.common import ContextDep, contract_route, enqueue
from app.core.exceptions import AppError
from app.services.policies import date

router = APIRouter()


@contract_route(router, "listDigests")
async def list_digests(context: ContextDep):
    return await context.services["analytics"].list(
        context.actor, context.path["companyId"], context.limit, context.cursor
    )


@contract_route(router, "getDigest")
async def get_digest(context: ContextDep):
    return await context.services["analytics"].get(context.actor, context.path["companyId"], context.path["digestId"])


@contract_route(router, "getAnswer")
async def get_answer(context: ContextDep):
    return await context.services["analytics"].get_answer(
        context.actor,
        context.path["companyId"],
        context.path["digestId"],
        context.path["answerId"],
    )


@contract_route(router, "createFeedback")
async def create_feedback(context: ContextDep):
    result = await context.services["analytics"].feedback(
        context.actor, context.path["companyId"], context.path["digestId"], context.body
    )
    return JSONResponse(result, status_code=201)


@contract_route(router, "createDigest")
async def create_digest(context: ContextDep):
    if date(context.body["period"]["from"]) >= date(context.body["period"]["to"]):
        raise AppError(422, "INVALID_PERIOD", "Начало периода должно быть раньше конца")
    return await enqueue(context, "digest_generation", context.body)


@contract_route(router, "askDigestQuestion")
async def ask_question(context: ContextDep):
    if not context.body["question"].strip():
        raise AppError(422, "EMPTY_QUESTION", "Вопрос не должен быть пустым")
    return await enqueue(context, "question_answering", {**context.body, "_digestId": context.path["digestId"]})
