from a11ywatch.web.trends import scan_trend


def test_trend_improved_when_issue_count_drops():
    t = scan_trend(2, 5)
    assert t.direction == "improved"
    assert t.change == -3
    assert t.magnitude == 3


def test_trend_regressed_when_issue_count_rises():
    t = scan_trend(5, 2)
    assert t.direction == "regressed"
    assert t.change == 3
    assert t.magnitude == 3


def test_trend_unchanged_when_equal():
    t = scan_trend(3, 3)
    assert t.direction == "unchanged"
    assert t.change == 0


def test_trend_no_baseline_when_no_previous_scan():
    t = scan_trend(4, None)
    assert t.direction == "no_baseline"
    assert t.change == 0


def test_trend_to_zero_is_improvement():
    t = scan_trend(0, 7)
    assert t.direction == "improved"
    assert t.change == -7
