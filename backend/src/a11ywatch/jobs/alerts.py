import asyncio
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from a11ywatch.alerts.delivery import deliver
from a11ywatch.alerts.messages import (
    AlertMessage,
    build_new_issues_message,
    build_operator_alert_message,
)
from a11ywatch.alerts.routing import channels_for_new_issues
from a11ywatch.core.config import settings
from a11ywatch.core.worker_db import worker_session
from a11ywatch.models.tables import AlertChannel, Project, Scan, Violation

log = logging.getLogger(__name__)

# Customer alerts (regressions) → the project's alert channels.
CUSTOMER_ALERT_JOB = "a11ywatch.jobs.alerts.send_customer_alert"
# Operator alerts (scan failures) → the operator, NEVER the customer.
OPERATOR_ALERT_JOB = "a11ywatch.jobs.alerts.send_operator_alert"


@dataclass(frozen=True)
class CustomerAlert:
    """A ready-to-deliver customer alert: which channels, and the message."""

    targets: list[tuple[str, str]]  # (channel_type, target)
    message: AlertMessage


# --------------------------------------------------------------------------- #
# Operator alerts (failures)
# --------------------------------------------------------------------------- #
def enqueue_operator_alert(queue: Queue, scan_id: str, error: str) -> None:
    """Enqueue an operator alert for a scan that failed for good."""
    queue.enqueue(OPERATOR_ALERT_JOB, scan_id, error)


def send_operator_alert(scan_id: str, error: str, *, deliver=deliver) -> None:
    """Consumer for operator alerts. Logs, then emails the operator if configured."""
    log.error("OPERATOR ALERT — scan %s failed: %s", scan_id, error)
    email = settings.operator_alert_email
    if email:
        deliver("email", email, build_operator_alert_message(scan_id, error))


# --------------------------------------------------------------------------- #
# Customer alerts (regressions / NEW issues)
# --------------------------------------------------------------------------- #
def enqueue_customer_alert(queue: Queue, scan_id: str, new_fingerprints: Iterable[str]) -> None:
    """Enqueue a customer regression alert for a scan with NEW issues."""
    queue.enqueue(CUSTOMER_ALERT_JOB, scan_id, list(new_fingerprints))


def enqueue_customer_alert_if_new(
    queue: Queue, scan_id: str, new_fingerprints: Iterable[str]
) -> bool:
    """Enqueue a customer alert only when there are NEW issues; silence otherwise.

    Returns True if an alert was enqueued.
    """
    fingerprints = sorted(new_fingerprints)
    if not fingerprints:
        return False
    enqueue_customer_alert(queue, scan_id, fingerprints)
    return True


async def collect_customer_alert(
    session: AsyncSession, scan_id: str, new_fingerprints: Iterable[str]
) -> CustomerAlert | None:
    """Build the customer alert for a scan, or None if there is nothing to send."""
    new = set(new_fingerprints)
    scan = await session.get(Scan, uuid.UUID(scan_id))
    if scan is None:
        return None
    project = await session.get(Project, scan.project_id)
    if project is None:
        return None

    channels = (
        await session.scalars(select(AlertChannel).where(AlertChannel.project_id == project.id))
    ).all()
    eligible = channels_for_new_issues(channels)
    if not eligible:
        return None

    sample = []
    if new:
        sample = (
            await session.scalars(
                select(Violation).where(
                    Violation.scan_id == scan.id, Violation.fingerprint.in_(new)
                )
            )
        ).all()

    message = build_new_issues_message(
        project_name=project.name,
        base_url=project.base_url,
        new_count=len(new),
        sample=sample,
    )
    return CustomerAlert(targets=[(c.type, c.target) for c in eligible], message=message)


def dispatch_customer_alert(alert: CustomerAlert, *, deliver=deliver) -> None:
    """Deliver the alert to each target independently (one bad channel won't block the rest)."""
    for channel_type, target in alert.targets:
        try:
            deliver(channel_type, target, alert.message)
        except Exception:
            log.warning("failed to deliver customer alert to %s:%s", channel_type, target)


def send_customer_alert(scan_id: str, new_fingerprints: list[str]) -> None:
    """RQ consumer: load the alert (DB) then deliver it (network) outside the session."""
    alert = asyncio.run(_collect(scan_id, new_fingerprints))
    if alert is not None:
        dispatch_customer_alert(alert)


async def _collect(scan_id: str, new_fingerprints: list[str]) -> CustomerAlert | None:
    async with worker_session() as session:
        return await collect_customer_alert(session, scan_id, new_fingerprints)
