import fakeredis
from rq import Queue

from a11ywatch.alerts.messages import AlertMessage
from a11ywatch.core.config import settings
from a11ywatch.jobs import alerts as alerts_mod
from a11ywatch.jobs.alerts import (
    CUSTOMER_ALERT_JOB,
    OPERATOR_ALERT_JOB,
    CustomerAlert,
    dispatch_customer_alert,
    enqueue_customer_alert,
    enqueue_customer_alert_if_new,
    enqueue_operator_alert,
)


def test_enqueue_operator_alert_goes_to_the_alerts_queue():
    conn = fakeredis.FakeStrictRedis()
    alerts = Queue("alerts", connection=conn)
    enqueue_operator_alert(alerts, "scan-123", "boom")
    assert alerts.count == 1
    job = alerts.jobs[0]
    assert job.func_name == OPERATOR_ALERT_JOB
    assert job.args == ("scan-123", "boom")


def test_enqueue_customer_alert_goes_to_the_alerts_queue():
    conn = fakeredis.FakeStrictRedis()
    alerts = Queue("alerts", connection=conn)
    enqueue_customer_alert(alerts, "scan-9", ["fp1", "fp2"])
    job = alerts.jobs[0]
    assert job.func_name == CUSTOMER_ALERT_JOB
    assert job.args == ("scan-9", ["fp1", "fp2"])


def test_customer_alert_enqueued_only_on_new_issues():
    conn = fakeredis.FakeStrictRedis()
    alerts = Queue("alerts", connection=conn)
    # NEW issues present -> one alert job enqueued.
    assert enqueue_customer_alert_if_new(alerts, "scan-1", {"fp1", "fp2"}) is True
    assert alerts.count == 1
    # No NEW issues -> silence (nothing enqueued).
    assert enqueue_customer_alert_if_new(alerts, "scan-2", set()) is False
    assert alerts.count == 1


def test_dispatch_customer_alert_delivers_to_each_target():
    calls = []
    alert = CustomerAlert(
        targets=[("email", "a@ex.com"), ("webhook", "https://hook.example")],
        message=AlertMessage(subject="s", body="b"),
    )
    dispatch_customer_alert(alert, deliver=lambda t, tgt, m: calls.append((t, tgt, m)))
    assert calls == [
        ("email", "a@ex.com", alert.message),
        ("webhook", "https://hook.example", alert.message),
    ]


def test_send_operator_alert_emails_operator_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "operator_alert_email", "ops@ex.com")
    calls = []
    alerts_mod.send_operator_alert(
        "scan-1", "boom", deliver=lambda t, tgt, m: calls.append((t, tgt))
    )
    assert calls == [("email", "ops@ex.com")]


def test_send_operator_alert_skips_delivery_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "operator_alert_email", "")
    calls = []
    alerts_mod.send_operator_alert("scan-1", "boom", deliver=lambda *a: calls.append(a))
    assert calls == []
