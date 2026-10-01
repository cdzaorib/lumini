"""Celery configuration only; no booking jobs or provider integrations registered yet."""

import ssl
from urllib.parse import urlsplit

from celery import Celery

from lumini.settings import Settings


def create_worker(settings: Settings | None = None) -> Celery:
    config = settings if settings is not None else Settings()
    if config.redis_url is None:
        raise RuntimeError("LUMINI_REDIS_URL is required to start the worker")
    worker = Celery("lumini", broker=config.redis_url.get_secret_value())
    worker.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_ignore_result=True,
        task_track_started=False,
        task_send_sent_event=False,
        worker_send_task_events=False,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"visibility_timeout": 3600},
        enable_utc=True,
        timezone="UTC",
    )
    if urlsplit(config.redis_url.get_secret_value()).scheme == "rediss":
        worker.conf.broker_use_ssl = {
            "ssl_cert_reqs": ssl.CERT_REQUIRED,
            "ssl_check_hostname": True,
        }
    return worker


def main() -> None:
    create_worker().worker_main(["worker", "--loglevel=WARNING", "--concurrency=1"])


if __name__ == "__main__":
    main()
