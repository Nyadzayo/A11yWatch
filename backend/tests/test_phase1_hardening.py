"""Tests added from the Phase 1 adversarial review: multi-tenant authz,
validation/auth gaps, pagination edges, and the error-handling bugs."""

from a11ywatch.core.db import get_session
from a11ywatch.main import app

PROJECT = {"name": "Site", "base_url": "https://example.com"}


async def _headers(client, email):
    creds = {"email": email, "password": "secret123"}
    await client.post("/api/v1/auth/register", json=creds)
    token = (await client.post("/api/v1/auth/login", json=creds)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _make_project(client, headers):
    return (await client.post("/api/v1/projects", json=PROJECT, headers=headers)).json()["id"]


# --- Multi-tenant isolation (mutations + scans) ---


async def test_cannot_patch_others_project(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    other = await _headers(client, "intruder1@example.com")
    r = await client.patch(f"/api/v1/projects/{pid}", json={"name": "Hacked"}, headers=other)
    assert r.status_code == 404


async def test_cannot_delete_others_project(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    other = await _headers(client, "intruder2@example.com")
    r = await client.delete(f"/api/v1/projects/{pid}", headers=other)
    assert r.status_code == 404
    assert (await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)).status_code == 200


async def test_cannot_trigger_scan_on_others_project(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    other = await _headers(client, "intruder3@example.com")
    r = await client.post(f"/api/v1/projects/{pid}/scans", headers=other)
    assert r.status_code == 404


async def test_cannot_get_others_scan(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    sid = (await client.post(f"/api/v1/projects/{pid}/scans", headers=auth_headers)).json()[
        "scan_id"
    ]
    other = await _headers(client, "intruder4@example.com")
    r = await client.get(f"/api/v1/scans/{sid}", headers=other)
    assert r.status_code == 404


async def test_cannot_list_others_scans(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    other = await _headers(client, "intruder5@example.com")
    r = await client.get(f"/api/v1/projects/{pid}/scans", headers=other)
    assert r.status_code == 404


# --- Validation / auth coverage ---


async def test_register_short_password_422(client):
    r = await client.post(
        "/api/v1/auth/register", json={"email": "p@example.com", "password": "short"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_login_unknown_email_401(client):
    r = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "secret123"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_me_invalid_token_401(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_register_duplicate_email_case_insensitive(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "Case@Example.com", "password": "secret123"}
    )
    r = await client.post(
        "/api/v1/auth/register", json={"email": "case@example.com", "password": "secret123"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


async def test_create_project_invalid_base_url_422(client, auth_headers):
    r = await client.post(
        "/api/v1/projects", json={"name": "X", "base_url": "notaurl"}, headers=auth_headers
    )
    assert r.status_code == 422


async def test_update_project_invalid_base_url_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.patch(
        f"/api/v1/projects/{pid}", json={"base_url": "notaurl"}, headers=auth_headers
    )
    assert r.status_code == 422


async def test_list_projects_offset_beyond_range(client, auth_headers):
    for _ in range(3):
        await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)
    r = await client.get("/api/v1/projects?limit=10&offset=100", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["items"] == []


async def test_invalid_pagination_422(client, auth_headers):
    r = await client.get("/api/v1/projects?limit=0", headers=auth_headers)
    assert r.status_code == 422


# --- Bug fixes (these should FAIL before the fix) ---


async def test_patch_null_base_url_rejected_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.patch(f"/api/v1/projects/{pid}", json={"base_url": None}, headers=auth_headers)
    assert r.status_code == 422


async def test_validation_error_does_not_echo_password(client):
    r = await client.post(
        "/api/v1/auth/register", json={"email": "leak@example.com", "password": "tinypw"}
    )
    assert r.status_code == 422
    assert "tinypw" not in r.text
    for item in r.json()["error"].get("details", []):
        assert "input" not in item


async def test_unhandled_exception_is_enveloped(client, auth_headers):
    async def _boom():
        raise RuntimeError("boom")
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = _boom
    r = await client.get("/api/v1/projects", headers=auth_headers)
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
