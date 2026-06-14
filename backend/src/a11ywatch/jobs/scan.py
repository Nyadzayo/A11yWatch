import asyncio
import logging
import uuid
from datetime import UTC, datetime

import httpx
from rq import get_current_job

from a11ywatch.core.config import settings
from a11ywatch.core.worker_db import worker_session
from a11ywatch.jobs.alerts import enqueue_customer_alert_if_new, enqueue_operator_alert
from a11ywatch.jobs.dispatch import LOCK_TTL_BUFFER_SECONDS, lock_key
from a11ywatch.jobs.queue import get_alert_queue, get_redis
from a11ywatch.jobs.retry import is_transient, should_retry
from a11ywatch.models.tables import Project, Scan
from a11ywatch.scanning.crawl import resolve_pages
from a11ywatch.scanning.engine import run_scan
from a11ywatch.scanning.persist import persist_scan_result
from a11ywatch.scanning.playwright_scanner import PlaywrightScanner
from a11ywatch.scanning.types import ScanResult

log = logging.getLogger(__name__)


def run_scan_job(scan_id: str) -> None:
    """The one shared scan job (on-demand and scheduled enqueue the same callable).

    DB work runs in ``asyncio.run()`` phases; the sync Playwright engine runs BETWEEN them
    with no event loop active (sync Playwright cannot run inside an asyncio loop).
    """
    config = asyncio.run(_begin(scan_id))
    if config is None:
        return
    try:
        result = _execute(config)
        asyncio.run(_finish(scan_id, result))
    except BaseException as exc:
        _on_error(scan_id, exc)


def _execute(config: dict) -> ScanResult:
    with httpx.Client(timeout=settings.scan_page_timeout_seconds, follow_redirects=True) as http:
        urls = resolve_pages(
            base_url=config["base_url"],
            url_list=config["url_list"],
            sitemap_url=config["sitemap_url"],
            max_pages=config["max_pages"],
            http_get=lambda url: http.get(url).text,
        )
    scanner = PlaywrightScanner(page_timeout_ms=config["page_timeout_ms"])
    return run_scan(urls, scanner, page_cap=config["max_pages"])


async def _begin(scan_id: str) -> dict | None:
    async with worker_session() as session:
        scan = await session.get(Scan, uuid.UUID(scan_id))
        if scan is None or scan.status != "queued":
            return None
        project = await session.get(Project, scan.project_id)
        if project is None:
            return None
        scan.status = "running"
        scan.started_at = datetime.now(UTC)
        project.status = "running"
        await session.commit()
        # Refresh the lock for this attempt's budget so retries don't let it expire mid-run.
        _refresh_lock(project.id)
        return {
            "base_url": project.base_url,
            "url_list": project.url_list,
            "sitemap_url": project.sitemap_url,
            "max_pages": project.max_pages or settings.scan_max_pages,
            "page_timeout_ms": settings.scan_page_timeout_seconds * 1000,
        }


async def _finish(scan_id: str, result: ScanResult) -> None:
    async with worker_session() as session:
        scan = await session.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            return
        diff = await persist_scan_result(session, scan, result)
        _release_lock(scan.project_id)
    # Regression alerts fire on NEW issues only; the queue op is best-effort so an
    # alert-queue hiccup can't fail a scan that already succeeded and committed.
    try:
        enqueue_customer_alert_if_new(get_alert_queue(), scan_id, diff.new)
    except Exception:
        log.warning("failed to enqueue customer alert for scan %s", scan_id)


async def _fail(scan_id: str, error: str) -> None:
    async with worker_session() as session:
        scan = await session.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            return
        finished = datetime.now(UTC)
        scan.status = "failed"
        scan.error = error[:2000]
        scan.finished_at = finished
        project = await session.get(Project, scan.project_id)
        if project is not None:
            # Unwedge: return to idle so the scheduler retries at the next due window.
            project.status = "idle"
            project.last_scan_at = finished
            project.last_scan_id = scan.id
        await session.commit()
        _release_lock(scan.project_id)


def _release_lock(project_id) -> None:
    try:
        get_redis().delete(lock_key(project_id))
    except Exception:
        log.warning("failed to release scan lock for project %s", project_id)


def _refresh_lock(project_id) -> None:
    try:
        get_redis().set(
            lock_key(project_id),
            "1",
            ex=settings.scan_site_timeout_seconds + LOCK_TTL_BUFFER_SECONDS,
        )
    except Exception:
        log.warning("failed to refresh scan lock for project %s", project_id)


def _on_error(scan_id: str, exc: BaseException) -> None:
    job = get_current_job()
    retries_left = getattr(job, "retries_left", None)
    if should_retry(exc, retries_left):
        # Transient with retries left: reset to 'queued' and re-raise so RQ retries with
        # backoff. The lock stays held across retries (the project remains in flight).
        asyncio.run(_reset_for_retry(scan_id))
        raise exc
    # Final outcome: mark failed (releases the lock) and alert the OPERATOR, not the customer.
    try:
        asyncio.run(_fail(scan_id, repr(exc)))
    except Exception:
        log.exception("failed to finalize failed scan %s", scan_id)
    try:
        enqueue_operator_alert(get_alert_queue(), scan_id, repr(exc))
    except Exception:
        log.warning("failed to enqueue operator alert for scan %s", scan_id)
    if is_transient(exc):
        raise exc  # retries exhausted: surface to RQ's failed registry
    # permanent failure: swallow so RQ does not retry


async def _reset_for_retry(scan_id: str) -> None:
    async with worker_session() as session:
        scan = await session.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            return
        scan.status = "queued"
        scan.started_at = None
        await session.commit()
