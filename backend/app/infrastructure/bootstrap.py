import json
import secrets
from pathlib import Path

from app.application.common import fingerprint, identifier
from app.domain.models import User, iso
from app.domain.policies import normalize_email
from app.infrastructure.security import JwtSecurity


async def bootstrap(uow_factory, settings):
    async with uow_factory() as uow:
        await uow.lock("bootstrap")
        config = await uow.resources.get("config", "jwt")
        key = settings.secret_key or (config["secret"] if config else secrets.token_urlsafe(48))
        if not config:
            await uow.resources.put("config", "jwt", {"secret": key})
        security = JwtSecurity(key)
        if settings.admin_email and settings.admin_password:
            email = normalize_email(settings.admin_email)
            if not await uow.users.by_email(email):
                if len(settings.admin_password) < 12:
                    raise ValueError("ADMIN_PASSWORD must be at least 12 characters")
                await uow.users.add(
                    User(identifier(), email, "Оператор", security.password_hash(settings.admin_password), True)
                )
        source_path = Path(settings.source_config)
        if source_path.exists():
            for source in json.loads(source_path.read_text()):
                if not source.get("id") or source["kind"] not in {"external_news", "bank_analytics"}:
                    raise ValueError("Invalid source configuration")
                old = await uow.resources.get("source", source["id"])
                await uow.resources.put(
                    "source",
                    source["id"],
                    {
                        "id": source["id"],
                        "kind": source["kind"],
                        "name": source["name"],
                        "url": source["url"],
                        "enabled": source.get("enabled", True),
                        "lastSuccessfulSyncAt": old.get("lastSuccessfulSyncAt") if old else None,
                        "_format": source.get("format", "rss"),
                        "_publishedAt": source.get("publishedAt"),
                    },
                )
        if settings.demo_data and not await uow.resources.get("config", "demo-seeded"):
            seed = json.loads(Path("data/seed.json").read_text())
            for company in seed["companies"]:
                company_id = company["id"]
                raw_features = {
                    "REVENUE_COMPANY": ("Годовая выручка, млрд RUB", str(company["revenue"])),
                    "MAINOKVED_NAME": ("Вид деятельности", company["industry"]),
                    "REGION": ("Регион регистрации", company["region"]),
                    "BANK_PRODUCTS": ("Банковские продукты", ", ".join(company["products"])),
                    "FTS_COUNTRY_NAME": ("Страны ФТС", ", ".join(company["countries"])),
                    "WORKERS": ("Количество сотрудников", company["workers"]),
                }
                features = [
                    {
                        "id": fingerprint([company_id, field])[:24],
                        "name": name,
                        "value": value or None,
                        "origin": "dataset",
                        "sourceField": field,
                        "datasetVersion": "synthetic-v1",
                        "confidence": 1.0,
                        "missingReason": None,
                    }
                    for field, (name, value) in raw_features.items()
                ]
                row = {
                    "id": company_id,
                    "displayName": company["name"],
                    "groupId": company["group"] or None,
                    "mainOkvedCode": company["okved"],
                    "mainOkvedName": company["industry"],
                    "region": company["region"],
                    "city": company["city"],
                    "_demo": True,
                    "_version": "synthetic-v1",
                    "_features": features,
                    "_tags": company["tags"],
                    "_summary": "Синтетическая компания. " + company["description"],
                }
                await uow.resources.put("company", company_id, row)
            for event in seed["events"]:
                text = "Синтетический тестовый сценарий. " + event["fact"]
                row = {
                    "id": "demo-" + event["id"],
                    "kind": "external_news",
                    "title": "[Тестовые данные] " + event["title"],
                    "publisher": "Синтетический набор для проверки",
                    "url": None,
                    "publishedAt": iso(),
                    "retrievedAt": iso(),
                    "version": fingerprint(text.encode())[:24],
                    "text": text,
                    "topics": event["tags"],
                    "availability": "available",
                    "_demo": True,
                }
                await uow.resources.put("material", row["id"], row)
                await uow.resources.put("material_version", f"{row['id']}:{row['version']}", row)
            await uow.resources.put("config", "demo-seeded", {"at": iso()})
    return security
