async def test_register_creates_user(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "secret123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "a@example.com"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=payload)
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


async def test_register_invalid_email_422(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "notanemail", "password": "secret123"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_login_returns_bearer_token(client):
    creds = {"email": "l@example.com", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=creds)
    r = await client.post("/api/v1/auth/login", json=creds)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_401(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "w@example.com", "password": "secret123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "w@example.com", "password": "WRONG-pass"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_returns_current_user(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "owner@example.com"
