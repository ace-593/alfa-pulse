import asyncio
import json
from pathlib import Path

from openapi_spec_validator import validate_spec

from app.presentation.contracts import SPEC, validate


def check(value, schema):
    validate(value, {"$ref": f"#/components/schemas/{schema}"})


def test_openapi_and_repository_copies_agree():
    validate_spec(SPEC)
    assert SPEC == json.loads(Path("../docs/openapi.json").read_text())
    assert sum(len(v) for v in SPEC["paths"].values()) == 25


async def test_register_normalizes_email_and_returns_contract(client, signed_in):
    check(signed_in, "AuthResponse")
    assert signed_in["user"]["displayName"] == "Анастасия"
    assert "password" not in str(signed_in["user"])
    assert signed_in["tokens"]["expiresIn"] == 900
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    check(me.json(), "User")
    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"email": " USER@EXAMPLE.COM ", "password": "Example-password-321", "displayName": "Другой"},
    )
    assert duplicate.status_code == 409


async def test_bad_credentials_and_validation(client, signed_in):
    assert (
        await client.post("/api/v1/auth/register", json={"email": "bad", "password": "short", "displayName": ""})
    ).status_code == 422
    for email in ["user@example.com", "unknown@example.com"]:
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong-password-321"})
        assert r.status_code == 401
        assert r.json()["code"] == "INVALID_CREDENTIALS"
    assert (await client.post("/api/v1/auth/login", content="{")).status_code == 400
    assert (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "x@example.com", "password": "Example-password-321", "displayName": "  ", "admin": True},
        )
    ).status_code == 422


async def test_refresh_rotation_replay_revokes_session(client, signed_in):
    old = signed_in["tokens"]["refreshToken"]
    response = await client.post("/api/v1/auth/refresh", json={"refreshToken": old})
    assert response.status_code == 200
    check(response.json(), "TokenPair")
    assert response.json()["refreshToken"] != old
    assert (await client.post("/api/v1/auth/refresh", json={"refreshToken": old})).status_code == 401
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_concurrent_refresh_has_one_winner_and_revokes_replay(client, signed_in):
    body = {"refreshToken": signed_in["tokens"]["refreshToken"]}
    responses = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json=body), client.post("/api/v1/auth/refresh", json=body)
    )
    assert sorted(r.status_code for r in responses) == [200, 401]
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_logout_revokes_access_and_refresh(client, signed_in):
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 204 and r.content == b""
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refreshToken": signed_in["tokens"]["refreshToken"]})
    ).status_code == 401


async def test_login_rate_limit(client):
    for _ in range(10):
        r = await client.post(
            "/api/v1/auth/login", json={"email": "missing@example.com", "password": "Wrong-password-321"}
        )
        assert r.status_code == 401
    assert (
        await client.post("/api/v1/auth/login", json={"email": "missing@example.com", "password": "Wrong-password-321"})
    ).status_code == 429


async def test_public_and_protected_routes(client):
    assert (await client.get("/healthz")).status_code == 200
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await client.get("/api/v1/companies")).status_code == 401
    assert (await client.get("/api/v1/openapi.json")).json() == SPEC
