from datetime import UTC, datetime, timedelta

from rq import Queue, Retry
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from a11ywatch.models.tables import Project, Scan

# Enqueued by string so the API/scheduler never import Playwright (worker resolves it).
RUN_SCAN_JOB = "a11ywatch.jobs.scan.run_scan_job"

_ACTIVE = ("queued", "running")
LOCK_TTL_BUFFER_SECONDS = 60


def lock_key(project_id) -> str:
    return f"scan:lock:{project_id}"


async def _in_flight_scan(session: AsyncSession, project_id, *, cutoff: datetime) -> Scan | None:
    """The latest queued/running scan that is still within its lock window.

    Active scans older than ``cutoff`` are treated as abandoned (worker crash) so a
    stuck row can't wedge the project forever — the DB gate and the Redis TTL agree.
    """
    return await session.scalar(
        select(Scan)
        .where(
            Scan.project_id == project_id,
            Scan.status.in_(_ACTIVE),
            # started_at advances on each retry attempt; created_at for not-yet-started scans.
            func.coalesce(Scan.started_at, Scan.created_at) >= cutoff,
        )
        .order_by(Scan.created_at.desc())
        .limit(1)
    )


async def enqueue_scan(
    session: AsyncSession,
    project: Project,
    trigger: str,
    *,
    redis_conn,
    queue: Queue,
    site_timeout_seconds: int,
    delay_seconds: int = 0,
    max_retries: int = 0,
) -> tuple[Scan | None, bool]:
    """Lock-before-check enqueue shared by on-demand (API) and scheduled (scheduler).

    Returns ``(scan, created)``:
    - ``created=True``  — a new queued scan was created and the shared job enqueued.
    - ``created=False`` — a scan is already in flight (returned if known); nothing enqueued.

    The per-project Redis lock is held until the worker finishes; its TTL covers the
    staggered wait plus the run budget and is the backstop if the worker dies.
    """
    lock_ttl = site_timeout_seconds + delay_seconds + LOCK_TTL_BUFFER_SECONDS
    cutoff = datetime.now(UTC) - timedelta(seconds=site_timeout_seconds + LOCK_TTL_BUFFER_SECONDS)

    # 1. DB gate: a non-stale queued/running scan already covers this project.
    in_flight = await _in_flight_scan(session, project.id, cutoff=cutoff)
    if in_flight is not None:
        return in_flight, False

    # 2. Final gate: atomically acquire the per-project lock (off the event loop).
    acquired = await run_in_threadpool(
        lambda: redis_conn.set(lock_key(project.id), "1", nx=True, ex=lock_ttl)
    )
    if not acquired:
        return await _in_flight_scan(session, project.id, cutoff=cutoff), False

    # 3. Create the queued scan and enqueue the one shared job. Release the lock on any
    #    failure so a transient DB/queue error can't leave the project locked until TTL.
    try:
        scan = Scan(project_id=project.id, trigger=trigger, status="queued")
        session.add(scan)
        await session.flush()
        project.status = "queued"
        retry = Retry(max=max_retries, interval=[4, 8]) if max_retries > 0 else None
        if delay_seconds > 0:
            job = await run_in_threadpool(
                lambda: queue.enqueue_in(
                    timedelta(seconds=delay_seconds),
                    RUN_SCAN_JOB,
                    str(scan.id),
                    job_timeout=site_timeout_seconds,
                    retry=retry,
                )
            )
        else:
            job = await run_in_threadpool(
                lambda: queue.enqueue(
                    RUN_SCAN_JOB, str(scan.id), job_timeout=site_timeout_seconds, retry=retry
                )
            )
        scan.job_id = job.id
        await session.commit()
    except BaseException:
        await session.rollback()
        await run_in_threadpool(lambda: redis_conn.delete(lock_key(project.id)))
        raise
    return scan, True
