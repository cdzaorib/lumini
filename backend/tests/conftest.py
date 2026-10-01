import os

import pytest


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never use a developer's provider/database credentials."""
    for key in tuple(os.environ):
        if key.startswith("LUMINI_") and key not in {
            "LUMINI_INTEGRATION_DATABASE_URL",
            "LUMINI_INTEGRATION_REDIS_URL",
        }:
            monkeypatch.delenv(key)
