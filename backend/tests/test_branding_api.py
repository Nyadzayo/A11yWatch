PROJECT = {"name": "My Site", "base_url": "https://example.com"}


async def _make_project(client, auth_headers):
    return (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]


async def _other_headers(client):
    creds = {"email": "other@example.com", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=creds)
    token = (await client.post("/api/v1/auth/login", json=creds)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_branding_defaults_when_absent(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.get(f"/api/v1/projects/{pid}/branding", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert body["company_name"] is None
    assert body["logo_url"] is None


async def test_put_branding_creates_then_get_returns_it(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    payload = {
        "company_name": "Acme",
        "logo_url": "https://acme.test/logo.png",
        "primary_color": "#112233",
        "report_footer": "Powered by Acme",
    }
    r = await client.put(f"/api/v1/projects/{pid}/branding", json=payload, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["company_name"] == "Acme"

    got = await client.get(f"/api/v1/projects/{pid}/branding", headers=auth_headers)
    assert got.json()["company_name"] == "Acme"
    assert got.json()["primary_color"] == "#112233"


async def test_put_branding_replaces_existing(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    await client.put(
        f"/api/v1/projects/{pid}/branding",
        json={"company_name": "Acme", "primary_color": "#112233"},
        headers=auth_headers,
    )
    # PUT is replace semantics: omitted fields are cleared.
    r = await client.put(
        f"/api/v1/projects/{pid}/branding",
        json={"company_name": "NewName"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["company_name"] == "NewName"
    assert body["primary_color"] is None


async def test_put_branding_invalid_logo_422(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.put(
        f"/api/v1/projects/{pid}/branding",
        json={"logo_url": "not-a-url"},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_branding_ownership_404(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    other = await _other_headers(client)
    r = await client.get(f"/api/v1/projects/{pid}/branding", headers=other)
    assert r.status_code == 404
