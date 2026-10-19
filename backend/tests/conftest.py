"""Fixtures comunes: ajustes aislados en ``tmp_path`` y cliente HTTP sobre la app."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Ajustes con ``data_dir`` y ``workspace_dir`` temporales; limpia las cachés de proceso."""
    monkeypatch.setenv("UBW_ENVIRONMENT", "test")
    monkeypatch.setenv("UBW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UBW_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("UBW_STATIC_DIR", str(tmp_path / "static"))
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield get_settings()
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
