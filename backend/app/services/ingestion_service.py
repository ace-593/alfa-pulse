import base64
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from app.core.entities import iso
from app.core.exceptions import AppError
from app.services.common import fingerprint, required
from app.services.policies import csv_rows, date

FIELD_NAMES = {
    "MAINOKVED_NAME": "Основной вид деятельности",
    "REVENUE_COMPANY": "Годовая выручка",
    "REGION": "Регион регистрации",
    "CITY": "Город регистрации",
    "FTS_COUNTRY_NAME": "Страна ФТС",
    "COMPANY_AGE_YEARS_GRADATION": "Возраст компании",
    "AMOUNT_WORKERS_FNS_GRADATION": "Количество сотрудников",
    "CL_PRODUCT_LOA_MARK": "Кредитные продукты",
    "CL_PRODUCT_DEP_MARK": "Депозиты",
    "CL_PRODUCT_LEA_MARK": "Лизинг",
    "FACTORING_MARK": "Факторинг",
}


def tags_from_row(row):
    tags = []
    for field, tag in [
        ("CL_PRODUCT_LOA_MARK", "credit"),
        ("CL_PRODUCT_DEP_MARK", "deposit"),
        ("CL_PRODUCT_LEA_MARK", "leasing"),
    ]:
        if row.get(field, "").strip().lower() in {"1", "1.0", "true", "да"}:
            tags.append(tag)
    if row.get("FTS_COUNTRY_NAME"):
        tags.append("fx")
    code = row.get("MAINOKVED_CODE", "")
    if code.startswith(("24", "25")):
        tags.append("metal")
    if code.startswith(("49", "50", "51", "52", "53")):
        tags.append("logistics")
    if code.startswith("01"):
        tags.append("agro")
    return tags


class IngestionService:
    def __init__(self, uow, fetcher):
        self.uow = uow
        self.fetcher = fetcher

    async def execute(self, job):
        if job["kind"] == "dataset_import":
            return await self.import_dataset(job)
        payload = job["_payload"]
        report = {
            "id": job["_resultId"],
            "jobId": job["id"],
            "processed": 0,
            "created": 0,
            "duplicates": 0,
            "rejected": 0,
            "warnings": [],
        }
        succeeded = 0
        for source_id in payload["sourceIds"]:
            async with self.uow() as uow:
                source = await required(uow, "source", source_id)
            if not source["enabled"]:
                report["warnings"].append(f"Источник {source_id} отключен")
                continue
            try:
                records = await self.fetcher.collect(
                    source, date(payload["publishedFrom"]) if payload.get("publishedFrom") else None
                )
                async with self.uow() as uow:
                    await uow.lock("material-ingestion")
                    for record in records:
                        report["processed"] += 1
                        if not record["text"].strip():
                            report["rejected"] += 1
                            continue
                        existing = await uow.resources.get("material", record["id"])
                        if existing and existing["version"] == record["version"]:
                            report["duplicates"] += 1
                        else:
                            await uow.resources.put("material", record["id"], record)
                            await uow.resources.put("material_version", f"{record['id']}:{record['version']}", record)
                            report["created"] += 1
                    source["lastSuccessfulSyncAt"] = iso()
                    await uow.resources.put("source", source_id, source)
                succeeded += 1
            except (AppError, ValueError):
                report["warnings"].append(f"Источник {source_id} недоступен или вернул неподдерживаемый материал")
        if not succeeded:
            raise AppError(503, "SOURCES_UNAVAILABLE", "Не удалось обработать ни один источник")
        return report

    async def import_dataset(self, job):
        payload = job["_payload"]
        files = {k: base64.b64decode(v, validate=True) for k, v in payload["files"].items()}
        companies = csv_rows(files["companies"], {"SYNTHETIC_U"})
        links = csv_rows(files["personLinks"], {"SYNTHETIC_F", "SYNTHETIC_U"})
        payments = csv_rows(files["payments"], {"BENEFICIARY", "PAYER", "PAY_AMT", "PAY_CNT"})
        if sum(map(len, [companies, links, payments])) > 100000:
            raise AppError(422, "DATASET_TOO_LARGE", "Для прототипа допускается до 100000 строк в наборе")
        ids = {r["SYNTHETIC_U"] for r in companies}
        if len(ids) != len(companies) or any(not value or len(value) > 128 for value in ids):
            raise AppError(
                422, "INVALID_COMPANY_IDS", "ID компаний должны быть уникальными непустыми строками до 128 символов"
            )
        if any(r["SYNTHETIC_U"] not in ids for r in links) or any(
            r["PAYER"] not in ids or r["BENEFICIARY"] not in ids for r in payments
        ):
            raise AppError(422, "BROKEN_LINKS", "Связи ссылаются на отсутствующие компании")
        version = payload["datasetVersion"]
        rows, relations = [], []
        for r in companies:
            company_id = r["SYNTHETIC_U"]
            features = [
                {
                    "id": fingerprint([company_id, field])[:24],
                    "name": name,
                    "value": r.get(field) or None,
                    "origin": "dataset",
                    "sourceField": field,
                    "datasetVersion": version,
                    "confidence": 1.0 if r.get(field) else 0.0,
                    "missingReason": None if r.get(field) else "В наборе данных отсутствует значение",
                }
                for field, name in FIELD_NAMES.items()
            ]
            rows.append(
                {
                    "id": company_id,
                    "displayName": f"Компания {company_id}",
                    "groupId": r.get("GROUP_ID") or None,
                    "mainOkvedCode": r.get("MAINOKVED_CODE") or None,
                    "mainOkvedName": r.get("MAINOKVED_NAME") or None,
                    "region": r.get("REGION") or None,
                    "city": r.get("CITY") or None,
                    "_version": version,
                    "_features": features,
                    "_tags": tags_from_row(r),
                    "_summary": r.get("MAINOKVED_NAME", "Контекст неполный"),
                    "_demo": False,
                }
            )
        aggregated = {}
        try:
            for r in payments:
                amount = Decimal(r["PAY_AMT"].replace(",", "."))
                count = int(r["PAY_CNT"])
                if not amount.is_finite() or amount < 0 or count < 0:
                    raise ValueError
                key = (r["PAYER"], r["BENEFICIARY"])
                old_amount, old_count = aggregated.get(key, (Decimal(0), 0))
                aggregated[key] = (old_amount + amount, old_count + count)
        except (ValueError, InvalidOperation) as exc:
            raise AppError(
                422, "INVALID_PAYMENTS", "Платежи должны содержать неотрицательные суммы и целое количество"
            ) from exc
        for (payer, beneficiary), (amount, count) in aggregated.items():
            relations.append(
                {
                    "id": fingerprint(["payment", payer, beneficiary])[:32],
                    "fromId": payer,
                    "toId": beneficiary,
                    "type": "payment",
                    "direction": "outgoing",
                    "paymentAmount": format(amount, "f"),
                    "paymentCurrency": None,
                    "paymentCount": count,
                    "datasetVersion": version,
                }
            )
        groups, persons = defaultdict(set), defaultdict(set)
        for r in companies:
            if r.get("GROUP_ID"):
                groups[r["GROUP_ID"]].add(r["SYNTHETIC_U"])
        for r in links:
            persons[r["SYNTHETIC_F"]].add(r["SYNTHETIC_U"])
        warnings = []
        for relation_type, sets in [("same_group", groups), ("shared_person", persons)]:
            for nodes in sets.values():
                ordered = sorted(nodes)
                if len(ordered) > 100:
                    warnings.append("Для большой группы/связи сохранены ребра к опорной компании вместо полного графа")
                for i, first in enumerate(ordered):
                    if len(ordered) > 100 and i > 0:
                        break
                    for second in ordered[i + 1 :]:
                        relations.append(
                            {
                                "id": fingerprint([relation_type, first, second])[:32],
                                "fromId": first,
                                "toId": second,
                                "type": relation_type,
                                "direction": "undirected",
                                "datasetVersion": version,
                            }
                        )
        async with self.uow() as uow:
            await uow.lock("dataset-import")
            existing = await uow.resources.get("dataset", version)
            checksum = fingerprint(payload["files"])
            if existing and existing["checksum"] != checksum:
                raise AppError(409, "DATASET_VERSION_CONFLICT", "Версия уже используется другим набором данных")
            if not existing:
                for row in rows:
                    await uow.resources.put("company", row["id"], row)
                for row in relations:
                    await uow.resources.put("relation", row["id"], row)
                await uow.resources.put("dataset", version, {"version": version, "checksum": checksum})
        return {
            "id": job["_resultId"],
            "jobId": job["id"],
            "datasetVersion": version,
            "processed": len(companies) + len(links) + len(payments),
            "created": 0 if existing else len(rows) + len(relations),
            "duplicates": len(rows) + len(relations) if existing else 0,
            "rejected": 0,
            "warnings": sorted(set(warnings)),
        }
