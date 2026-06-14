from a11ywatch.models.tables import Scan


def scan_metrics(scan: Scan) -> dict:
    """Structured metrics for a finished scan — log as ``extra`` for observability."""
    duration = None
    if scan.started_at is not None and scan.finished_at is not None:
        duration = (scan.finished_at - scan.started_at).total_seconds()
    return {
        "event": "scan_finished",
        "scan_id": str(scan.id),
        "project_id": str(scan.project_id),
        "status": scan.status,
        "trigger": scan.trigger,
        "duration_seconds": duration,
        "pages_scanned": scan.pages_scanned,
        "total_issues": scan.total_issues,
        "new_issues": scan.new_issues,
        "resolved_issues": scan.resolved_issues,
    }
