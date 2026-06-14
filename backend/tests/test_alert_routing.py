from a11ywatch.alerts.routing import channels_for_new_issues
from a11ywatch.models.tables import AlertChannel


def _ch(*, enabled=True, events=("new_issues",), target="a@ex.com"):
    return AlertChannel(
        project_id=None, type="email", target=target, enabled=enabled, events=list(events)
    )


def test_enabled_subscribed_channel_is_selected():
    ch = _ch()
    assert channels_for_new_issues([ch]) == [ch]


def test_disabled_channel_is_skipped():
    assert channels_for_new_issues([_ch(enabled=False)]) == []


def test_channel_not_subscribed_to_new_issues_is_skipped():
    assert channels_for_new_issues([_ch(events=("weekly_digest",))]) == []


def test_null_events_defaults_to_new_issues():
    ch = AlertChannel(project_id=None, type="email", target="a@ex.com", enabled=True, events=None)
    assert channels_for_new_issues([ch]) == [ch]


def test_explicit_empty_events_is_an_opt_out_not_a_default():
    # [] means "subscribed to nothing" — distinct from None ("never set, use default").
    ch = AlertChannel(project_id=None, type="email", target="a@ex.com", enabled=True, events=[])
    assert channels_for_new_issues([ch]) == []


def test_mixed_channels_returns_only_eligible():
    keep = _ch(target="keep@ex.com")
    drop_disabled = _ch(enabled=False, target="off@ex.com")
    drop_unsub = _ch(events=("other",), target="other@ex.com")
    selected = channels_for_new_issues([keep, drop_disabled, drop_unsub])
    assert selected == [keep]
