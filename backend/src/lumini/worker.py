"""Celery worker with an embedded beat schedule for the booking jobs.

Run exactly one beat (the default `main` embeds it in a single worker). A duplicate beat only
wastes work: each job takes a Redis lock and PostgreSQL keeps concurrent runs correct.
"""

import asyncio
import ssl
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from celery import Celery

from lumini.booking.google_calendar import build_calendar
from lumini.booking.jobs import run_reconcile, run_tick
from lumini.settings import Settings
from lumini.whatsapp.evolution import build_sender

TICK_TASK = "lumini.booking.tick"
RECONCILE_TASK = "lumini.calendar.reconcile"
TICK_SECONDS = 60.0
RECONCILE_SECONDS = 900.0


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

    calendar = build_calendar(config)
    sender = build_sender(config)

    @worker.task(name=TICK_TASK, shared=False)  # type: ignore[untyped-decorator]
    def booking_tick() -> None:
        asyncio.run(run_tick(config, calendar=calendar, sender=sender))

    @worker.task(name=RECONCILE_TASK, shared=False)  # type: ignore[untyped-decorator]
    def calendar_reconcile() -> None:
        if calendar is not None:
            asyncio.run(run_reconcile(config, calendar=calendar))

    # Expiring messages keep a stopped worker from replaying a backlog of identical runs.
    worker.conf.beat_schedule = {
        "booking-tick": {
            "task": TICK_TASK,
            "schedule": TICK_SECONDS,
            "options": {"expires": TICK_SECONDS - 5},
        },
        "calendar-reconcile": {
            "task": RECONCILE_TASK,
            "schedule": RECONCILE_SECONDS,
            "options": {"expires": RECONCILE_SECONDS / 2},
        },
    }
    return worker


def main() -> None:
    schedule = Path(tempfile.gettempdir()) / "lumini-celerybeat-schedule"
    create_worker().worker_main(
        ["worker", "--loglevel=WARNING", "--concurrency=1", "--beat", f"--schedule={schedule}"]
    )


if __name__ == "__main__":
    main()
