from fastapi import APIRouter

from app.api.v1.common import ContextDep, contract_route

router = APIRouter()


@contract_route(router, "listCompanies")
async def list_companies(context: ContextDep):
    return await context.services["catalog"].companies(
        context.actor,
        context.limit,
        context.cursor,
        context.query.get("q"),
        context.query.get("groupId"),
    )


@contract_route(router, "getCompany")
async def get_company(context: ContextDep):
    return await context.services["catalog"].company(context.actor, context.path["companyId"])


@contract_route(router, "getPreferences")
@contract_route(router, "replacePreferences")
async def preferences(context: ContextDep):
    return await context.services["catalog"].preferences(context.actor, context.path["companyId"], context.body)


@contract_route(router, "getCompanyContext")
async def company_context(context: ContextDep):
    return await context.services["catalog"].context(
        context.actor, context.path["companyId"], context.query.get("scope", "company")
    )


@contract_route(router, "listCompanyRelations")
async def company_relations(context: ContextDep):
    return await context.services["catalog"].relations(
        context.actor,
        context.path["companyId"],
        context.limit,
        context.cursor,
        context.query.get("type"),
    )
