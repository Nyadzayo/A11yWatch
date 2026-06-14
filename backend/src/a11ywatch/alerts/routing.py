from collections.abc import Iterable

# MVP fires customer alerts on regressions only. A channel with no explicit event
# subscription defaults to receiving new-issue alerts.
NEW_ISSUES_EVENT = "new_issues"
DEFAULT_EVENTS = (NEW_ISSUES_EVENT,)


def channels_for_new_issues(channels: Iterable) -> list:
    """Filter to channels that are enabled and subscribed to new-issue alerts.

    ``events is None`` means the subscription was never set, so it defaults to new issues.
    An explicit empty list means "subscribed to nothing" — a real opt-out we must honor,
    so we check against None rather than truthiness.
    """
    selected = []
    for c in channels:
        if not c.enabled:
            continue
        events = c.events if c.events is not None else DEFAULT_EVENTS
        if NEW_ISSUES_EVENT in events:
            selected.append(c)
    return selected
