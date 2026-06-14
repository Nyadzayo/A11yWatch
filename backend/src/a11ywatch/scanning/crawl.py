import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from urllib.parse import urljoin, urlsplit

HttpGet = Callable[[str], str]

_HREF = re.compile(r"""href=["']([^"'#]+)""", re.IGNORECASE)


def resolve_pages(
    *,
    base_url: str,
    url_list: Sequence[str] | None,
    sitemap_url: str | None,
    max_pages: int,
    http_get: HttpGet,
) -> list[str]:
    """Resolve the page set to scan: explicit url_list, else sitemap, else BFS crawl."""
    if url_list:
        return list(url_list)[:max_pages]
    if sitemap_url:
        return _from_sitemap(sitemap_url, http_get)[:max_pages]
    return _crawl(base_url, max_pages, http_get)


def _from_sitemap(sitemap_url: str, http_get: HttpGet) -> list[str]:
    root = ET.fromstring(http_get(sitemap_url))
    locs = [el.text.strip() for el in root.iter() if el.tag.endswith("}loc") or el.tag == "loc"]
    return [loc for loc in locs if loc]


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme.lower(), pa.netloc.lower()) == (pb.scheme.lower(), pb.netloc.lower())


def _crawl(base_url: str, max_pages: int, http_get: HttpGet) -> list[str]:
    visited: set[str] = set()
    enqueued: set[str] = {base_url}
    queue: list[str] = [base_url]
    pages: list[str] = []
    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        pages.append(url)
        try:
            html = http_get(url)
        except Exception:
            continue
        for href in _HREF.findall(html):
            link = urljoin(url, href)
            if urlsplit(link).scheme not in ("http", "https"):
                continue
            if _same_origin(base_url, link) and link not in enqueued:
                enqueued.add(link)
                queue.append(link)
    return pages[:max_pages]
