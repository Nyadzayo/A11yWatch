from a11ywatch.scheduler.healthcheck import ping_healthcheck


def test_ping_calls_http_get_with_url():
    calls = []
    ok = ping_healthcheck("https://hc.test/abc", http_get=lambda u: calls.append(u))
    assert ok is True
    assert calls == ["https://hc.test/abc"]


def test_ping_is_noop_when_url_empty():
    calls = []
    ok = ping_healthcheck("", http_get=lambda u: calls.append(u))
    assert ok is False
    assert calls == []


def test_ping_swallows_errors_and_returns_false():
    def boom(_url):
        raise RuntimeError("network down")

    assert ping_healthcheck("https://hc.test/abc", http_get=boom) is False
