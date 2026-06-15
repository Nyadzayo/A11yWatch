from urllib.parse import urlsplit

# Scan-frequency presets offered in the dashboard, mapped to minutes the scheduler uses.
FREQUENCY_MINUTES = {"hourly": 60, "daily": 1440, "weekly": 10080}


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
