from app.core.entities import iso
from app.schemas.contracts import validate


async def operator(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "operator@example.com", "password": "Operator-password-321"}
    )
    assert response.status_code == 200
    client.headers["Authorization"] = "Bearer " + response.json()["tokens"]["accessToken"]


async def drain(client, job_id):
    services = client.application.state.services
    await services["jobs"].execute_one(services["analytics"], services["ingestion"])
    return (await client.get(f"/api/v1/jobs/{job_id}")).json()


async def test_csv_import_is_atomic_and_preserves_permissions(client, signed_in):
    token = client.headers["Authorization"]
    await operator(client)
    files = {
        "companies": (
            "companies.csv",
            b"SYNTHETIC_U,MAINOKVED_NAME,MAINOKVED_CODE,REVENUE_COMPANY,CL_PRODUCT_LOA_MARK,GROUP_ID\nnew-a,Metal,24.1,20000000000,1,g\nnew-b,Transport,49.1,18000000000,0,g\n",
        ),
        "personLinks": ("people.csv", b"SYNTHETIC_F,SYNTHETIC_U\nperson,new-a\nperson,new-b\n"),
        "payments": ("payments.csv", b"BENEFICIARY,PAYER,PAY_AMT,PAY_CNT\nnew-b,new-a,10.20,2\nnew-b,new-a,0.30,1\n"),
    }
    response = await client.post(
        "/api/v1/admin/dataset-imports",
        files=files,
        data={"datasetVersion": "fresh-v1"},
        headers={"Idempotency-Key": "import"},
    )
    assert response.status_code == 202, response.text
    job = await drain(client, response.json()["id"])
    assert job["status"] == "succeeded", job
    report = (await client.get(job["result"]["href"])).json()
    validate(report, {"$ref": "#/components/schemas/IngestionReport"})
    assert report["processed"] == 6
    relations = (await client.get("/api/v1/companies/new-a/relations")).json()["items"]
    assert {v["type"] for v in relations} == {"payment", "same_group", "shared_person"}
    payment = next(v for v in relations if v["type"] == "payment")
    assert payment["paymentAmount"] == "10.50" and payment["paymentCount"] == 3
    assert payment["paymentCurrency"] is None
    assert (await client.get("/api/v1/companies/new-a/context?scope=group")).status_code == 200
    client.headers["Authorization"] = token
    assert (await client.get("/api/v1/companies/new-a")).status_code == 404


async def test_invalid_dataset_rolls_back(client):
    await operator(client)
    files = {
        "companies": ("c.csv", b"SYNTHETIC_U\npartial-company\n"),
        "personLinks": ("p.csv", b"SYNTHETIC_F,SYNTHETIC_U\np,missing\n"),
        "payments": ("m.csv", b"BENEFICIARY,PAYER,PAY_AMT,PAY_CNT\npartial-company,partial-company,1,1\n"),
    }
    response = await client.post(
        "/api/v1/admin/dataset-imports",
        files=files,
        data={"datasetVersion": "broken"},
        headers={"Idempotency-Key": "broken-import"},
    )
    job = await drain(client, response.json()["id"])
    assert job["status"] == "failed"
    assert job["error"]["code"] == "BROKEN_LINKS"
    assert (await client.get("/api/v1/companies/partial-company")).status_code == 404


class FakeFetcher:
    async def collect(self, source, published_from=None):
        return [
            {
                "id": "unseen-source-material",
                "kind": source["kind"],
                "title": "Свежая новость",
                "publisher": "Тестовый издатель",
                "url": "https://example.com/news",
                "publishedAt": iso(),
                "retrievedAt": iso(),
                "version": "1",
                "text": "Новая ситуация на рынке кредитования",
                "topics": ["credit"],
                "availability": "available",
            }
        ]


async def test_ingestion_preserves_versions_and_deduplicates(client):
    await operator(client)
    services = client.application.state.services
    services["ingestion"].fetcher = FakeFetcher()
    async with services["jobs"].uow() as uow:
        await uow.resources.put(
            "source",
            "test-source",
            {
                "id": "test-source",
                "name": "Test",
                "kind": "external_news",
                "url": "https://example.com/news",
                "enabled": True,
                "lastSuccessfulSyncAt": None,
            },
        )
    sources = await client.get("/api/v1/admin/sources")
    validate(sources.json(), {"$ref": "#/components/schemas/SourcePage"})
    reports = []
    for key in ["first", "second"]:
        response = await client.post(
            "/api/v1/admin/material-ingestions", json={"sourceIds": ["test-source"]}, headers={"Idempotency-Key": key}
        )
        assert response.status_code == 202
        job = await drain(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        reports.append((await client.get(job["result"]["href"])).json())
    assert reports[0]["created"] == 1
    assert reports[1]["duplicates"] == 1
    material = await client.get("/api/v1/materials/unseen-source-material?version=1")
    assert material.status_code == 200


async def test_budget_rejects_before_provider_request(client):
    import pytest

    from app.core.config import Settings
    from app.core.exceptions import AppError
    from app.services.llm_service import HttpModel

    services = client.application.state.services
    settings = Settings(
        llm_base_url="https://provider.example/v1",
        llm_api_key="test",
        llm_model_id="approved",
        llm_allowed_model_ids="approved",
        llm_input_rub_per_million=1e9,
        llm_output_rub_per_million=1e9,
    )
    model = HttpModel(services["jobs"].uow, settings)
    with pytest.raises(AppError) as error:
        await model.complete("planning", {"context": "test"})
    assert error.value.code == "LLM_BUDGET_EXCEEDED"
