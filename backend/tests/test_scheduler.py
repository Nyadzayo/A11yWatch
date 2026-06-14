import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
from rq import Queue

from a11ywatch.core.security import hash_password
from a11ywatch.models.tables import Project, User
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
