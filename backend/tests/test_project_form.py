import pytest

from a11ywatch.web.forms import FREQUENCY_MINUTES, frequency_label, parse_project_settings


def test_parse_full_settings():
    out = parse_project_settings(
        frequency="weekly",
        sitemap_url="https://ex.com/sitemap.xml",
        url_list_raw="https://ex.com/a\n  https://ex.com/b  \n\n",
        max_pages_raw="10",
    )
    assert out["scan_frequency_minutes"] == FREQUENCY_MINUTES["weekly"]
    assert out["sitemap_url"] == "https://ex.com/sitemap.xml"
    assert out["url_list"] == ["https://ex.com/a", "https://ex.com/b"]
    assert out["max_pages"] == 10


def test_parse_blank_optionals_become_none():
    out = parse_project_settings(
        frequency="daily", sitemap_url="  ", url_list_raw="", max_pages_raw=""
    )
    assert out["scan_frequency_minutes"] == 1440
    assert out["sitemap_url"] is None
    assert out["url_list"] is None
    assert out["max_pages"] is None


def test_parse_rejects_unknown_frequency():
    with pytest.raises(ValueError):
        parse_project_settings(
            frequency="yearly", sitemap_url=None, url_list_raw=None, max_pages_raw=None
        )


def test_parse_rejects_non_http_sitemap():
    with pytest.raises(ValueError):
        parse_project_settings(
            frequency="daily", sitemap_url="ftp://x", url_list_raw=None, max_pages_raw=None
        )


def test_parse_rejects_non_http_url_in_list():
    with pytest.raises(ValueError):
        parse_project_settings(
            frequency="daily",
            sitemap_url=None,
            url_list_raw="https://ok.com\nnot-a-url",
            max_pages_raw=None,
        )


def test_parse_rejects_non_numeric_max_pages():
    with pytest.raises(ValueError):
        parse_project_settings(
            frequency="daily", sitemap_url=None, url_list_raw=None, max_pages_raw="abc"
        )


def test_parse_rejects_zero_max_pages():
    with pytest.raises(ValueError):
        parse_project_settings(
            frequency="daily", sitemap_url=None, url_list_raw=None, max_pages_raw="0"
        )


def test_frequency_label_maps_known_minutes():
    assert frequency_label(60) == "hourly"
    assert frequency_label(1440) == "daily"
    assert frequency_label(10080) == "weekly"
