from datetime import timedelta

from app.domain.models import iso, now
from app.presentation.contracts import validate


def checked(value, schema):
    validate(value, {"$ref": f"#/components/schemas/{schema}"})
    return value


async def generate(client, company="metal", key="test-digest", extra=None):
    body = {
        "scope": "company",
        "period": {"from": iso(now() - timedelta(days=1)), "to": iso(now() + timedelta(days=1))},
        "maxItems": 10,
    }
    body.update(extra or {})
    response = await client.post(f"/api/v1/companies/{company}/digests", json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    job = checked(response.json(), "Job")
    services = client.application.state.services
    assert await services["jobs"].execute_one(services["analytics"], services["ingestion"])
    job = (await client.get(f"/api/v1/jobs/{job['id']}")).json()
    assert job["status"] == "succeeded", job
    checked(job, "Job")
    result = await client.get(job["result"]["href"])
    assert result.status_code == 200, result.text
    return checked(result.json(), "Digest"), body


async def test_full_offline_scenario(client, signed_in):
    companies = checked((await client.get("/api/v1/companies")).json(), "CompanyPage")
    assert len(companies["items"]) == 3
    checked((await client.get("/api/v1/companies/metal")).json(), "Company")
    context = checked((await client.get("/api/v1/companies/metal/context")).json(), "CompanyContext")
    assert context["features"]
    preferences = {"role": "cfo", "topics": [], "regions": [], "scope": "company"}
    assert (await client.put("/api/v1/companies/metal/preferences", json=preferences)).json() == preferences
    checked((await client.get("/api/v1/companies/metal/relations")).json(), "RelationPage")
    digest, _ = await generate(client)
    assert digest["items"] and digest["status"] == "partial"
    assert any("LLM" in v for v in digest["limitations"])
    assert all(v["bankPositionStatus"] == "not_found" for v in digest["items"])
    checked((await client.get("/api/v1/companies/metal/digests")).json(), "DigestPage")
    checked((await client.get(f"/api/v1/runs/{digest['runId']}/trace")).json(), "RunTrace")
    source = digest["materials"][0]
    checked(
        (await client.get(f"/api/v1/materials/{source['id']}", params={"version": source["version"]})).json(),
        "Material",
    )
    checked((await client.get("/api/v1/materials")).json(), "MaterialPage")
    feedback = await client.post(
        f"/api/v1/companies/metal/digests/{digest['id']}/feedback",
        json={"targetType": "insight", "targetId": digest["items"][0]["id"], "rating": "useful"},
    )
    assert feedback.status_code == 201
    checked(feedback.json(), "Feedback")
    question = await client.post(
        f"/api/v1/companies/metal/digests/{digest['id']}/questions",
        json={"question": "Каких данных не хватает?"},
        headers={"Idempotency-Key": "question"},
    )
    assert question.status_code == 202
    services = client.application.state.services
    await services["jobs"].execute_one(services["analytics"], services["ingestion"])
    job = (await client.get(f"/api/v1/jobs/{question.json()['id']}")).json()
    answer = checked((await client.get(job["result"]["href"])).json(), "Answer")
    assert answer["status"] == "insufficient_data" and not answer["claims"]


async def test_idempotency_and_period_validation(client, signed_in):
    digest, body = await generate(client)
    again = await client.post("/api/v1/companies/metal/digests", json=body, headers={"Idempotency-Key": "test-digest"})
    assert again.status_code == 202
    assert again.json()["result"]["id"] == digest["id"]
    changed = await client.post(
        "/api/v1/companies/metal/digests", json={**body, "maxItems": 1}, headers={"Idempotency-Key": "test-digest"}
    )
    assert changed.status_code == 409
    assert (await client.post("/api/v1/companies/metal/digests", json=body)).status_code == 422
    assert (await client.get("/api/v1/companies", params={"limit": 101})).status_code == 422
    assert (await client.get("/api/v1/companies", params={"cursor": "bad"})).status_code == 400


async def test_isolation_and_admin_permissions(client, signed_in):
    digest, _ = await generate(client)
    assert (await client.get("/api/v1/admin/sources")).status_code == 403
    other = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "Other-password-321", "displayName": "Другой"},
    )
    client.headers["Authorization"] = "Bearer " + other.json()["tokens"]["accessToken"]
    assert (await client.get(f"/api/v1/companies/metal/digests/{digest['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/runs/{digest['runId']}/trace")).status_code == 404
    assert not (await client.get("/api/v1/companies/metal/digests")).json()["items"]
    assert (await client.get(f"/api/v1/companies/agro/digests/{digest['id']}")).status_code == 404


async def test_company_and_role_change_ranking(client, signed_in):
    metal, _ = await generate(client)
    agro, _ = await generate(client, "agro", "agro-digest")
    assert {v["eventId"] for v in metal["items"]} != {v["eventId"] for v in agro["items"]}
    await client.put(
        "/api/v1/companies/metal/preferences", json={"role": "cfo", "scope": "company", "topics": [], "regions": []}
    )
    cfo, _ = await generate(client, key="cfo")
    first = {v["eventId"]: v["relevanceScore"] for v in metal["items"]}
    assert any(v["relevanceScore"] != first[v["eventId"]] for v in cfo["items"])


async def test_empty_period_is_successful_with_explanation(client, signed_in):
    value, _ = await generate(client, extra={"period": {"from": "2000-01-01T00:00:00Z", "to": "2000-02-01T00:00:00Z"}})
    assert value["items"] == []
    assert any("не найдены" in v for v in value["limitations"])


class FakeModel:
    enabled = True
    model_id = "approved-test-model"

    def __init__(self):
        self.attempts = 0

    async def complete(self, task, context):
        if task == "planning":
            return {"topics": ["credit"]}
        self.attempts += 1
        if self.attempts == 1:
            return {"claims": [{"text": "Неверный источник", "materialIds": ["nonexistent"], "featureIds": []}]}
        return {
            "claims": [
                {
                    "text": "При сохранении стоимости финансирования компании с кредитными продуктами стоит сравнить график платежей и альтернативные источники ликвидности. Размер эффекта без структуры долга неизвестен.",
                    "materialIds": [context["materials"][0]["id"]],
                    "featureIds": [context["context"]["features"][0]["id"]],
                }
            ]
        }


async def test_agent_retries_invalid_sources_and_handles_unseen_bank_material(client, signed_in):
    services = client.application.state.services
    services["analytics"].model = FakeModel()
    async with services["jobs"].uow() as uow:
        bank = {
            "id": "fresh-bank",
            "kind": "bank_analytics",
            "title": "Новый тестовый банковский отчет",
            "publisher": "Синтетический источник теста",
            "url": None,
            "publishedAt": iso(),
            "retrievedAt": iso(),
            "version": "1",
            "text": "Тестовая позиция: изменение стоимости финансирования влияет на планирование ликвидности.",
            "topics": ["credit"],
            "availability": "available",
        }
        await uow.resources.put("material", bank["id"], bank)
    digest, _ = await generate(client)
    assert any(v["bankPositionStatus"] == "available" for v in digest["items"])
    trace = (await client.get(f"/api/v1/runs/{digest['runId']}/trace")).json()
    assert any(v["stage"] == "adaptation" for v in trace["steps"])
    assert trace["modelIds"] == ["approved-test-model"]
