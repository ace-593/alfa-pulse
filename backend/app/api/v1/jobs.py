from fastapi import APIRouter

from app.api.v1.common import ContextDep, contract_route

router = APIRouter()


@contract_route(router, "getJob")
async def get_job(context: ContextDep):
    return await context.services["jobs"].get(context.actor, context.path["jobId"])


@contract_route(router, "getRunTrace")
async def get_run_trace(context: ContextDep):
    result = await context.services["jobs"].trace(context.actor, context.path["runId"])
    result.pop("companyId", None)
    return result
