"""Prueba de conexión y readiness reales contra los contenedores bench de util_bbdd (fuera del CI).

Requiere ``docker-compose.bench.yml`` de util_bbdd en marcha y ``UTIL_BBDD_BENCH_PASSWORD`` en el entorno. Los
puertos se pueden cambiar con ``UTIL_BBDD_BENCH_<MOTOR>_PORT`` (los mismos nombres que el compose)::

    uv run pytest -m integration tests/integration
"""

from __future__ import annotations

import os
import re
from typing import Any

import pytest

from app.integrations.util_bbdd.catalog import build_params
from app.integrations.util_bbdd.probe import check_connection, engine_readiness

pytestmark = pytest.mark.integration

PASSWORD = os.environ.get("UTIL_BBDD_BENCH_PASSWORD", "")


def _port(name: str, default: int) -> int:
    return int(os.environ.get(f"UTIL_BBDD_BENCH_{name}_PORT", default))


BENCH: dict[str, dict[str, Any]] = {
    "postgresql": {"host": "127.0.0.1", "port": _port("POSTGRES", 55432), "user": "bench", "database": "bench"},
    "mysql": {"host": "127.0.0.1", "port": _port("MYSQL", 53306), "user": "bench", "database": "bench"},
    "mariadb": {"host": "127.0.0.1", "port": _port("MARIADB", 53307), "user": "bench", "database": "bench"},
    "sqlserver": {"host": "127.0.0.1", "port": _port("MSSQL", 51433), "user": "sa", "database": "bench"},
    "oracle": {"host": "127.0.0.1", "port": _port("ORACLE", 51521), "user": "bench", "service_name": "FREEPDB1"},
}


@pytest.fixture(scope="module", autouse=True)
def _require_password() -> None:
    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")


@pytest.mark.parametrize("db_type", sorted(BENCH))
def test_bench_connection(db_type: str) -> None:
    result = check_connection(db_type, build_params(db_type, {**BENCH[db_type], "password": PASSWORD}), timeout=60)

    assert result.ok, result.error
    # G43 (util_bbdd 5.0.0, W-8.3): numérica y sin sufijos de distribución (Oracle 23ai: 23.26.3.0.0).
    assert result.server_version and re.fullmatch(r"\d+(\.\d+)+", result.server_version), result.server_version


@pytest.mark.parametrize("db_type", sorted(BENCH))
def test_bench_readiness(db_type: str) -> None:
    report = engine_readiness(db_type, build_params(db_type, {**BENCH[db_type], "password": PASSWORD}), timeout=60)

    assert report.error is None, report.error
    assert report.supported
    assert report.dynamic, report.detail
    assert all(PASSWORD not in f.current for f in report.findings)


def test_bench_wrong_password_is_sanitized() -> None:
    result = check_connection(
        "postgresql", build_params("postgresql", {**BENCH["postgresql"], "password": "no-es-esta"}), timeout=60
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "connection_failed"
