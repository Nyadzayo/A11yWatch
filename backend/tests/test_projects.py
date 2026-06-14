import uuid

PROJECT = {"name": "My Site", "base_url": "https://example.com", "scan_frequency_minutes": 1440}


async def _other_user_headers(client):
    creds = {"email": "other@example.com", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=creds)
    token = (await client.post("/api/v1/auth/login", json=creds)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_project(client, auth_headers):
    r = await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My Site"
    assert body["base_url"] == "https://example.com"
    assert body["status"] == "idle"
    assert "id" in body


async def test_create_project_requires_auth(client):
    r = await client.post("/api/v1/projects", json=PROJECT)
    assert r.status_code == 401


async def test_create_project_validation_422(client, auth_headers):
    r = await client.post("/api/v1/projects", json={"name": "x"}, headers=auth_headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_list_projects_pagination(client, auth_headers):
    for i in range(3):
        await client.post(
            "/api/v1/projects", json={**PROJECT, "name": f"S{i}"}, headers=auth_headers
        )
    r = await client.get("/api/v1/projects?limit=2&offset=0", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2


async def test_list_projects_filter_by_base_url(client, auth_headers):
    await client.post(
        "/api/v1/projects",
        json={**PROJECT, "base_url": "https://a.example.com"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/projects",
        json={**PROJECT, "base_url": "https://b.example.com"},
        headers=auth_headers,
    )
    r = await client.get("/api/v1/projects?base_url=https://b.example.com", headers=auth_headers)
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["base_url"] == "https://b.example.com"


async def test_list_only_own_projects(client, auth_headers):
    await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)
    other = await _other_user_headers(client)
    r = await client.get("/api/v1/projects", headers=other)
    assert r.json()["total"] == 0


async def test_get_project(client, auth_headers):
    pid = (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]
    r = await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == pid


async def test_get_missing_project_404(client, auth_headers):
    r = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_update_project(client, auth_headers):
    pid = (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]
    r = await client.patch(
        f"/api/v1/projects/{pid}", json={"name": "Renamed"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"


async def test_delete_project(client, auth_headers):
    pid = (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]
    r = await client.delete(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)).status_code == 404


async def test_cannot_access_others_project(client, auth_headers):
    pid = (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]
    other = await _other_user_headers(client)
    r = await client.get(f"/api/v1/projects/{pid}", headers=other)
    assert r.status_code == 404  # don't leak existence to non-owners
