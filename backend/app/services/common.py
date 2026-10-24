import base64
import hashlib
import json
from copy import deepcopy
from uuid import uuid4

from app.core.entities import Actor
from app.core.exceptions import AppError
from app.services.ports import Document, UnitOfWork


def identifier() -> str:
    return str(uuid4())


def fingerprint(value) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def public(value):
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [public(v) for v in value]
    return value


async def required(uow: UnitOfWork, kind: str, key: str) -> Document:
    result = await uow.resources.get(kind, key)
    if result is None:
        raise AppError(404, "NOT_FOUND", "Объект не найден")
    return deepcopy(result)


async def company_access(uow: UnitOfWork, actor: Actor, company_id: str) -> Document:
    company = await required(uow, "company", company_id)
    if not actor.admin and not await uow.resources.get("membership", f"{actor.id}:{company_id}"):
        raise AppError(404, "NOT_FOUND", "Объект не найден")
    return company


async def owned(uow: UnitOfWork, actor: Actor, kind: str, key: str) -> Document:
    value = await required(uow, kind, key)
    if value.get("_owner") != actor.id:
        raise AppError(404, "NOT_FOUND", "Объект не найден")
    if value.get("companyId"):
        await company_access(uow, actor, value["companyId"])
    return value


def admin_access(actor: Actor):
    if not actor.admin:
        raise AppError(403, "FORBIDDEN", "Недостаточно прав")


def preferences() -> Document:
    return {"role": "other", "topics": [], "regions": [], "scope": "company"}


def page(items: list[Document], limit: int, cursor: str | None, scope: str) -> Document:
    offset = 0
    if cursor:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor))
            if data["scope"] != scope or type(data["offset"]) is not int or data["offset"] < 0:
                raise ValueError
            offset = data["offset"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AppError(400, "INVALID_CURSOR", "Курсор не соответствует запросу") from exc
    end = offset + limit
    next_cursor = (
        base64.urlsafe_b64encode(json.dumps({"scope": scope, "offset": end}).encode()).decode()
        if end < len(items)
        else None
    )
    return {"items": public(items[offset:end]), "nextCursor": next_cursor}
