import uuid
from datetime import UTC, datetime, timedelta

from a11ywatch.core.metrics import scan_metrics
from a11ywatch.models.tables import Scan


def _scan(**kw):
    s = Scan(project_id=uuid.uuid4(), trigger="on_demand", status="succeeded")
    s.id = uuid.uuid4()
    for key, value in kw.items():
        setattr(s, key, value)
    return s


def test_scan_metrics_computes_duration_and_fields():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    s = _scan(
        started_at=start,
        finished_at=start + timedelta(seconds=42),
        pages_scanned=5,
        total_issues=10,
        new_issues=3,
        resolved_issues=2,
    )
    m = scan_metrics(s)
    assert m["event"] == "scan_finished"
    assert m["scan_id"] == str(s.id)
    assert m["project_id"] == str(s.project_id)
    assert m["status"] == "succeeded"
    assert m["duration_seconds"] == 42.0
    assert m["pages_scanned"] == 5
    assert m["new_issues"] == 3
    assert m["resolved_issues"] == 2


def test_scan_metrics_duration_none_when_not_finished():
    s = _scan(started_at=datetime(2026, 1, 1, tzinfo=UTC), finished_at=None)
    assert scan_metrics(s)["duration_seconds"] is None
