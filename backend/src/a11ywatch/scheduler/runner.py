import asyncio
import logging
from datetime import UTC, datetime

from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.core.config import settings
from a11ywatch.core.worker_db import worker_session
from a11ywatch.jobs.dispatch import enqueue_scan
from a11ywatch.jobs.queue import get_redis, get_scan_queue
from a11ywatch.scheduler.due import select_due_projects

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
    async with worker_session() as session:
        count = await run_due_scans_once(
            session,
            redis_conn=redis_conn,
            queue=queue,
            now=datetime.now(UTC),
            stagger_seconds=settings.scheduler_stagger_seconds,
            site_timeout_seconds=settings.scan_site_timeout_seconds,
            max_retries=settings.scan_max_retries,
        )
    log.info("scheduler cycle: enqueued %d scan(s)", count)


def _cycle() -> None:
    asyncio.run(_cycle_async())


def main() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    logging.basicConfig(level=logging.INFO)
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _cycle, "interval", seconds=settings.scheduler_interval_seconds, id="due-scans"
    )
    log.info("A11yWatch scheduler started (interval=%ss)", settings.scheduler_interval_seconds)
    scheduler.start()


if __name__ == "__main__":
    main()
