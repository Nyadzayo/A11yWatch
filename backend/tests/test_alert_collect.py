import uuid
from datetime import UTC, datetime

from a11ywatch.core.security import hash_password
from a11ywatch.jobs.alerts import collect_customer_alert
from a11ywatch.models.tables import AlertChannel, Project, Scan, User, Violation


async def _seed(session):
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="Acme", base_url="https://acme.test")
    session.add(project)
    await session.flush()
    scan = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="succeeded",
        finished_at=datetime.now(UTC),
        new_issues=2,
    )
    session.add(scan)
    await session.flush()
    for fp in ("new1", "new2"):
        session.add(
            Violation(
                scan_id=scan.id,
                project_id=project.id,
                page_url="https://acme.test/x",
                rule_id="image-alt",
                fingerprint=fp,
            )
        )
    await session.flush()
    return project, scan


async def test_collect_targets_only_enabled_subscribed_channels(db_session):
    project, scan = await _seed(db_session)
    db_session.add_all(
        [
            AlertChannel(
                project_id=project.id,
                type="email",
                target="keep@acme.test",
                enabled=True,
                events=["new_issues"],
            ),
            AlertChannel(
                project_id=project.id,
                type="email",
                target="off@acme.test",
                enabled=False,
                events=["new_issues"],
            ),
            AlertChannel(
                project_id=project.id,
                type="email",
                target="other@acme.test",
                enabled=True,
                events=["weekly_digest"],
            ),
        ]
    )
    await db_session.flush()

    alert = await collect_customer_alert(db_session, str(scan.id), {"new1", "new2"})

    assert alert is not None
    assert {t for _, t in alert.targets} == {"keep@acme.test"}
    assert "2" in alert.message.subject
    assert "image-alt" in alert.message.body


async def test_collect_returns_none_when_no_eligible_channels(db_session):
    project, scan = await _seed(db_session)
    db_session.add(
        AlertChannel(
            project_id=project.id,
            type="email",
            target="off@acme.test",
            enabled=False,
            events=["new_issues"],
        )
    )
    await db_session.flush()

    alert = await collect_customer_alert(db_session, str(scan.id), {"new1", "new2"})
    assert alert is None


async def test_collect_returns_none_for_unknown_scan(db_session):
    alert = await collect_customer_alert(db_session, str(uuid.uuid4()), {"new1"})
    assert alert is None
