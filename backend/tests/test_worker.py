import ssl

import pytest
from pydantic import SecretStr

from lumini.settings import Settings
from lumini.worker import RECONCILE_TASK, TICK_TASK, create_worker
from tests.calendar_keys import service_account_json


def test_worker_refuses_to_start_without_explicit_broker() -> None:
    with pytest.raises(RuntimeError, match="LUMINI_REDIS_URL"):
        create_worker(Settings())


def test_worker_uses_json_and_registers_only_the_booking_jobs() -> None:
    worker = create_worker(Settings(redis_url=SecretStr("redis://localhost:6379/1")))
    assert worker.conf.accept_content == ["json"]
    assert worker.conf.task_ignore_result is True
    assert worker.conf.enable_utc is True
    assert worker.conf.timezone == "UTC"
    assert {name for name in worker.tasks if name.startswith("lumini.")} == {
        TICK_TASK,
        RECONCILE_TASK,
    }


def test_beat_runs_each_job_periodically_without_replaying_a_backlog() -> None:
    worker = create_worker(Settings(redis_url=SecretStr("redis://localhost:6379/1")))
    schedule = {entry["task"]: entry for entry in worker.conf.beat_schedule.values()}
    assert schedule[TICK_TASK]["schedule"] == 60
    assert schedule[RECONCILE_TASK]["schedule"] == 900
    for entry in schedule.values():
        assert 0 < entry["options"]["expires"] < entry["schedule"]


def test_jobs_run_without_calendar_credentials_only_where_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []

    async def fake_tick(settings: Settings, *, calendar: object) -> None:
        calls.append(("tick", calendar))

    async def fake_reconcile(settings: Settings, *, calendar: object) -> None:
        calls.append(("reconcile", calendar))

    monkeypatch.setattr("lumini.worker.run_tick", fake_tick)
    monkeypatch.setattr("lumini.worker.run_reconcile", fake_reconcile)
    worker = create_worker(Settings(redis_url=SecretStr("redis://localhost:6379/1")))
    worker.tasks[TICK_TASK].run()
    worker.tasks[RECONCILE_TASK].run()
    # Expiry and message scheduling still run; reconciliation needs the calendar.
    assert calls == [("tick", None)]

    calls.clear()
    configured = Settings(
        redis_url=SecretStr("redis://localhost:6379/1"),
        google_calendar_credentials=SecretStr(service_account_json()),
    )
    worker = create_worker(configured)
    worker.tasks[RECONCILE_TASK].run()
    assert [name for name, calendar in calls if calendar is not None] == ["reconcile"]


def test_rediss_requires_certificate_and_hostname_in_resolved_kombu_connection() -> None:
    worker = create_worker(Settings(redis_url=SecretStr("rediss://localhost:6380/0")))
    connection = worker.connection_for_write()
    assert connection.ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert connection.ssl["ssl_check_hostname"] is True
