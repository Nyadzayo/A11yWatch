import pytest

from a11ywatch.web.forms import is_hex_color, parse_branding


def test_parse_branding_full():
    out = parse_branding(
        company_name="  Acme Agency ",
        logo_url="https://acme.com/logo.png",
        primary_color="#1a56db",
        report_footer="  Prepared by Acme  ",
    )
    assert out["company_name"] == "Acme Agency"
    assert out["logo_url"] == "https://acme.com/logo.png"
    assert out["primary_color"] == "#1a56db"
    assert out["report_footer"] == "Prepared by Acme"


def test_parse_branding_blank_to_none():
    out = parse_branding(company_name="", logo_url="  ", primary_color="", report_footer="")
    assert out == {
        "company_name": None,
        "logo_url": None,
        "primary_color": None,
        "report_footer": None,
    }


def test_parse_branding_normalizes_short_hex_without_hash():
    out = parse_branding(
        company_name=None, logo_url=None, primary_color="abc", report_footer=None
    )
    assert out["primary_color"] == "#aabbcc"


def test_parse_branding_rejects_non_http_logo():
    with pytest.raises(ValueError):
        parse_branding(
            company_name=None, logo_url="ftp://x/logo.png", primary_color=None, report_footer=None
        )


def test_parse_branding_rejects_css_injection_color():
    with pytest.raises(ValueError):
        parse_branding(
            company_name=None, logo_url=None, primary_color="red; }", report_footer=None
        )


def test_is_hex_color():
    assert is_hex_color("#1a56db")
    assert is_hex_color("#abc")
    assert is_hex_color("aabbcc")
    assert not is_hex_color("red")
    assert not is_hex_color("#12")
    assert not is_hex_color("#xyzxyz")
