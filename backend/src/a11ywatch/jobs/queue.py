import redis
from rq import Queue

from a11ywatch.core.config import settings

SCAN_QUEUE = "scans"
ALERT_QUEUE = "alerts"


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=5)


def get_scan_queue() -> Queue:
    return Queue(SCAN_QUEUE, connection=get_redis())


def get_alert_queue() -> Queue:
    return Queue(ALERT_QUEUE, connection=get_redis())
