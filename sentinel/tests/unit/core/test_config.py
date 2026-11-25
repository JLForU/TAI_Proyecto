"""Tests de ``core.config`` (BR-U2-41/42)."""

from __future__ import annotations

import pytest

from sentinel.core.config import CoreSettings, load_core_settings
from sentinel.foundation.errors import ConfigError


def test_defaults() -> None:
    s = load_core_settings({})
    assert s.db_path == "/data/sentinel.db"
    assert s.ingest_token == ""
    assert s.page_limit == 100
    assert s.missing_cycles == 3


def test_env_overrides() -> None:
    s = load_core_settings(
        {
            "SENTINEL_DB_PATH": "/tmp/x.db",
            "SENTINEL_INGEST_TOKEN": "t",
            "SENTINEL_PAGE_LIMIT": "50",
            "SENTINEL_MISSING_CYCLES": "5",
        }
    )
    assert (s.db_path, s.ingest_token, s.page_limit, s.missing_cycles) == (
        "/tmp/x.db",
        "t",
        50,
        5,
    )


def test_exactly_four_fields() -> None:
    assert set(CoreSettings.model_fields) == {
        "db_path",
        "ingest_token",
        "page_limit",
        "missing_cycles",
    }


def test_invalid_page_limit_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        load_core_settings({"SENTINEL_PAGE_LIMIT": "99999"})


def test_extra_env_ignored() -> None:
    s = load_core_settings({"SENTINEL_UNRELATED": "x"})
    assert isinstance(s, CoreSettings)
