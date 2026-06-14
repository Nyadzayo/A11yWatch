import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest
from rq import Queue

from a11ywatch.core.security import hash_password
from a11ywatch.jobs.dispatch import RUN_SCAN_JOB, enqueue_scan
from a11ywatch.models.tables import Project, Scan, User


def _redis_and_queue():
    conn = fakeredis.FakeStrictRedis()
    return conn, Queue("scans", connection=conn)


async def _project(session, status="idle"):
    user = User(email=f"{uuid.uuid4()}@ex.com", password_hash=hash_password("secret123"))
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="P", base_url="https://ex.com", status=status)
    session.add(project)
    await session.flush()
    return project


async def test_enqueue_creates_scan_and_job(db_session):
    project = await _project(db_session)
    conn, queue = _redis_and_queue()
    scan, created = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert created is True
    assert scan.status == "queued"
    assert scan.job_id
    assert project.status == "queued"
    assert queue.count == 1
    assert conn.get(f"scan:lock:{project.id}") is not None  # lock held until worker finishes


async def test_no_double_enqueue_when_running(db_session):
    project = await _project(db_session, status="running")
    existing = Scan(project_id=project.id, trigger="on_demand", status="running")
    db_session.add(existing)
    await db_session.flush()
    conn, queue = _redis_and_queue()
    scan, created = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert created is False
    assert queue.count == 0
    assert scan is not None
    assert scan.id == existing.id


async def test_lock_held_declines_even_if_status_idle(db_session):
    project = await _project(db_session)
    conn, queue = _redis_and_queue()
    conn.set(f"scan:lock:{project.id}", "1")  # another dispatch already holds the lock
    scan, created = await enqueue_scan(
        db_session, project, "scheduled", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert created is False
    assert queue.count == 0


async def test_on_demand_and_scheduled_enqueue_the_same_job(db_session):
    p1 = await _project(db_session)
    p2 = await _project(db_session)
    conn, queue = _redis_and_queue()
    s1, c1 = await enqueue_scan(
        db_session, p1, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    s2, c2 = await enqueue_scan(
        db_session, p2, "scheduled", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert c1 and c2
    assert queue.count == 2
    assert all(job.func_name == RUN_SCAN_JOB for job in queue.jobs)
    assert s1.trigger == "on_demand"
    assert s2.trigger == "scheduled"


async def test_lock_release_allows_a_new_scan(db_session):
    project = await _project(db_session)
    conn, queue = _redis_and_queue()
    s1, c1 = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert c1
    # simulate the worker finishing: status back to idle, lock released
    project.status = "idle"
    s1.status = "succeeded"
    conn.delete(f"scan:lock:{project.id}")
    await db_session.flush()
    s2, c2 = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert c2 is True
    assert s2.id != s1.id
    assert queue.count == 2


class _BoomQueue:
    def __init__(self, connection):
        self.connection = connection

    def enqueue(self, *args, **kwargs):
        raise RuntimeError("queue down")

    def enqueue_in(self, *args, **kwargs):
        raise RuntimeError("queue down")


async def test_stale_active_scan_is_ignored(db_session):
    project = await _project(db_session, status="running")
    old = Scan(
        project_id=project.id,
        trigger="scheduled",
        status="running",
        created_at=datetime.now(UTC) - timedelta(hours=3),
    )
    db_session.add(old)
    await db_session.flush()
    conn, queue = _redis_and_queue()
    scan, created = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert created is True
    assert scan.id != old.id


async def test_lock_released_when_enqueue_fails(db_session):
    project = await _project(db_session)
    conn, _ = _redis_and_queue()
    with pytest.raises(RuntimeError):
        await enqueue_scan(
            db_session,
            project,
            "on_demand",
            redis_conn=conn,
            queue=_BoomQueue(conn),
            site_timeout_seconds=600,
        )
    assert conn.get(f"scan:lock:{project.id}") is None  # released, not leaked


async def test_two_sequential_enqueues_only_one_created(db_session):
    project = await _project(db_session)
    conn, queue = _redis_and_queue()
    _, c1 = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    _, c2 = await enqueue_scan(
        db_session, project, "on_demand", redis_conn=conn, queue=queue, site_timeout_seconds=600
    )
    assert c1 is True
    assert c2 is False
    assert queue.count == 1


async def test_enqueue_configures_retry(db_session):
    project = await _project(db_session)
    conn, queue = _redis_and_queue()
    _, created = await enqueue_scan(
        db_session,
        project,
        "on_demand",
        redis_conn=conn,
        queue=queue,
        site_timeout_seconds=600,
        max_retries=2,
    )
    assert created is True
    assert queue.jobs[0].retries_left == 2
