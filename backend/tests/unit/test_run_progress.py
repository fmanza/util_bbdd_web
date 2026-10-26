"""Puente de progreso y cancelación cooperativa con util_bbdd (GAPS G1, util_bbdd 4.1.0)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from util_bbdd.exceptions import OperationCancelledError
from util_bbdd.progress import ProgressEvent

from app.integrations.util_bbdd import documentation
from app.integrations.util_bbdd.documentation import DocumentationOptions
from app.integrations.util_bbdd.progress import RunProgress, is_cancellation
from app.jobs.operations.documentation import _job_error

PHASES = ("metadata", "word", "html")


def _bridge(
    cancel: bool = False, poll_seconds: float = 0.0
) -> tuple[RunProgress, list[tuple[str, int | None]], list[int]]:
    reported: list[tuple[str, int | None]] = []
    polls: list[int] = []

    def cancel_requested() -> bool:
        polls.append(1)
        return cancel

    bridge = RunProgress(
        lambda message, pct: reported.append((message, pct)),
        cancel_requested,
        PHASES,
        {"metadata": "Leyendo el catálogo", "word": "Word"},
        poll_seconds=poll_seconds,
    )
    return bridge, reported, polls


def test_events_become_messages_and_an_overall_percentage() -> None:
    bridge, reported, _ = _bridge()

    bridge(ProgressEvent("documentation", "metadata", 0, 1))
    bridge(ProgressEvent("documentation", "word", 2, 4, "clientes"))
    bridge(ProgressEvent("documentation", "html", 4, 4, "pedidos"))
    bridge(ProgressEvent("documentation", "otra", 0, None))

    assert reported == [
        ("Leyendo el catálogo: 0 de 1", 0),
        ("Word: 2 de 4 (clientes)", 50),  # 1 fase hecha + la mitad de la segunda, de 3
        ("html: 4 de 4 (pedidos)", 99),  # nunca 100 hasta que el run termina
        ("otra", None),
    ]


def test_cancel_request_cancels_the_token_and_polling_is_throttled() -> None:
    bridge, _, polls = _bridge(cancel=False, poll_seconds=3600)
    for current in range(5):
        bridge(ProgressEvent("documentation", "word", current, 5))
    assert len(polls) == 1  # una lectura de la BD por intervalo
    assert not bridge.token.is_cancelled()

    cancelling, _, _ = _bridge(cancel=True)
    cancelling(ProgressEvent("documentation", "metadata", 0, 1))
    assert cancelling.token.is_cancelled()


def test_cancellation_is_recognized_and_becomes_a_cancelled_job() -> None:
    try:
        try:
            raise OperationCancelledError("Operación cancelada: documentation", phase="word")
        except OperationCancelledError as exc:
            raise RuntimeError("envoltorio") from exc
    except RuntimeError as wrapped:
        assert is_cancellation(wrapped)
    assert not is_cancellation(RuntimeError("otra cosa"))
    error = _job_error(OperationCancelledError("x"))
    assert (error.code, error.message) == ("cancelled", "Cancelada por un usuario.")


def test_documentation_stops_between_tables_when_cancelled(tmp_path: Path) -> None:
    """Con util_bbdd real y SQLite: la cancelación pedida para la generación y los formatos no se escriben."""
    database = tmp_path / "tienda.db"
    con = sqlite3.connect(database)
    con.executescript("CREATE TABLE a (id INTEGER PRIMARY KEY); CREATE TABLE b (id INTEGER PRIMARY KEY);")
    con.close()
    bridge, reported, _ = _bridge(cancel=True)

    with pytest.raises(OperationCancelledError):
        documentation.generate_documentation(
            "sqlite",
            {"database": str(database)},
            schema=None,
            options=DocumentationOptions(formats=("word", "html"), graphs=False),
            outputs_dir=tmp_path / "out",
            work_dir=tmp_path / "work",
            name="doc",
            progress=bridge,
        )

    assert reported and reported[0][0].startswith("Leyendo el catálogo")
    assert not list((tmp_path / "out").rglob("*.docx"))


def test_worker_gives_cooperative_operations_time_to_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.jobs import worker as worker_module

    class _Process:
        def is_alive(self) -> bool:
            return True

    stopped: list[str] = []
    monkeypatch.setattr(worker_module.queue, "cancel_requested", lambda _db, ids: list(ids))
    w: Any = worker_module.Worker.__new__(worker_module.Worker)
    w.settings = type("S", (), {"job_timeout_seconds": 3600})()
    w.children = {
        "doc": worker_module._Child(process=_Process(), started=0.0, operation="documentation"),  # type: ignore[arg-type]
        "noop": worker_module._Child(process=_Process(), started=0.0, operation="noop"),  # type: ignore[arg-type]
    }
    monkeypatch.setattr(worker_module.time, "monotonic", lambda: 1.0)
    w._stop_child = lambda run_id, *_: stopped.append(run_id) or w.children.pop(run_id)

    w.enforce()
    assert stopped == ["noop"]  # la documentación tiene margen para parar sola
    assert w.children["doc"].cancel_seen == 1.0

    monkeypatch.setattr(worker_module.time, "monotonic", lambda: 1.0 + worker_module.COOPERATIVE_CANCEL_GRACE)
    w.enforce()
    assert stopped == ["noop", "doc"]  # sin parar a tiempo, se termina el subproceso (ADR-002)
