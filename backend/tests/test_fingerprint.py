from a11ywatch.scanning.fingerprint import compute_fingerprint, normalize_url


def test_normalize_lowercases_host_strips_fragment_and_trailing_slash():
    assert normalize_url("https://Example.com/Path/#section") == "https://example.com/Path"


def test_normalize_root_path_has_no_trailing_slash():
    assert normalize_url("https://example.com/") == "https://example.com"
    assert normalize_url("https://example.com") == "https://example.com"


def test_normalize_sorts_query_and_drops_tracking_params():
    assert (
        normalize_url("https://example.com/p?b=2&a=1&utm_source=x&gclid=y&fbclid=z")
        == "https://example.com/p?a=1&b=2"
    )


def test_fingerprint_stable_across_equivalent_urls():
    f1 = compute_fingerprint("color-contrast", "https://example.com/p/?utm_source=x", "div > a")
    f2 = compute_fingerprint("color-contrast", "https://Example.com/p#frag", "div > a")
    assert f1 == f2


def test_fingerprint_differs_by_rule_and_target():
    base = compute_fingerprint("color-contrast", "https://example.com/p", "a")
    assert base != compute_fingerprint("image-alt", "https://example.com/p", "a")
    assert base != compute_fingerprint("color-contrast", "https://example.com/p", "button")


def test_normalize_strips_default_ports_but_keeps_others():
    assert normalize_url("https://example.com:443/p") == "https://example.com/p"
    assert normalize_url("http://example.com:80/p") == "http://example.com/p"
    assert normalize_url("https://example.com:8443/p") == "https://example.com:8443/p"
