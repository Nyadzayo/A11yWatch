import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from a11ywatch.models.tables import Project, Scan, User, Violation


async def _user(db_session, email):
    return await db_session.scalar(select(User).where(User.email == email))


async def _scan_with_violations(db_session, user, specs):
    project = Project(user_id=user.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.flush()
    scan = Scan(
        project_id=project.id,
        trigger="on_demand",
        status="succeeded",
        finished_at=datetime.now(UTC),
    )
    db_session.add(scan)
    await db_session.flush()
    for i, (rule, impact) in enumerate(specs):
        db_session.add(
            Violation(
                scan_id=scan.id,
                project_id=project.id,
                page_url="https://ex.com/a",
                rule_id=rule,
                impact=impact,
                help=f"{rule} help",
                help_url=f"https://dequeuniversity.com/rules/axe/{rule}",
                target="img",
                fingerprint=f"fp{i}",
            )
        )
    await db_session.commit()
    return scan


async def test_list_violations_for_owned_scan(client, auth_headers, db_session):
    user = await _user(db_session, "owner@example.com")
    scan = await _scan_with_violations(
        db_session, user, [("image-alt", "serious"), ("label", "critical")]
    )
    r = await client.get(f"/api/v1/scans/{scan.id}/violations", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {v["rule_id"] for v in body["items"]} == {"image-alt", "label"}
    row = next(v for v in body["items"] if v["rule_id"] == "image-alt")
    assert row["impact"] == "serious"
    assert row["help_url"].endswith("image-alt")
    assert row["page_url"] == "https://ex.com/a"


async def test_list_violations_requires_auth(client, auth_headers, db_session):
    user = await _user(db_session, "owner@example.com")
    scan = await _scan_with_violations(db_session, user, [("image-alt", "serious")])
    r = await client.get(f"/api/v1/scans/{scan.id}/violations")
    assert r.status_code == 401


async def test_list_violations_404_for_non_owner(client, auth_headers, db_session):
    # A scan owned by a different user must not be readable (no existence leak).
    other = User(email="stranger@example.com", password_hash="x")
    db_session.add(other)
    await db_session.flush()
    scan = await _scan_with_violations(db_session, other, [("image-alt", "serious")])
    r = await client.get(f"/api/v1/scans/{scan.id}/violations", headers=auth_headers)
    assert r.status_code == 404


async def test_list_violations_404_for_unknown_scan(client, auth_headers):
    r = await client.get(f"/api/v1/scans/{uuid.uuid4()}/violations", headers=auth_headers)
    assert r.status_code == 404


async def test_list_violations_pagination(client, auth_headers, db_session):
    user = await _user(db_session, "owner@example.com")
    scan = await _scan_with_violations(db_session, user, [(f"rule-{i}", "minor") for i in range(5)])
    r = await client.get(
        f"/api/v1/scans/{scan.id}/violations?limit=2&offset=0", headers=auth_headers
    )
    body = r.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert len(body["items"]) == 2


async def test_list_violations_impact_filter(client, auth_headers, db_session):
    user = await _user(db_session, "owner@example.com")
    scan = await _scan_with_violations(
        db_session, user, [("image-alt", "serious"), ("label", "critical"), ("region", "minor")]
    )
    r = await client.get(
        f"/api/v1/scans/{scan.id}/violations?impact=critical", headers=auth_headers
    )
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["rule_id"] == "label"


async def test_list_violations_empty_scan(client, auth_headers, db_session):
    user = await _user(db_session, "owner@example.com")
    scan = await _scan_with_violations(db_session, user, [])
    r = await client.get(f"/api/v1/scans/{scan.id}/violations", headers=auth_headers)
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []
