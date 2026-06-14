from redis import Redis
from rq import Queue, Worker

from a11ywatch.core.config import settings
from a11ywatch.core.logging import configure_logging


def main() -> None:
    configure_logging()
    connection = Redis.from_url(settings.redis_url)
    queues = [Queue("scans", connection=connection), Queue("alerts", connection=connection)]
    # with_scheduler=True so staggered (enqueue_in) scans fire when due.
    Worker(queues, connection=connection).work(with_scheduler=True)


if __name__ == "__main__":
    main()
