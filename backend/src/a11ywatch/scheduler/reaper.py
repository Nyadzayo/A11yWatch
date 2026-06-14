import logging
from datetime import datetime, timedelta

from rq import Queue
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.jobs.alerts import enqueue_operator_alert
from a11ywatch.jobs.dispatch import lock_key
from a11ywatch.models.tables import Project, Scan

log = logging.getLogger(__name__)


async def select_stuck_scans(
    session: AsyncSession, now: datetime, *, older_than_seconds: int
) -> list[Scan]:
    """Running scans whose start is older than the budget — i.e. a worker died mid-scan."""
    cutoff = now - timedelta(seconds=older_than_seconds)
    return list(
        await session.scalars(
            select(Scan).where(
                Scan.status == "running",
                func.coalesce(Scan.started_at, Scan.created_at) < cutoff,
            )
        )
    )


async def reap_stuck_scans(
    session: AsyncSession,
    now: datetime,
    *,
    older_than_seconds: int,
    redis_conn,
    alert_queue: Queue,
) -> int:
    """Fail stuck scans, unwedge their projects, release locks, and alert the operator.

    Complements the dispatch staleness gate: that stops a crashed scan from blocking *new*
    enqueues; this actively cleans the abandoned row so the project resumes scheduling.
    """
    stuck = await select_stuck_scans(session, now, older_than_seconds=older_than_seconds)
    reaped: list[Scan] = []
    for scan in stuck:
        # Compare-and-swap: only reap a scan that is *still* running. A worker may have
        # finished it between the select above and this write — don't clobber that result.
        result = await session.execute(
            update(Scan)
            .where(Scan.id == scan.id, Scan.status == "running")
            .values(
                status="failed",
                error="stuck: scan exceeded its time budget without completing",
                finished_at=now,
            )
        )
        if result.rowcount == 0:
            continue
        project = await session.get(Project, scan.project_id)
        if project is not None and project.status == "running":
            # Unwedge only if the project is still tied to this scan, not a newer one.
            project.status = "idle"
            project.last_scan_at = now
            project.last_scan_id = scan.id
        reaped.append(scan)

    await session.commit()

    # Irreversible side effects only AFTER the durable status flip commits: the flip is the
    # dedupe key, so a failed commit must leave zero locks released and zero alerts sent.
    for scan in reaped:
        try:
            redis_conn.delete(lock_key(scan.project_id))
        except Exception:
            log.warning("failed to release lock for reaped project %s", scan.project_id)
        try:
            enqueue_operator_alert(alert_queue, str(scan.id), "stuck running scan reaped")
        except Exception:
            log.warning("failed to enqueue operator alert for reaped scan %s", scan.id)

    if reaped:
        log.warning(
            "reaped stuck scans", extra={"event": "stuck_scans_reaped", "count": len(reaped)}
        )
    return len(reaped)
