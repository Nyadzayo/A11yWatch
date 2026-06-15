import pytest

from a11ywatch.web.forms import parse_alert_channel


def test_parse_email_channel():
    out = parse_alert_channel(channel_type="email", target="  alerts@acme.com  ")
    assert out == {
        "type": "email",
        "target": "alerts@acme.com",
        "events": ["new_issues"],
        "enabled": True,
    }


def test_parse_slack_webhook():
    out = parse_alert_channel(channel_type="slack", target="https://hooks.slack.com/services/x")
    assert out["type"] == "slack"
    assert out["target"] == "https://hooks.slack.com/services/x"
    assert out["events"] == ["new_issues"]


def test_parse_rejects_unknown_type():
    with pytest.raises(ValueError):
        parse_alert_channel(channel_type="sms", target="+123")


def test_parse_rejects_bad_email():
    with pytest.raises(ValueError):
        parse_alert_channel(channel_type="email", target="not-an-email")


def test_parse_rejects_non_http_slack():
    with pytest.raises(ValueError):
        parse_alert_channel(channel_type="slack", target="ftp://nope")


def test_parse_rejects_blank_target():
    with pytest.raises(ValueError):
        parse_alert_channel(channel_type="email", target="   ")
