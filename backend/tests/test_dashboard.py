import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from a11ywatch.core.security import hash_password
from a11ywatch.models.tables import Project, Scan, User, Violation


async def _register(client, email="dash@example.com", password="secret123"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def _login(client, email="dash@example.com", password="secret123"):
    return await client.post("/login", data={"email": email, "password": password})


async def test_dashboard_redirects_to_login_when_logged_out(client):
    r = await client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


async def test_login_page_renders(client):
    r = await client.get("/login")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "sign in" in r.text.lower()


async def test_login_sets_cookie_and_redirects(client):
    await _register(client)
    r = await _login(client)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert "a11ywatch_session=" in r.headers.get("set-cookie", "")


async def test_dashboard_after_login_returns_200(client):
    await _register(client)
    await _login(client)
    r = await client.get("/")
    assert r.status_code == 200
    assert "dash@example.com" in r.text


async def test_register_from_login_creates_account(client, db_session):
    r = await client.post(
        "/login",
        data={"email": "new@example.com", "password": "secret123", "create_account": "on"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    user = await db_session.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None


async def test_dashboard_lists_only_owners_projects(client, db_session):
    await _register(client)
    await _login(client)
    await client.post("/projects", data={"name": "Mine", "base_url": "https://mine.example.com"})
    other = User(email="other@example.com", password_hash=hash_password("secret123"))
    db_session.add(other)
    await db_session.flush()
    db_session.add(Project(user_id=other.id, name="Theirs", base_url="https://theirs.example.com"))
    await db_session.commit()

    r = await client.get("/")
    assert "Mine" in r.text
    assert "Theirs" not in r.text


async def test_scan_now_enqueues_and_redirects(client, db_session):
    await _register(client)
    await _login(client)
    user = await db_session.scalar(select(User).where(User.email == "dash@example.com"))
    project = Project(user_id=user.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.commit()

    r = await client.post(f"/projects/{project.id}/scan")
    assert r.status_code == 303
    assert r.headers["location"].startswith("/scans/")
    count = await db_session.scalar(
        select(func.count()).select_from(Scan).where(Scan.project_id == project.id)
    )
    assert count == 1


async def test_scan_page_renders_issues_grouped_by_impact(client, db_session):
    await _register(client)
    await _login(client)
    user = await db_session.scalar(select(User).where(User.email == "dash@example.com"))
    project = Project(user_id=user.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.flush()
    scan = Scan(
        project_id=project.id,
        trigger="on_demand",
        status="succeeded",
        finished_at=datetime.now(UTC),
        total_issues=2,
    )
    db_session.add(scan)
    await db_session.flush()
    for fp, rule, impact in [("fp1", "image-alt", "critical"), ("fp2", "label", "serious")]:
        db_session.add(
            Violation(
                scan_id=scan.id,
                project_id=project.id,
                page_url="https://ex.com/a",
                rule_id=rule,
                impact=impact,
                fingerprint=fp,
            )
        )
    await db_session.commit()

    r = await client.get(f"/scans/{scan.id}")
    assert r.status_code == 200
    assert "image-alt" in r.text
    assert "label" in r.text
    assert "critical" in r.text.lower()


async def test_scan_page_404s_for_non_owner(client, db_session):
    await _register(client)
    await _login(client)
    other = User(email="other@example.com", password_hash=hash_password("secret123"))
    db_session.add(other)
    await db_session.flush()
    project = Project(user_id=other.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.flush()
    scan = Scan(project_id=project.id, trigger="on_demand", status="succeeded")
    db_session.add(scan)
    await db_session.commit()

    r = await client.get(f"/scans/{scan.id}")
    assert r.status_code in (303, 404)  # must not render another user's scan


async def test_logout_clears_cookie(client):
    await _register(client)
    await _login(client)
    r = await client.post("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert "a11ywatch_session=" in r.headers.get("set-cookie", "")


async def test_no_compliance_in_rendered_pages(client, db_session):
    await _register(client)
    await _login(client)
    await client.post("/projects", data={"name": "Mine", "base_url": "https://mine.example.com"})
    blob = (await client.get("/login")).text + (await client.get("/")).text
    assert "compliance" not in blob.lower()


# --- security regressions from the dashboard review -------------------------- #
async def test_register_short_password_does_not_leak_account_existence(client):
    # The 400-vs-401 oracle: short password must yield the SAME status whether or not
    # the email already has an account.
    await _register(client, email="exists@example.com")
    r_exists = await client.post(
        "/login",
        data={"email": "exists@example.com", "password": "short", "create_account": "on"},
    )
    r_new = await client.post(
        "/login",
        data={"email": "brandnew@example.com", "password": "short", "create_account": "on"},
    )
    assert r_exists.status_code == r_new.status_code


async def test_login_cookie_flags(client):
    await _register(client)
    sc = (await _login(client)).headers.get("set-cookie", "").lower()
    assert "httponly" in sc
    assert "samesite=lax" in sc
    assert "secure" not in sc  # dev env: cookie works over http


async def test_login_rejects_cross_site_origin(client):
    await _register(client)
    r = await client.post(
        "/login",
        data={"email": "dash@example.com", "password": "secret123"},
        headers={"origin": "http://evil.example.com"},
    )
    assert r.status_code == 403


async def test_login_allows_same_origin(client):
    await _register(client)
    r = await client.post(
        "/login",
        data={"email": "dash@example.com", "password": "secret123"},
        headers={"origin": "http://test"},
    )
    assert r.status_code == 303


async def test_project_page_redirects_for_non_owner(client, db_session):
    await _register(client)
    await _login(client)
    other = User(email="other@example.com", password_hash=hash_password("secret123"))
    db_session.add(other)
    await db_session.flush()
    project = Project(user_id=other.id, name="SecretProj", base_url="https://secret.example.com")
    db_session.add(project)
    await db_session.commit()

    r = await client.get(f"/projects/{project.id}")
    assert r.status_code == 303
    assert r.headers["location"] == "/"


async def test_scan_now_rejects_non_owner(client, db_session):
    await _register(client)
    await _login(client)
    other = User(email="other@example.com", password_hash=hash_password("secret123"))
    db_session.add(other)
    await db_session.flush()
    project = Project(user_id=other.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.commit()

    r = await client.post(f"/projects/{project.id}/scan")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    count = await db_session.scalar(
        select(func.count()).select_from(Scan).where(Scan.project_id == project.id)
    )
    assert count == 0  # no scan created for someone else's project


async def test_dashboard_routes_require_login(client):
    uid = str(uuid.uuid4())
    r1 = await client.post("/projects", data={"name": "x", "base_url": "https://x.example.com"})
    r2 = await client.get(f"/projects/{uid}")
    r3 = await client.post(f"/projects/{uid}/scan")
    r4 = await client.get(f"/scans/{uid}")
    for r in (r1, r2, r3, r4):
        assert r.status_code == 303
        assert r.headers["location"] == "/login"


async def test_scan_page_groups_in_severity_order(client, db_session):
    await _register(client)
    await _login(client)
    user = await db_session.scalar(select(User).where(User.email == "dash@example.com"))
    project = Project(user_id=user.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.flush()
    scan = Scan(project_id=project.id, trigger="on_demand", status="succeeded", total_issues=2)
    db_session.add(scan)
    await db_session.flush()
    db_session.add_all(
        [
            Violation(
                scan_id=scan.id,
                project_id=project.id,
                page_url="u",
                rule_id="r1",
                impact="minor",
                fingerprint="f1",
            ),
            Violation(
                scan_id=scan.id,
                project_id=project.id,
                page_url="u",
                rule_id="r2",
                impact="critical",
                fingerprint="f2",
            ),
        ]
    )
    await db_session.commit()

    body = (await client.get(f"/scans/{scan.id}")).text
    assert body.index("critical") < body.index("minor")  # severest first


async def test_scan_page_escapes_violation_fields_and_guards_help_url(client, db_session):
    await _register(client)
    await _login(client)
    user = await db_session.scalar(select(User).where(User.email == "dash@example.com"))
    project = Project(user_id=user.id, name="P", base_url="https://ex.com")
    db_session.add(project)
    await db_session.flush()
    scan = Scan(project_id=project.id, trigger="on_demand", status="succeeded", total_issues=1)
    db_session.add(scan)
    await db_session.flush()
    db_session.add(
        Violation(
            scan_id=scan.id,
            project_id=project.id,
            page_url="https://ex.com/a",
            rule_id="image-alt",
            impact="serious",
            target="<script>alert(1)</script>",
            help_url="javascript:alert(1)",
            fingerprint="f1",
        )
    )
    await db_session.commit()

    body = (await client.get(f"/scans/{scan.id}")).text
    assert "<script>alert(1)</script>" not in body  # autoescaped
    assert "&lt;script&gt;" in body
    assert 'href="javascript:alert(1)"' not in body  # scheme guard
