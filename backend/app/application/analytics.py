from app.application.common import company_access, fingerprint, identifier, owned, page, public
from app.domain.models import Actor, AppError, iso
from app.domain.policies import date, relevance


def claim(text, kind, citations=(), features=(), supports=(), assumptions=()):
    return {
        "id": identifier(),
        "text": text,
        "kind": kind,
        "certainty": "confirmed" if kind == "confirmed_fact" else "conditional",
        "citations": list(citations),
        "featureIds": list(features),
        "supportingClaimIds": list(supports),
        "assumptions": list(assumptions),
    }


def citation(material):
    return {"materialId": material["id"], "materialVersion": material["version"], "quote": material["text"][:700]}


def verified_claims(items, materials, feature_ids, known_claims=()):
    by_key = {(m["id"], m["version"]): m for m in materials}
    ids = {c["id"] for c in items} | set(known_claims)
    for value in items:
        if not value["text"].strip() or not set(value["featureIds"]) <= set(feature_ids):
            raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "Вывод содержит неизвестные признаки")
        if not set(value["supportingClaimIds"]) <= ids or value["id"] in value["supportingClaimIds"]:
            raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "Некорректное основание вывода")
        for ref in value["citations"]:
            source = by_key.get((ref["materialId"], ref["materialVersion"]))
            if source is None or not ref["quote"] or ref["quote"] not in source["text"]:
                raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "Цитата не подтверждается источником")
            if value["kind"] == "bank_position" and source["kind"] != "bank_analytics":
                raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "Нет банковского источника")
        if value["kind"] in {"confirmed_fact", "bank_position"} and not value["citations"]:
            raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "Отсутствует первоисточник")
        if not any(value[k] for k in ["citations", "featureIds", "supportingClaimIds"]):
            raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "У вывода нет оснований")
    graph = {v["id"]: v["supportingClaimIds"] for v in items}

    def visit(node, path):
        if node in path:
            raise AppError(422, "UNGROUNDED_MODEL_OUTPUT", "Цикл в основаниях")
        for parent in graph.get(node, []):
            visit(parent, path | {node})

    for key in graph:
        visit(key, set())


class AnalyticsService:
    def __init__(self, uow, model):
        self.uow = uow
        self.model = model

    async def list(self, actor, company_id, limit, cursor):
        async with self.uow() as uow:
            await company_access(uow, actor, company_id)
            values = await uow.resources.list("digest", {"companyId": company_id, "_owner": actor.id})
        values.sort(key=lambda v: (v["createdAt"], v["id"]), reverse=True)
        values = [
            {
                "id": v["id"],
                "companyId": v["companyId"],
                "createdAt": v["createdAt"],
                "status": v["status"],
                "itemCount": len(v["items"]),
            }
            for v in values
        ]
        return page(values, limit, cursor, f"digests:{actor.id}:{company_id}")

    async def get(self, actor, company_id, digest_id):
        async with self.uow() as uow:
            value = await owned(uow, actor, "digest", digest_id)
            if value["companyId"] != company_id:
                raise AppError(404, "NOT_FOUND", "Объект не найден")
            return public(value)

    async def get_answer(self, actor, company_id, digest_id, answer_id):
        await self.get(actor, company_id, digest_id)
        async with self.uow() as uow:
            value = await owned(uow, actor, "answer", answer_id)
            if value["digestId"] != digest_id:
                raise AppError(404, "NOT_FOUND", "Объект не найден")
            result = public(value)
            result.pop("companyId", None)
            return result

    async def feedback(self, actor, company_id, digest_id, body):
        digest = await self.get(actor, company_id, digest_id)
        async with self.uow() as uow:
            if body["targetType"] == "insight":
                if not any(v["id"] == body["targetId"] for v in digest["items"]):
                    raise AppError(422, "INVALID_TARGET", "Событие не принадлежит сводке")
            else:
                answer = await owned(uow, actor, "answer", body["targetId"])
                if answer["digestId"] != digest_id:
                    raise AppError(422, "INVALID_TARGET", "Ответ не принадлежит сводке")
            result = {"id": identifier(), "createdAt": iso()}
            await uow.resources.put(
                "feedback",
                result["id"],
                {**result, **body, "digestId": digest_id, "companyId": company_id, "_owner": actor.id},
                create=True,
            )
        return result

    async def step(self, job, stage, summary, materials=(), features=(), retry=None):
        async with self.uow() as uow:
            trace = await uow.resources.get("trace", job["_runId"]) or {
                "id": job["_runId"],
                "jobId": job["id"],
                "companyId": job.get("companyId"),
                "_owner": job["_owner"],
                "steps": [],
                "modelIds": [self.model.model_id] if self.model.enabled else [],
                "inputTokens": 0,
                "outputTokens": 0,
            }
            trace["steps"].append(
                {
                    "id": identifier(),
                    "stage": stage,
                    "status": "succeeded",
                    "startedAt": iso(),
                    "finishedAt": iso(),
                    "materialIds": list(materials),
                    "featureIds": list(features),
                    "resultSummary": summary,
                    "retryReason": retry,
                }
            )
            await uow.resources.put("trace", trace["id"], trace)

    async def model_claim(self, task, context, sources, features, job):
        error = None
        for _attempt in range(2):
            result = await self.model.complete(task, {**context, "validationError": error})
            try:
                converted = []
                for v in result.get("claims", []):
                    if (
                        not isinstance(v, dict)
                        or not isinstance(v.get("text"), str)
                        or not isinstance(v.get("materialIds", []), list)
                    ):
                        raise ValueError("claim shape")
                    refs = []
                    for source_id in v.get("materialIds", []):
                        source = next((m for m in sources if m["id"] == source_id), None)
                        if source is None:
                            raise ValueError("unknown source")
                        refs.append(citation(source))
                    feature_ids = v.get("featureIds", [])
                    if not isinstance(feature_ids, list):
                        raise ValueError("feature ids")
                    converted.append(
                        claim(
                            v["text"],
                            "model_inference",
                            refs,
                            feature_ids,
                            assumptions=["Сценарный вывод модели; требует проверки перед принятием решения."],
                        )
                    )
                if not converted:
                    raise ValueError("empty claims")
                verified_claims(converted, sources, features)
                return converted
            except (AppError, ValueError, KeyError, TypeError) as exc:
                error = str(exc)
                await self.step(
                    job,
                    "adaptation",
                    "Повтор генерации: первичный ответ не прошел проверку ссылок",
                    retry="Неподтвержденные или неполные основания",
                )
        raise AppError(
            503, "MODEL_VERIFICATION_FAILED", "Модель не смогла сформировать вывод с проверяемыми основаниями"
        )

    async def generate(self, job):
        payload = job["_payload"]
        context = payload["_context"]
        prefs = payload["_preferences"]
        actor = Actor(job["_owner"], "", job["_admin"])
        features = [f["id"] for f in context["features"]]
        await self.step(
            job,
            "planning",
            "План: контекст → поиск → классификация → дедупликация → ранжирование → интерпретация → проверка",
        )
        async with self.uow() as uow:
            company = await company_access(uow, actor, job["companyId"])
            materials = await uow.resources.list("material")
            company_tags = company.get("_tags", [])
            if payload["scope"] == "group":
                members = await uow.resources.list("company", {"groupId": company["groupId"]})
                company_tags = list({t for c in members for t in c.get("_tags", [])})
        await self.step(job, "context", "Зафиксирован снимок признаков и настроек пользователя", features=features)
        start, end = date(payload["period"]["from"]), date(payload["period"]["to"])
        materials = [
            m
            for m in materials
            if m["availability"] == "available" and m["publishedAt"] and start <= date(m["publishedAt"]) < end
        ]
        if prefs["topics"]:
            materials = [
                m
                for m in materials
                if any(t.casefold() in (" ".join(m["topics"]) + " " + m["text"]).casefold() for t in prefs["topics"])
            ]
        if prefs["regions"]:
            materials = [m for m in materials if any(r.casefold() in m["text"].casefold() for r in prefs["regions"])]
        await self.step(job, "retrieval", f"Найдено материалов: {len(materials)}", [m["id"] for m in materials])
        if self.model.enabled:
            plan = await self.model.complete(
                "planning",
                {
                    "features": context["features"],
                    "question": "Определи направления анализа. Верни JSON с полем topics: массив тегов из переданных материалов.",
                    "availableTopics": sorted({t for m in materials for t in m["topics"]}),
                },
            )
            await self.step(
                job, "planning", "Модель уточнила направления поиска; инструменты ограничены доступными материалами"
            )
            suggested = plan.get("topics", [])
            if isinstance(suggested, list) and all(isinstance(t, str) for t in suggested):
                company_tags = list(set(company_tags) | (set(suggested) & {t for m in materials for t in m["topics"]}))
        await self.step(job, "classification", "Внешние новости отделены от аналитики банка; темы нормализованы")
        seen, news, bank = set(), [], []
        for m in materials:
            signature = fingerprint(" ".join(m["text"].split()).encode())
            if signature in seen:
                continue
            seen.add(signature)
            (bank if m["kind"] == "bank_analytics" else news).append(m)
        await self.step(
            job, "deduplication", f"Уникальных внешних событий: {len(news)}, банковских материалов: {len(bank)}"
        )
        scored = [(relevance(company_tags, m["topics"], prefs["role"]), m) for m in news]
        scored = sorted([(s, m) for s, m in scored if s > 0], key=lambda v: (-v[0], v[1]["id"]))[
            : payload.get("maxItems", 10)
        ]
        await self.step(job, "ranking", f"Отобрано событий: {len(scored)}; учтены профиль и роль {prefs['role']}")
        items, used = [], {}
        limitations = list(context["limitations"])
        if not self.model.enabled:
            limitations.append("LLM не настроена. Показан проверяемый анализ правилами, а не результат AI-агента.")
        if not scored:
            limitations.append("За выбранный период значимые события не найдены; проверь период, темы и источники.")
        for score, material in scored:
            related = [m for m in bank if set(m["topics"]) & set(material["topics"])][:3]
            sources = [material, *related]
            used.update({m["id"]: m for m in sources})
            fact = claim(material["text"][:700], "confirmed_fact", [citation(material)])
            position = [claim(m["text"][:700], "bank_position", [citation(m)]) for m in related]
            reason = claim(
                f"Событие связано с признаками компании: {', '.join(sorted(set(company_tags) & set(material['topics'])))}. Приоритет учитывает роль {prefs['role']}.",
                "model_inference",
                [citation(material)],
                features,
            )
            if self.model.enabled:
                interpretations = await self.model_claim(
                    "interpretation",
                    {
                        "context": context,
                        "role": prefs["role"],
                        "materials": public(sources),
                        "question": "Объясни причинную связь события с компанией, возможные последствия, риски, возможности и релевантные действия. Не приписывай выводы банку.",
                    },
                    sources,
                    features,
                    job,
                )
            else:
                interpretations = [
                    claim(
                        "Нужно сопоставить условия из события с фактическими договорами и объемами операций компании. Само наличие продукта не определяет размер финансового эффекта.",
                        "model_inference",
                        [citation(material)],
                        features,
                        assumptions=["Требуются структура договоров, сроки и объемы операций."],
                    )
                ]
            risks = [
                {
                    "claim": claim(
                        "При подтвержденной зависимости бизнеса от затронутых условий возможны изменения затрат или сроков денежных потоков.",
                        "model_inference",
                        [citation(material)],
                        features,
                        assumptions=["Зависимость и величина эффекта требуют уточнения."],
                    ),
                    "severity": "medium",
                    "horizon": "unknown",
                }
            ]
            opportunities = [
                {
                    "claim": claim(
                        "Сопоставить новые условия с текущими договорами: при наличии подходящего окна может быть полезен пересмотр условий финансирования, закупок или размещения средств.",
                        "model_inference",
                        [citation(material)],
                        features,
                        assumptions=["Выгода не рассчитана без договорных данных."],
                    ),
                    "severity": "medium",
                    "horizon": "unknown",
                }
            ]
            actions = [
                claim(
                    "Уточнить объем затронутых операций, сроки договоров и доступные альтернативы; сравнить базовый и неблагоприятный сценарии.",
                    "model_inference",
                    [citation(material)],
                    features,
                )
            ]
            item = {
                "id": identifier(),
                "eventId": material["id"],
                "companyId": job["companyId"],
                "title": material["title"],
                "summary": interpretations[0]["text"],
                "occurredAt": material["publishedAt"],
                "relevanceScore": score,
                "relevanceExplanation": reason,
                "facts": [fact],
                "bankPosition": position,
                "bankPositionStatus": "available" if position else "not_found",
                "interpretation": interpretations,
                "risks": risks,
                "opportunities": opportunities,
                "suggestedActions": actions,
                "limitations": []
                if position
                else ["В доступных материалах не найдена подтвержденная позиция банка по событию."],
            }
            all_claims = [
                fact,
                *position,
                reason,
                *interpretations,
                *actions,
                *[v["claim"] for v in risks + opportunities],
            ]
            verified_claims(all_claims, sources, features)
            items.append(item)
        await self.step(
            job,
            "interpretation",
            "Сформированы отдельные факты, позиция банка, сценарные выводы и действия",
            list(used),
            features,
        )
        await self.step(
            job,
            "verification",
            "Проверены цитаты, версии источников, признаки компании и отсутствие циклов оснований",
            list(used),
            features,
        )
        return {
            "id": job["_resultId"],
            "companyId": job["companyId"],
            "createdAt": iso(),
            "status": "partial",
            "period": payload["period"],
            "preferences": prefs,
            "contextSnapshot": context,
            "items": items,
            "materials": public(list(used.values())),
            "limitations": limitations,
            "runId": job["_runId"],
            "_owner": job["_owner"],
        }

    async def answer(self, job):
        payload = job["_payload"]
        actor = Actor(job["_owner"], "", job["_admin"])
        async with self.uow() as uow:
            digest = await owned(uow, actor, "digest", payload["_digestId"])
            parent = (
                await owned(uow, actor, "answer", payload["parentAnswerId"]) if payload.get("parentAnswerId") else None
            )
        selected = [v for v in digest["items"] if not payload.get("insightId") or v["id"] == payload["insightId"]]
        sources = digest["materials"]
        features = [v["id"] for v in digest["contextSnapshot"]["features"]]
        await self.step(job, "planning", "Уточнение по зафиксированному контексту сводки и выбранному событию")
        await self.step(
            job, "retrieval", "Загружены источники и предыдущий ответ диалога", [m["id"] for m in sources], features
        )
        limitations, claims = [], []
        if self.model.enabled and sources:
            claims = await self.model_claim(
                "answer",
                {
                    "question": payload["question"],
                    "perspective": payload.get("perspective", "general"),
                    "context": digest["contextSnapshot"],
                    "insights": selected,
                    "materials": sources,
                    "previousAnswer": public(parent),
                },
                sources,
                features,
                job,
            )
        else:
            limitations = [
                "Для произвольного уточняющего вопроса нужно настроить разрешенную LLM. Выдуманный ответ не сформирован."
            ]
        await self.step(
            job,
            "verification",
            "Ответ проверен по доступным источникам; нехватка данных отмечена явно",
            [m["id"] for m in sources],
            features,
        )
        return {
            "id": job["_resultId"],
            "companyId": job["companyId"],
            "digestId": digest["id"],
            "question": payload["question"],
            "parentAnswerId": payload.get("parentAnswerId"),
            "createdAt": iso(),
            "claims": claims,
            "materials": [],
            "additionalFeatures": [],
            "status": "answered" if claims else "insufficient_data",
            "limitations": limitations,
            "runId": job["_runId"],
            "_owner": job["_owner"],
        }
