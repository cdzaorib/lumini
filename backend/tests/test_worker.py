import ssl

import pytest
from pydantic import SecretStr

from lumini.settings import Settings
from lumini.worker import create_worker


def test_worker_refuses_to_start_without_explicit_broker() -> None:
    with pytest.raises(RuntimeError, match="LUMINI_REDIS_URL"):
        create_worker(Settings())


def test_worker_uses_json_and_has_no_mock_business_tasks() -> None:
    worker = create_worker(Settings(redis_url=SecretStr("redis://localhost:6379/1")))
    assert worker.conf.accept_content == ["json"]
    assert worker.conf.task_ignore_result is True
    assert worker.conf.enable_utc is True
    assert worker.conf.timezone == "UTC"
    assert not [name for name in worker.tasks if name.startswith("lumini.")]


def test_rediss_requires_certificate_and_hostname_in_resolved_kombu_connection() -> None:
    worker = create_worker(Settings(redis_url=SecretStr("rediss://localhost:6380/0")))
    connection = worker.connection_for_write()
    assert connection.ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert connection.ssl["ssl_check_hostname"] is True
