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


@pytest.mark.parametrize("operation", ["migrate_apply", "dump_apply", "bulk_apply"])
def test_worker_never_kills_a_write_that_stops_between_steps(monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    """``migrate_apply`` (entre sentencias, W-M4), ``dump_apply`` (W-V2) y ``bulk_apply`` (W-B3, entre lotes) paran
    solos: cancelar no mata el subproceso; el timeout sí."""
    from app.jobs import worker as worker_module

    class _Process:
        def is_alive(self) -> bool:
            return True

    stopped: list[tuple[str, str]] = []
    monkeypatch.setattr(worker_module.queue, "cancel_requested", lambda _db, ids: list(ids))
    w: Any = worker_module.Worker.__new__(worker_module.Worker)
    w.settings = type("S", (), {"job_timeout_seconds": 3600})()
    w.children = {"ddl": worker_module._Child(process=_Process(), started=0.0, operation=operation)}  # type: ignore[arg-type]
    w._stop_child = lambda run_id, _status, code, _msg: stopped.append((run_id, code)) or w.children.pop(run_id)

    monkeypatch.setattr(worker_module.time, "monotonic", lambda: 1.0 + 10 * worker_module.COOPERATIVE_CANCEL_GRACE)
    w.enforce()
    assert stopped == [] and w.children["ddl"].cancel_seen is not None

    monkeypatch.setattr(worker_module.time, "monotonic", lambda: 3601.0)
    w.enforce()
    assert stopped == [("ddl", "job_timeout")]


def test_graph_of_all_tables_stops_between_tables_when_cancelled(tmp_path: Path) -> None:
    """Grafo de todas las tablas con util_bbdd real: la cancelación lo para tabla a tabla (W-G1)."""
    import shutil

    if shutil.which("dot") is None:
        pytest.skip("Graphviz (dot) no está instalado")
    database = tmp_path / "tienda.db"
    con = sqlite3.connect(database)
    con.executescript(
        """
        CREATE TABLE a (id INTEGER PRIMARY KEY);
        CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER REFERENCES a(id));
        """
    )
    con.close()
    reported: list[tuple[str, int | None]] = []
    graphs_bridge = RunProgress(lambda m, p: reported.append((m, p)), lambda: True, ("tables",), poll_seconds=0)

    with pytest.raises(OperationCancelledError):
        documentation.generate_graphs(
            "sqlite",
            {"database": str(database)},
            schema=None,
            options=documentation.GraphOptions(),
            output_dir=tmp_path / "graphs",
            progress=graphs_bridge,
        )

    assert not list((tmp_path / "graphs").glob("*.svg"))


def test_worker_queues_a_restore_when_a_dump_process_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout, caída o huérfano: tras cerrar el run, el worker pide la restauración de constraints (G31)."""
    from app.jobs import worker as worker_module

    class _Process:
        exitcode = -9

        def is_alive(self) -> bool:
            return False

        def join(self, timeout: float | None = None) -> None:
            return None

        def terminate(self) -> None:
            return None

    asked: list[str] = []

    def enqueue(_db: Any, run_id: str, _settings: Any, *, ctx: Any) -> str | None:
        asked.append(run_id)
        if run_id == "roto":
            raise RuntimeError("la BD no responde")
        return "restauracion"

    monkeypatch.setattr(worker_module, "enqueue_automatic_restore", enqueue)
    monkeypatch.setattr(worker_module, "finalize_run", lambda *_a, **_k: True)
    w: Any = worker_module.Worker.__new__(worker_module.Worker)
    w.settings = object()
    w.children = {
        "muerto": worker_module._Child(process=_Process(), started=0.0, operation="dump_apply"),  # type: ignore[arg-type]
        "lento": worker_module._Child(process=_Process(), started=0.0, operation="dump_apply"),  # type: ignore[arg-type]
    }

    w.reap()
    w.children["lento"] = worker_module._Child(process=_Process(), started=0.0, operation="dump_apply")  # type: ignore[arg-type]
    w._stop_child("lento", "failed", "job_timeout", "Superó el tiempo máximo")
    w._restore_after("roto")  # un fallo al encolar no para el worker

    assert asked == ["muerto", "lento", "lento", "roto"]
