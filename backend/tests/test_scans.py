PROJECT = {"name": "S", "base_url": "https://example.com"}


async def _make_project(client, auth_headers):
    return (await client.post("/api/v1/projects", json=PROJECT, headers=auth_headers)).json()["id"]


async def test_trigger_scan_enqueues_and_returns_envelope(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(f"/api/v1/projects/{pid}/scans", headers=auth_headers)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["scan_id"]
    assert body["job_id"]


async def test_trigger_scan_requires_auth(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r = await client.post(f"/api/v1/projects/{pid}/scans")
    assert r.status_code == 401


async def test_get_scan_status(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    sid = (await client.post(f"/api/v1/projects/{pid}/scans", headers=auth_headers)).json()[
        "scan_id"
    ]
    r = await client.get(f"/api/v1/scans/{sid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "queued"


async def test_scan_history_lists_scans(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    await client.post(f"/api/v1/projects/{pid}/scans", headers=auth_headers)
    r = await client.get(f"/api/v1/projects/{pid}/scans", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 1


async def test_trigger_scan_is_idempotent_for_in_flight(client, auth_headers):
    pid = await _make_project(client, auth_headers)
    r1 = await client.post(f"/api/v1/projects/{pid}/scans", headers=auth_headers)
    assert r1.status_code == 202
    r2 = await client.post(f"/api/v1/projects/{pid}/scans", headers=auth_headers)
    assert r2.status_code == 200  # in-flight scan returned, not re-enqueued
    assert r2.json()["scan_id"] == r1.json()["scan_id"]
