import runpy
import traceback
from pathlib import Path

import pytest
from pydantic import SecretStr

from lumini.settings import Settings


def test_alembic_engine_constructor_failure_does_not_echo_sensitive_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive = "synthetic-sensitive-query-value"
    settings = Settings(
        database_url=SecretStr(f"postgresql://localhost/lumini_test?async_fallback={sensitive}")
    )
    monkeypatch.setattr("lumini.settings.Settings", lambda: settings)
    monkeypatch.setattr("alembic.context.is_offline_mode", lambda: False)
    migration_env = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    with pytest.raises(RuntimeError, match="Migration failed") as caught:
        runpy.run_path(str(migration_env))
    assert sensitive not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__ is True
