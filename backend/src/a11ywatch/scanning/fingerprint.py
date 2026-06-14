import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"gclid", "fbclid"}


def normalize_url(url: str) -> str:
    """Canonicalize a page URL so equivalent URLs produce one stable fingerprint.

    Lowercase scheme+host, drop fragment, strip trailing slash, sort query params
    by key, and drop tracking params (utm_*, gclid, fbclid). Path case is preserved.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    elif scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    path = parts.path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    if path == "/":
        path = ""
    pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith(_TRACKING_PREFIXES) and k not in _TRACKING_KEYS
    ]
    query = urlencode(sorted(pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def compute_fingerprint(rule_id: str, page_url: str, target: str) -> str:
    """Stable diff key for a single accessibility issue on a page element."""
    raw = f"{rule_id}|{normalize_url(page_url)}|{target}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
