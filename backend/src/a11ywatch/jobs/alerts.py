import logging

from rq import Queue

log = logging.getLogger(__name__)

# Operator alerts (scan failures) go to the operator, NOT the customer.
OPERATOR_ALERT_JOB = "a11ywatch.jobs.alerts.send_operator_alert"


def enqueue_operator_alert(queue: Queue, scan_id: str, error: str) -> None:
    """Enqueue an operator alert for a scan that failed for good."""
    queue.enqueue(OPERATOR_ALERT_JOB, scan_id, error)


def send_operator_alert(scan_id: str, error: str) -> None:
    """Consumer for operator alerts. Real delivery (email/etc.) lands in Phase 5."""
    log.error("OPERATOR ALERT — scan %s failed: %s", scan_id, error)
