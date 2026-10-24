from copy import deepcopy

from app.application.common import admin_access, company_access, page, preferences, public, required
from app.domain.models import AppError, iso
from app.domain.policies import date


class CatalogService:
    def __init__(self, uow):
        self.uow = uow

    async def companies(self, actor, limit, cursor, query=None, group=None):
        async with self.uow() as uow:
            values = await uow.resources.list("company")
            memberships = {v["companyId"] for v in await uow.resources.list("membership", {"userId": actor.id})}
            values = [
                v
                for v in values
                if (actor.admin or v["id"] in memberships) and (not group or v.get("groupId") == group)
            ]
            if query:
                values = [
                    v
                    for v in values
                    if query.casefold()
                    in " ".join(
                        str(v.get(k) or "") for k in ["id", "displayName", "mainOkvedName", "mainOkvedCode"]
                    ).casefold()
                ]
            return page(values, limit, cursor, f"companies:{actor.id}:{query}:{group}")

    async def company(self, actor, company_id):
        async with self.uow() as uow:
            return public(await company_access(uow, actor, company_id))

    async def preferences(self, actor, company_id, value=None):
        async with self.uow() as uow:
            await company_access(uow, actor, company_id)
            key = f"{actor.id}:{company_id}"
            if value is not None:
                if value["scope"] == "group":
                    await self.context_in(uow, actor, company_id, "group")
                await uow.resources.put("preferences", key, value)
            return value or await uow.resources.get("preferences", key) or preferences()

    async def context_in(self, uow, actor, company_id, scope):
        company = await company_access(uow, actor, company_id)
        companies = [company]
        if scope == "group":
            if not company.get("groupId"):
                raise AppError(422, "NO_GROUP", "Компания не входит в группу")
            companies = await uow.resources.list("company", {"groupId": company["groupId"]})
            for value in companies:
                await company_access(uow, actor, value["id"])
        features = []
        for value in companies:
            features.extend(deepcopy(value.get("_features", [])))
        return {
            "companyId": company_id,
            "scope": scope,
            "version": ":".join(v.get("_version", "unknown") for v in companies),
            "generatedAt": iso(),
            "summary": "; ".join(v.get("_summary", v["displayName"]) for v in companies),
            "features": features,
            "dataQuality": "partial" if features else "insufficient",
            "limitations": [
                "Доля рынка, структура долга и платежный календарь могут отсутствовать. Отсутствие признака не означает нулевое значение."
            ],
            "_tags": sorted({tag for value in companies for tag in value.get("_tags", [])}),
        }

    async def context(self, actor, company_id, scope):
        async with self.uow() as uow:
            return public(await self.context_in(uow, actor, company_id, scope))

    async def relations(self, actor, company_id, limit, cursor, relation_type=None):
        async with self.uow() as uow:
            await company_access(uow, actor, company_id)
            result = []
            for value in await uow.resources.list("relation"):
                if company_id not in [value["fromId"], value["toId"]] or (
                    relation_type and value["type"] != relation_type
                ):
                    continue
                try:
                    await company_access(uow, actor, value["fromId"])
                    await company_access(uow, actor, value["toId"])
                except AppError:
                    continue
                result.append(
                    {
                        **value,
                        "direction": "undirected"
                        if value["type"] != "payment"
                        else "outgoing"
                        if value["fromId"] == company_id
                        else "incoming",
                    }
                )
            return page(result, limit, cursor, f"relations:{actor.id}:{company_id}:{relation_type}")

    async def materials(self, actor, limit, cursor, query=None, kind=None, start=None, end=None):
        if start and end and date(start) >= date(end):
            raise AppError(422, "INVALID_PERIOD", "Начало периода должно быть раньше конца")
        async with self.uow() as uow:
            values = await uow.resources.list("material")
            values = [v for v in values if v["availability"] == "available" and (not kind or v["kind"] == kind)]
            if query:
                values = [v for v in values if query.casefold() in (v["title"] + " " + v["text"]).casefold()]
            values = [
                v
                for v in values
                if (not start or v["publishedAt"] and date(v["publishedAt"]) >= date(start))
                and (not end or v["publishedAt"] and date(v["publishedAt"]) < date(end))
            ]
            values.sort(key=lambda v: v["id"])
            values.sort(key=lambda v: v["publishedAt"] or "", reverse=True)
            return page(values, limit, cursor, f"materials:{query}:{kind}:{start}:{end}")

    async def material(self, actor, material_id, version=None):
        async with self.uow() as uow:
            value = await required(
                uow,
                "material_version" if version else "material",
                f"{material_id}:{version}" if version else material_id,
            )
            if value["availability"] != "available":
                raise AppError(404, "NOT_FOUND", "Объект не найден")
            return public(value)

    async def sources(self, actor, limit, cursor):
        admin_access(actor)
        async with self.uow() as uow:
            return page(await uow.resources.list("source"), limit, cursor, "sources")
