import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest
from rq import Queue

from a11ywatch.core.security import hash_password
from a11ywatch.jobs.alerts import OPERATOR_ALERT_JOB
from a11ywatch.jobs.dispatch import lock_key
from a11ywatch.models.tables import Project, Scan, User
from a11ywatch.scheduler import reaper as reaper_mod
from a11ywatch.scheduler.reaper import reap_stuck_scans, select_stuck_scans


async def _project_with_running_scan(session, *, started_delta):
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="P", base_url="https://ex.com", status="running")
    session.add(project)
    await session.flush()
    scan = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="running",
        started_at=datetime.now(UTC) - started_delta,
    )
    session.add(scan)
    await session.flush()
    return project, scan


async def test_select_stuck_scans_only_returns_old_running(db_session):
    now = datetime.now(UTC)
    _, old = await _project_with_running_scan(db_session, started_delta=timedelta(hours=2))
    _, fresh = await _project_with_running_scan(db_session, started_delta=timedelta(seconds=5))
    stuck = await select_stuck_scans(db_session, now, older_than_seconds=600)
    ids = {s.id for s in stuck}
    assert old.id in ids
    assert fresh.id not in ids


async def test_reap_marks_failed_unwedges_and_alerts(db_session):
    now = datetime.now(UTC)
    project, scan = await _project_with_running_scan(db_session, started_delta=timedelta(hours=2))
    conn = fakeredis.FakeStrictRedis()
    conn.set(lock_key(project.id), "1")
    alert_q = Queue("alerts", connection=conn)

    reaped = await reap_stuck_scans(
        db_session, now, older_than_seconds=600, redis_conn=conn, alert_queue=alert_q
    )

    assert reaped == 1
    await db_session.refresh(scan)
    await db_session.refresh(project)
    assert scan.status == "failed"
    assert scan.finished_at is not None
    assert project.status == "idle"  # unwedged
    assert conn.get(lock_key(project.id)) is None  # lock released
    assert alert_q.count == 1
    assert alert_q.jobs[0].func_name == OPERATOR_ALERT_JOB


async def test_reap_does_not_overwrite_a_scan_that_already_succeeded(db_session, monkeypatch):
    # Race: the scan was selected as running, but a worker finished it before the reaper's
    # write lands. The compare-and-swap must no-op rather than clobber the success.
    now = datetime.now(UTC)
    _, scan = await _project_with_running_scan(db_session, started_delta=timedelta(hours=2))
    scan.status = "succeeded"
    await db_session.flush()

    async def _stale_select(session, when, *, older_than_seconds):
        return [scan]

    monkeypatch.setattr(reaper_mod, "select_stuck_scans", _stale_select)
    conn = fakeredis.FakeStrictRedis()
    alert_q = Queue("alerts", connection=conn)

    reaped = await reap_stuck_scans(
        db_session, now, older_than_seconds=600, redis_conn=conn, alert_queue=alert_q
    )

    assert reaped == 0
    await db_session.refresh(scan)
    assert scan.status == "succeeded"  # CAS no-op, not overwritten to failed
    assert alert_q.count == 0


async def test_reap_holds_side_effects_until_commit_succeeds(db_session, monkeypatch):
    # Lock release + operator alert are irreversible; they must not happen before the
    # durable status flip commits, or a failed commit double-alerts on the next cycle.
    now = datetime.now(UTC)
    project, scan = await _project_with_running_scan(db_session, started_delta=timedelta(hours=2))
    conn = fakeredis.FakeStrictRedis()
    conn.set(lock_key(project.id), "1")
    alert_q = Queue("alerts", connection=conn)

    async def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db_session, "commit", _boom)

    with pytest.raises(RuntimeError):
        await reap_stuck_scans(
            db_session, now, older_than_seconds=600, redis_conn=conn, alert_queue=alert_q
        )

    assert conn.get(lock_key(project.id)) is not None  # lock NOT released before commit
    assert alert_q.count == 0  # no operator alert before commit


async def test_reap_ignores_fresh_running_scans(db_session):
    now = datetime.now(UTC)
    _, scan = await _project_with_running_scan(db_session, started_delta=timedelta(seconds=5))
    conn = fakeredis.FakeStrictRedis()
    alert_q = Queue("alerts", connection=conn)

    reaped = await reap_stuck_scans(
        db_session, now, older_than_seconds=600, redis_conn=conn, alert_queue=alert_q
    )

    assert reaped == 0
    await db_session.refresh(scan)
    assert scan.status == "running"
    assert alert_q.count == 0
