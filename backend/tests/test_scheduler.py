import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import fakeredis
from rq import Queue

from a11ywatch.core.config import settings
from a11ywatch.core.security import hash_password
from a11ywatch.models.tables import Project, Scan, User
from a11ywatch.scheduler import runner as scheduler_runner
from a11ywatch.scheduler.due import select_due_projects
from a11ywatch.scheduler.runner import run_due_scans_once


def _redis_and_queue():
    conn = fakeredis.FakeStrictRedis()
    return conn, Queue("scans", connection=conn)


async def _project(session, *, status="idle", last=None, freq=60):
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    session.add(user)
    await session.flush()
    project = Project(
        user_id=user.id,
        name="P",
        base_url="https://ex.com",
        status=status,
        scan_frequency_minutes=freq,
        last_scan_at=last,
    )
    session.add(project)
    await session.flush()
    return project


async def test_select_due_projects(db_session):
    now = datetime.now(UTC)
    never = await _project(db_session, last=None)
    stale = await _project(db_session, last=now - timedelta(hours=2), freq=60)
    recent = await _project(db_session, last=now - timedelta(minutes=5), freq=60)
    running = await _project(db_session, status="running", last=None)

    due_ids = {p.id for p in await select_due_projects(db_session, now)}
    assert never.id in due_ids
    assert stale.id in due_ids
    assert recent.id not in due_ids
    assert running.id not in due_ids


async def test_run_cycle_enqueues_only_due_idle_projects(db_session):
    now = datetime.now(UTC)
    due = await _project(db_session, last=None)
    not_due = await _project(db_session, last=now - timedelta(minutes=1), freq=60)
    conn, queue = _redis_and_queue()

    created = await run_due_scans_once(
        db_session,
        redis_conn=conn,
        queue=queue,
        now=now,
        stagger_seconds=0,
        site_timeout_seconds=600,
    )
    assert created == 1
    await db_session.refresh(due)
    await db_session.refresh(not_due)
    assert due.status == "queued"
    assert not_due.status == "idle"


async def test_cycle_pings_healthcheck_and_reaps_stuck_scans(db_session, monkeypatch):
    # Seed a project wedged on a long-running scan that has clearly exceeded its budget.
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    db_session.add(user)
    await db_session.flush()
    project = Project(user_id=user.id, name="P", base_url="https://ex.com", status="running")
    db_session.add(project)
    await db_session.flush()
    stuck = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="running",
        started_at=datetime.now(UTC) - timedelta(hours=3),
    )
    db_session.add(stuck)
    await db_session.flush()

    conn = fakeredis.FakeStrictRedis()
    scan_q = Queue("scans", connection=conn)
    alert_q = Queue("alerts", connection=conn)

    @asynccontextmanager
    async def fake_ws():
        yield db_session

    pings = []
    monkeypatch.setattr(scheduler_runner, "worker_session", fake_ws)
    monkeypatch.setattr(scheduler_runner, "get_redis", lambda: conn)
    monkeypatch.setattr(scheduler_runner, "get_scan_queue", lambda: scan_q)
    monkeypatch.setattr(scheduler_runner, "get_alert_queue", lambda: alert_q)
    monkeypatch.setattr(scheduler_runner, "ping_healthcheck", lambda url: pings.append(url))
    monkeypatch.setattr(settings, "healthcheck_ping_url", "https://hc.test/abc")

    await scheduler_runner._cycle_async()

    assert pings == ["https://hc.test/abc"]  # pinged once per cycle
    await db_session.refresh(stuck)
    assert stuck.status == "failed"  # stuck scan reaped
    assert alert_q.count == 1  # operator alerted


async def test_cycle_pings_healthcheck_even_when_db_work_raises(db_session, monkeypatch):
    # A transient DB blip must not suppress the dead-man's-switch ping (R9): the scheduler
    # process is alive and self-heals next cycle; a missed ping would falsely page the operator.
    conn = fakeredis.FakeStrictRedis()

    @asynccontextmanager
    async def fake_ws():
        yield db_session

    async def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    pings = []
    monkeypatch.setattr(scheduler_runner, "worker_session", fake_ws)
    monkeypatch.setattr(scheduler_runner, "get_redis", lambda: conn)
    monkeypatch.setattr(scheduler_runner, "get_scan_queue", lambda: Queue("scans", connection=conn))
    monkeypatch.setattr(
        scheduler_runner, "get_alert_queue", lambda: Queue("alerts", connection=conn)
    )
    monkeypatch.setattr(scheduler_runner, "run_due_scans_once", _boom)
    monkeypatch.setattr(scheduler_runner, "ping_healthcheck", lambda url: pings.append(url))
    monkeypatch.setattr(settings, "healthcheck_ping_url", "https://hc.test/abc")

    # Must not raise — the cycle logs the DB error and still pings.
    await scheduler_runner._cycle_async()

    assert pings == ["https://hc.test/abc"]
