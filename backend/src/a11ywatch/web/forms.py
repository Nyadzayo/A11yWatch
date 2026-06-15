from urllib.parse import urlsplit

from a11ywatch.models.schemas import validate_channel_target

# Scan-frequency presets offered in the dashboard, mapped to minutes the scheduler uses.
FREQUENCY_MINUTES = {"hourly": 60, "daily": 1440, "weekly": 10080}

# Alert-channel kinds offered in the dashboard (must match AlertChannelCreate's Literal).
ALERT_CHANNEL_TYPES = ("email", "webhook", "slack")


def _is_http_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def parse_project_settings(
    *,
    frequency: str,
    sitemap_url: str | None,
    url_list_raw: str | None,
    max_pages_raw: str | None,
) -> dict:
    """Validate and normalize the optional add-project settings into model kwargs.

    Raises ``ValueError`` with a user-facing message on invalid input. Blank optional
    fields normalize to ``None`` (clearing them).
    """
    if frequency not in FREQUENCY_MINUTES:
        raise ValueError("Choose a valid scan frequency")
    out: dict = {"scan_frequency_minutes": FREQUENCY_MINUTES[frequency]}

    sitemap = (sitemap_url or "").strip()
    if sitemap and not _is_http_url(sitemap):
        raise ValueError("Sitemap URL must start with http:// or https://")
    out["sitemap_url"] = sitemap or None

    urls = [line.strip() for line in (url_list_raw or "").splitlines() if line.strip()]
    for url in urls:
        if not _is_http_url(url):
            raise ValueError(f"Each page URL must start with http:// or https:// — got: {url}")
    out["url_list"] = urls or None

    max_pages = (max_pages_raw or "").strip()
    if max_pages:
        try:
            count = int(max_pages)
        except ValueError:
            raise ValueError("Max pages must be a whole number") from None
        if count < 1:
            raise ValueError("Max pages must be at least 1")
        out["max_pages"] = count
    else:
        out["max_pages"] = None

    return out


def is_hex_color(value: str) -> bool:
    digits = value.lstrip("#")
    return len(digits) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in digits)


def _normalize_hex_color(value: str) -> str:
    digits = value.lstrip("#").lower()
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits


def parse_branding(
    *,
    company_name: str | None,
    logo_url: str | None,
    primary_color: str | None,
    report_footer: str | None,
) -> dict:
    """Validate and normalize white-label branding into model kwargs.

    Raises ``ValueError`` on a non-http logo URL or a malformed brand color (the color
    is later inlined into report CSS, so it must be a safe hex value). Blank fields → None.
    """
    name = (company_name or "").strip()
    if len(name) > 200:
        raise ValueError("Company name must be 200 characters or fewer")

    logo = (logo_url or "").strip()
    if logo and not _is_http_url(logo):
        raise ValueError("Logo URL must start with http:// or https://")

    color = (primary_color or "").strip()
    if color and not is_hex_color(color):
        raise ValueError("Brand color must be a hex value like #1a56db")

    return {
        "company_name": name or None,
        "logo_url": logo or None,
        "primary_color": _normalize_hex_color(color) if color else None,
        "report_footer": (report_footer or "").strip() or None,
    }


def parse_alert_channel(*, channel_type: str, target: str) -> dict:
    """Validate a regression-alert destination into AlertChannel kwargs.

    Reuses the API's ``validate_channel_target`` so the dashboard and API enforce the
    same rules. Raises ``ValueError`` with a user-facing message on invalid input.
    """
    if channel_type not in ALERT_CHANNEL_TYPES:
        raise ValueError("Choose a valid channel type")
    target = (target or "").strip()
    if not target:
        raise ValueError("Destination is required")
    validate_channel_target(channel_type, target)  # raises ValueError if malformed
    return {"type": channel_type, "target": target, "events": ["new_issues"], "enabled": True}


def frequency_label(minutes: int) -> str:
    """Human label for a stored scan-frequency value (inverse of FREQUENCY_MINUTES)."""
    for name, mins in FREQUENCY_MINUTES.items():
        if mins == minutes:
            return name
    if minutes % 1440 == 0:
        return f"every {minutes // 1440} days"
    if minutes % 60 == 0:
        return f"every {minutes // 60} hours"
    return f"every {minutes} minutes"
