import uuid

PROJECT = {"name": "My Site", "base_url": "https://example.com"}


async def _make_project(client, auth_headers):
    return (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]


async def _other_headers(client):
    creds = {"email": "other@example.com", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=creds)
    token = (await client.post("/api/v1/auth/login", json=creds)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_email_channel(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "email", "target": "alerts@example.com"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "email"
    assert body["target"] == "alerts@example.com"
    assert body["enabled"] is True
    assert body["events"] == ["new_issues"]


async def test_create_webhook_channel(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "webhook", "target": "https://hooks.example/abc"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["type"] == "webhook"


async def test_invalid_email_target_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "email", "target": "not-an-email"},
        headers=auth_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_webhook_requires_http_url_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "webhook", "target": "ftp://nope"},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_unsupported_event_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "email", "target": "a@b.com", "events": ["weekly_digest"]},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_empty_events_list_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "email", "target": "a@b.com", "events": []},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_patch_events_null_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    cid = (
        await client.post(
            f"/api/v1/projects/{pid}/alert-channels",
            json={"type": "email", "target": "a@example.com"},
            headers=auth_headers,
        )
    ).json()["id"]
    r = await client.patch(
        f"/api/v1/projects/{pid}/alert-channels/{cid}",
        json={"events": None},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_list_channels(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    for i in range(2):
        await client.post(
            f"/api/v1/projects/{pid}/alert-channels",
            json={"type": "email", "target": f"a{i}@example.com"},
            headers=auth_headers,
        )
    r = await client.get(f"/api/v1/projects/{pid}/alert-channels", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_patch_channel_toggles_enabled(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    cid = (
        await client.post(
            f"/api/v1/projects/{pid}/alert-channels",
            json={"type": "email", "target": "a@example.com"},
            headers=auth_headers,
        )
    ).json()["id"]
    r = await client.patch(
        f"/api/v1/projects/{pid}/alert-channels/{cid}",
        json={"enabled": False},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False


async def test_patch_channel_invalid_target_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    cid = (
        await client.post(
            f"/api/v1/projects/{pid}/alert-channels",
            json={"type": "email", "target": "a@example.com"},
            headers=auth_headers,
        )
    ).json()["id"]
    r = await client.patch(
        f"/api/v1/projects/{pid}/alert-channels/{cid}",
        json={"target": "not-an-email"},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_delete_channel(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    cid = (
        await client.post(
            f"/api/v1/projects/{pid}/alert-channels",
            json={"type": "email", "target": "a@example.com"},
            headers=auth_headers,
        )
    ).json()["id"]
    r = await client.delete(f"/api/v1/projects/{pid}/alert-channels/{cid}", headers=auth_headers)
    assert r.status_code == 204
    listed = await client.get(f"/api/v1/projects/{pid}/alert-channels", headers=auth_headers)
    assert listed.json() == []


async def test_cannot_create_channel_on_others_project_404(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    other = await _other_headers(client)
    r = await client.post(
        f"/api/v1/projects/{pid}/alert-channels",
        json={"type": "email", "target": "a@example.com"},
        headers=other,
    )
    assert r.status_code == 404


async def test_patch_unknown_channel_404(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.patch(
        f"/api/v1/projects/{pid}/alert-channels/{uuid.uuid4()}",
        json={"enabled": False},
        headers=auth_headers,
    )
    assert r.status_code == 404
