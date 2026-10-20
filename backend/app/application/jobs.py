from datetime import timedelta

from app.application.common import admin_access, company_access, fingerprint, identifier, owned, public, required
from app.domain.models import AppError, iso, now
from app.domain.policies import date


class JobService:
    def __init__(self, uow, catalog):
        self.uow = uow
        self.catalog = catalog

    async def enqueue(self, actor, kind, payload, key, route, company_id=None):
        digest_id = payload.get("_digestId")
        async with self.uow() as uow:
            if company_id:
                await company_access(uow, actor, company_id)
            else:
                admin_access(actor)
            identity = fingerprint([actor.id, route, key])
            await uow.lock(f"idempotency:{identity}")
            existing = await uow.resources.get("idempotency", identity)
            body_hash = fingerprint(payload)
            if existing and date(existing["expiresAt"]) > now():
                if existing["bodyHash"] != body_hash:
                    raise AppError(409, "IDEMPOTENCY_CONFLICT", "Ключ уже использован с другим запросом")
                return public(await required(uow, "job", existing["jobId"]))
            if kind == "digest_generation":
                payload = {
                    **payload,
                    "_context": await self.catalog.context_in(uow, actor, company_id, payload["scope"]),
                    "_preferences": await uow.resources.get("preferences", f"{actor.id}:{company_id}")
                    or {"role": "other", "topics": [], "regions": [], "scope": "company"},
                }
            if kind == "question_answering":
                digest = await owned(uow, actor, "digest", digest_id)
                if digest["companyId"] != company_id:
                    raise AppError(404, "NOT_FOUND", "Объект не найден")
                if payload.get("insightId") and not any(v["id"] == payload["insightId"] for v in digest["items"]):
                    raise AppError(422, "INVALID_INSIGHT", "Событие не принадлежит сводке")
                if payload.get("parentAnswerId"):
                    parent = await owned(uow, actor, "answer", payload["parentAnswerId"])
                    if parent["digestId"] != digest_id:
                        raise AppError(422, "INVALID_PARENT", "Ответ не принадлежит сводке")
            job_id = identifier()
            job = {
                "id": job_id,
                "kind": kind,
                "status": "queued",
                "createdAt": iso(),
                "updatedAt": iso(),
                "_owner": actor.id,
                "_admin": actor.admin,
                "_payload": payload,
                "_resultId": identifier(),
                "_runId": identifier(),
            }
            if company_id:
                job["companyId"] = company_id
            await uow.resources.put("job", job_id, job, create=True)
            await uow.resources.put(
                "idempotency",
                identity,
                {"jobId": job_id, "bodyHash": body_hash, "expiresAt": iso(now() + timedelta(hours=24))},
            )
            return public(job)

    async def get(self, actor, job_id):
        async with self.uow() as uow:
            value = await owned(uow, actor, "job", job_id)
            result = public(value)
            result.pop("companyId", None)
            return result

    async def trace(self, actor, run_id):
        async with self.uow() as uow:
            return public(await owned(uow, actor, "trace", run_id))

    async def report(self, actor, report_id):
        admin_access(actor)
        async with self.uow() as uow:
            return public(await required(uow, "ingestion_report", report_id))

    async def execute_one(self, analytics, ingestion):
        async with self.uow() as uow:
            job = await uow.resources.claim_job()
        if job is None:
            return False
        try:
            if job["kind"] == "digest_generation":
                kind, result = "digest", await analytics.generate(job)
                href = f"/api/v1/companies/{job['companyId']}/digests/{result['id']}"
            elif job["kind"] == "question_answering":
                kind, result = "answer", await analytics.answer(job)
                href = f"/api/v1/companies/{job['companyId']}/digests/{result['digestId']}/answers/{result['id']}"
            else:
                kind, result = "ingestion_report", await ingestion.execute(job)
                href = f"/api/v1/admin/ingestion-reports/{result['id']}"
            async with self.uow() as uow:
                await uow.resources.put(kind, result["id"], result)
                job.update(status="succeeded", updatedAt=iso(), result={"type": kind, "id": result["id"], "href": href})
                await uow.resources.put("job", job["id"], job)
        except Exception as exc:
            error = (
                exc if isinstance(exc, AppError) else AppError(500, "JOB_FAILED", "Не удалось подготовить результат")
            )
            async with self.uow() as uow:
                job.update(
                    status="failed",
                    updatedAt=iso(),
                    error={"code": error.code, "message": error.message, "requestId": job["id"]},
                )
                await uow.resources.put("job", job["id"], job)
            if not isinstance(exc, AppError):
                import logging

                logging.getLogger(__name__).error(
                    "job_failed", extra={"job_id": job["id"], "error_type": type(exc).__name__}
                )
        return True
