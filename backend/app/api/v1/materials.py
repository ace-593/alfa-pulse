from fastapi import APIRouter

from app.api.v1.common import ContextDep, contract_route

router = APIRouter()


@contract_route(router, "listMaterials")
async def list_materials(context: ContextDep):
    return await context.services["catalog"].materials(
        context.actor,
        context.limit,
        context.cursor,
        context.query.get("q"),
        context.query.get("kind"),
        context.query.get("publishedFrom"),
        context.query.get("publishedTo"),
    )


@contract_route(router, "getMaterial")
async def get_material(context: ContextDep):
    return await context.services["catalog"].material(
        context.actor, context.path["materialId"], context.query.get("version")
    )
