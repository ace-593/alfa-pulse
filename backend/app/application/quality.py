from collections import Counter

from app.domain.policies import date


class QualityService:
    def __init__(self, uow):
        self.uow = uow

    async def report(self):
        async with self.uow() as uow:
            jobs = await uow.resources.list("job")
            feedback = await uow.resources.list("feedback")
            digests = await uow.resources.list("digest")
            budgets = await uow.resources.list("budget")
        finished = [v for v in jobs if v["status"] in {"succeeded", "failed"}]
        durations = sorted((date(v["updatedAt"]) - date(v["createdAt"])).total_seconds() for v in finished)
        latest = {}
        for value in sorted(feedback, key=lambda v: v["createdAt"]):
            latest[(value["_owner"], value["targetType"], value["targetId"])] = value
        items = [item for digest in digests for item in digest["items"]]
        return {
            "jobsByStatus": dict(Counter(v["status"] for v in jobs)),
            "failureRate": sum(v["status"] == "failed" for v in finished) / len(finished) if finished else None,
            "p95CompletionSeconds": durations[min(len(durations) - 1, int(len(durations) * 0.95))]
            if durations
            else None,
            "feedbackCount": len(latest),
            "usefulRate": sum(v["rating"] == "useful" for v in latest.values()) / len(latest) if latest else None,
            "feedbackReasons": dict(Counter(reason for v in latest.values() for reason in v.get("reasons", []))),
            "bankPositionCoverage": sum(v["bankPositionStatus"] == "available" for v in items) / len(items)
            if items
            else None,
            "partialDigestCount": sum(v["status"] == "partial" for v in digests),
            "reservedLlmRub": sum(v["reservedRub"] for v in budgets),
        }
