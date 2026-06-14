import fakeredis
from rq import Queue

from a11ywatch.jobs.alerts import OPERATOR_ALERT_JOB, enqueue_operator_alert


def test_enqueue_operator_alert_goes_to_the_alerts_queue():
    conn = fakeredis.FakeStrictRedis()
    alerts = Queue("alerts", connection=conn)
    enqueue_operator_alert(alerts, "scan-123", "boom")
    assert alerts.count == 1
    job = alerts.jobs[0]
    assert job.func_name == OPERATOR_ALERT_JOB
    assert job.args == ("scan-123", "boom")
