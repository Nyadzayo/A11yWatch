import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import fakeredis
from rq import Queue

from a11ywatch.core.security import hash_password
from a11ywatch.jobs import scan as scan_job
from a11ywatch.jobs.alerts import CUSTOMER_ALERT_JOB
from a11ywatch.models.tables import Project, Scan, User, Violation
from a11ywatch.scanning.types import ScanResult, ScanViolation


def _sv(fingerprint):
    return ScanViolation(
        page_url="https://acme.test/x",
        rule_id="image-alt",
        impact="serious",
        help=None,
        help_url=None,
        target="img",
        html_snippet=None,
        fingerprint=fingerprint,
    )


async def _running_scan(session):
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="Acme", base_url="https://acme.test", status="running")
    session.add(project)
    await session.flush()
    scan = Scan(project_id=project.id, trigger="on_demand", status="running")
    session.add(scan)
    await session.flush()
    return project, scan


def _wire(monkeypatch, db_session):
    conn = fakeredis.FakeStrictRedis()
    queue = Queue("alerts", connection=conn)

    @asynccontextmanager
    async def fake_ws():
        yield db_session

    monkeypatch.setattr(scan_job, "worker_session", fake_ws)
    monkeypatch.setattr(scan_job, "get_alert_queue", lambda: queue)
    monkeypatch.setattr(scan_job, "get_redis", lambda: conn)
    return queue


async def test_finish_enqueues_customer_alert_on_new_issues(db_session, monkeypatch):
    _, scan = await _running_scan(db_session)
    queue = _wire(monkeypatch, db_session)

    await scan_job._finish(
        str(scan.id), ScanResult(pages_scanned=1, violations=[_sv("a"), _sv("b")])
    )

    assert queue.count == 1
    job = queue.jobs[0]
    assert job.func_name == CUSTOMER_ALERT_JOB
    assert job.args == (str(scan.id), ["a", "b"])  # NEW fingerprints, sorted


async def test_finish_skips_when_scan_already_reaped(db_session, monkeypatch):
    # The reaper flipped the scan to failed; a late worker must not un-reap or alert.
    _, scan = await _running_scan(db_session)
    scan.status = "failed"
    await db_session.flush()
    queue = _wire(monkeypatch, db_session)

    await scan_job._finish(str(scan.id), ScanResult(pages_scanned=1, violations=[_sv("a")]))

    await db_session.refresh(scan)
    assert scan.status == "failed"  # not un-reaped to succeeded
    assert queue.count == 0  # no customer alert for a reaped scan


async def test_fail_returns_true_and_finalizes_running_scan(db_session, monkeypatch):
    _, scan = await _running_scan(db_session)
    _wire(monkeypatch, db_session)

    result = await scan_job._fail(str(scan.id), "boom")

    assert result is True
    await db_session.refresh(scan)
    assert scan.status == "failed"


async def test_fail_returns_false_when_already_reaped(db_session, monkeypatch):
    _, scan = await _running_scan(db_session)
    scan.status = "failed"
    await db_session.flush()
    _wire(monkeypatch, db_session)

    result = await scan_job._fail(str(scan.id), "boom")

    assert result is False


async def test_finish_is_silent_when_no_new_issues(db_session, monkeypatch):
    project, scan = await _running_scan(db_session)
    prev = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="succeeded",
        finished_at=datetime.now(UTC),
    )
    db_session.add(prev)
    await db_session.flush()
    for fp in ("a", "b"):
        db_session.add(
            Violation(
                scan_id=prev.id, project_id=project.id, page_url="u", rule_id="r", fingerprint=fp
            )
        )
    await db_session.flush()
    queue = _wire(monkeypatch, db_session)

    # Same fingerprints as the previous successful scan -> nothing NEW -> silence.
    await scan_job._finish(
        str(scan.id), ScanResult(pages_scanned=1, violations=[_sv("a"), _sv("b")])
    )

    assert queue.count == 0
