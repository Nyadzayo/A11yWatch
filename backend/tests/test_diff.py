from a11ywatch.scanning.diff import diff_fingerprints


def test_identical_scans_have_no_new_or_resolved():
    d = diff_fingerprints(current={"a", "b"}, previous={"a", "b"})
    assert d.new == set()
    assert d.resolved == set()


def test_added_issue_is_new():
    d = diff_fingerprints(current={"a", "b", "c"}, previous={"a", "b"})
    assert d.new == {"c"}
    assert d.resolved == set()


def test_removed_issue_is_resolved():
    d = diff_fingerprints(current={"a"}, previous={"a", "b"})
    assert d.new == set()
    assert d.resolved == {"b"}


def test_first_scan_marks_everything_new():
    d = diff_fingerprints(current={"a", "b"}, previous=set())
    assert d.new == {"a", "b"}
    assert d.resolved == set()


def test_counts_reflect_new_and_resolved():
    d = diff_fingerprints(current={"a", "c"}, previous={"a", "b"})
    assert d.new == {"c"}
    assert d.resolved == {"b"}
    assert d.new_count == 1
    assert d.resolved_count == 1
