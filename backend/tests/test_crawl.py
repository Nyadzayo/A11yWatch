from a11ywatch.scanning.crawl import resolve_pages

SITEMAP = (
    '<?xml version="1.0"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://ex.com/a</loc></url>"
    "<url><loc>https://ex.com/b</loc></url>"
    "</urlset>"
)


def test_url_list_is_used_and_capped_without_fetching():
    calls = []

    def http_get(u):
        calls.append(u)
        return ""

    result = resolve_pages(
        base_url="https://ex.com",
        url_list=["https://ex.com/1", "https://ex.com/2", "https://ex.com/3"],
        sitemap_url=None,
        max_pages=2,
        http_get=http_get,
    )
    assert result == ["https://ex.com/1", "https://ex.com/2"]
    assert calls == []


def test_sitemap_is_parsed():
    result = resolve_pages(
        base_url="https://ex.com",
        url_list=None,
        sitemap_url="https://ex.com/sitemap.xml",
        max_pages=10,
        http_get=lambda u: SITEMAP,
    )
    assert result == ["https://ex.com/a", "https://ex.com/b"]


def test_crawl_stays_same_origin_and_respects_cap():
    pages = {
        "https://ex.com/": '<a href="/a">a</a><a href="/b">b</a><a href="https://other.com/x">x</a>',
        "https://ex.com/a": '<a href="/c">c</a>',
        "https://ex.com/b": "",
    }
    result = resolve_pages(
        base_url="https://ex.com/",
        url_list=None,
        sitemap_url=None,
        max_pages=3,
        http_get=lambda u: pages.get(u, ""),
    )
    assert len(result) == 3
    assert all(r.startswith("https://ex.com") for r in result)
    assert "https://other.com/x" not in result


def test_crawl_excludes_non_http_schemes():
    pages = {
        "https://ex.com/": (
            '<a href="mailto:x@y.com">m</a><a href="javascript:void(0)">j</a><a href="/a">a</a>'
        ),
        "https://ex.com/a": "",
    }
    result = resolve_pages(
        base_url="https://ex.com/",
        url_list=None,
        sitemap_url=None,
        max_pages=10,
        http_get=lambda u: pages.get(u, ""),
    )
    assert result == ["https://ex.com/", "https://ex.com/a"]
