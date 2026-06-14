import asyncio
import logging
from datetime import UTC, datetime

from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.core.config import settings
from a11ywatch.core.logging import configure_logging
from a11ywatch.core.worker_db import worker_session
from a11ywatch.jobs.dispatch import LOCK_TTL_BUFFER_SECONDS, enqueue_scan
from a11ywatch.jobs.queue import get_alert_queue, get_redis, get_scan_queue
from a11ywatch.scheduler.due import select_due_projects
from a11ywatch.scheduler.healthcheck import ping_healthcheck
from a11ywatch.scheduler.reaper import reap_stuck_scans

log = logging.getLogger(__name__)


async def run_due_scans_once(
    session: AsyncSession,
    *,
    redis_conn,
    queue: Queue,
    now: datetime,
    stagger_seconds: int,
    site_timeout_seconds: int,
    max_retries: int = 0,
) -> int:
    """Enqueue (only) the due projects, staggered. Returns how many were newly enqueued."""
    due = await select_due_projects(session, now)
    created_count = 0
    for index, project in enumerate(due):
        _, created = await enqueue_scan(
            session,
            project,
            "scheduled",
            redis_conn=redis_conn,
            queue=queue,
            site_timeout_seconds=site_timeout_seconds,
            delay_seconds=index * stagger_seconds,
            max_retries=max_retries,
        )
        if created:
            created_count += 1
    return created_count


async def _cycle_async() -> None:
    redis_conn = get_redis()
    queue = get_scan_queue()
    alert_queue = get_alert_queue()
    now = datetime.now(UTC)
    stuck_after = settings.scan_site_timeout_seconds + LOCK_TTL_BUFFER_SECONDS
    count = reaped = 0
    try:
        async with worker_session() as session:
            count = await run_due_scans_once(
                session,
                redis_conn=redis_conn,
                queue=queue,
                now=now,
                stagger_seconds=settings.scheduler_stagger_seconds,
                site_timeout_seconds=settings.scan_site_timeout_seconds,
                max_retries=settings.scan_max_retries,
            )
            reaped = await reap_stuck_scans(
                session,
                now,
                older_than_seconds=stuck_after,
                redis_conn=redis_conn,
                alert_queue=alert_queue,
            )
    except Exception:
        # A transient DB/Redis blip degrades this cycle but the process is alive and recovers
        # next interval — surface it on its own channel, never via a missed dead-man ping.
        log.exception("scheduler cycle DB work failed", extra={"event": "scheduler_cycle_error"})
    finally:
        # The ping is a process-liveness signal (R9): it must fire even if the DB work failed,
        # or a transient blip would falsely page the operator as a dead scheduler.
        ping_healthcheck(settings.healthcheck_ping_url)
    log.info(
        "scheduler cycle complete",
        extra={"event": "scheduler_cycle", "enqueued": count, "reaped": reaped},
    )


def _cycle() -> None:
    asyncio.run(_cycle_async())


def main() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    configure_logging()
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _cycle, "interval", seconds=settings.scheduler_interval_seconds, id="due-scans"
    )
    log.info("A11yWatch scheduler started (interval=%ss)", settings.scheduler_interval_seconds)
    scheduler.start()


if __name__ == "__main__":
    main()
