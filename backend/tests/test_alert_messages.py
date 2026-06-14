from types import SimpleNamespace

from a11ywatch.alerts.messages import (
    AlertMessage,
    build_new_issues_message,
    build_operator_alert_message,
)


def _v(rule_id, page_url):
    return SimpleNamespace(rule_id=rule_id, page_url=page_url)


def test_new_issues_message_reports_count_and_samples():
    msg = build_new_issues_message(
        project_name="Acme",
        base_url="https://acme.test",
        new_count=2,
        sample=[_v("image-alt", "https://acme.test/a"), _v("label", "https://acme.test/b")],
    )
    assert isinstance(msg, AlertMessage)
    assert "2" in msg.subject
    assert "Acme" in msg.subject
    assert "image-alt" in msg.body
    assert "label" in msg.body
    assert "https://acme.test/a" in msg.body


def test_new_issues_message_uses_approved_vocabulary_not_compliance():
    msg = build_new_issues_message(
        project_name="Acme", base_url="https://acme.test", new_count=1, sample=[_v("r", "u")]
    )
    blob = (msg.subject + "\n" + msg.body).lower()
    assert "compliance" not in blob
    assert "regression" in blob or "monitoring" in blob


def test_operator_alert_message_includes_scan_and_error():
    msg = build_operator_alert_message("scan-123", "TimeoutError: boom")
    assert "scan-123" in msg.body
    assert "boom" in msg.body
    assert "compliance" not in (msg.subject + msg.body).lower()
