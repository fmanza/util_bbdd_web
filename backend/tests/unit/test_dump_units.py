"""Fase 8: vista previa con ``plan()`` (G29), avance y cancelación (G1), huella, tablas y errores saneados."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd.dump import (
    DumpOptions,
    DumpProgress,
    Endpoint,
    build_preview,
    cancelled_result,
    parse_tables,
    redact_values,
    result_to_dict,
    run_dump,
    structure_hash,
)

# Cadena clientes → pedidos → lineas, tabla suelta (sin destino en el test de orden) y ciclo a ↔ b.
SCHEMA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id), total NUMERIC);
CREATE TABLE lineas (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));
CREATE TABLE a (id INTEGER PRIMARY KEY, b_id INTEGER REFERENCES b(id));
CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER REFERENCES a(id));
CREATE TABLE sueltas (id INTEGER PRIMARY KEY, v TEXT);
"""


def _endpoints(tmp_path: Path, source_sql: str, target_sql: str) -> tuple[Endpoint, Endpoint]:
    from app.integrations.util_bbdd.catalog import build_params

    endpoints = []
    for name, script in (("o.db", source_sql), ("d.db", target_sql)):
        con = sqlite3.connect(tmp_path / name)
        con.executescript(script)
        con.close()
        endpoints.append(Endpoint("sqlite", build_params("sqlite", {"database": str(tmp_path / name)}), None))
    return endpoints[0], endpoints[1]


def test_preview_order_is_the_one_util_bbdd_loads(tmp_path: Path) -> None:
    """Contrato G29: el orden y los ciclos de la vista previa (``plan()``) son los de ``run()``."""
    target_sql = SCHEMA.replace("CREATE TABLE sueltas (id INTEGER PRIMARY KEY, v TEXT);", "")
    source, target = _endpoints(tmp_path, SCHEMA + "INSERT INTO clientes VALUES (1, 'x');", target_sql)
    options = DumpOptions()

    preview = build_preview(source, target, options)
    result = run_dump(
        source, target, options=options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
    )  # fmt: skip

    assert preview["load_order"] == result["load_order"] == ["clientes", "sueltas", "pedidos", "lineas", "a", "b"]
    assert preview["cycles"] == result["cycles"] == [["a", "b"]]
    assert [t["position"] for t in preview["tables"]] == list(range(6))


@pytest.mark.parametrize("on_error", ["raise", "isolate"])
def test_preview_columns_come_from_the_plan(tmp_path: Path, on_error: Literal["raise", "isolate"]) -> None:
    source_sql = "CREATE TABLE t (id INTEGER PRIMARY KEY, extra TEXT, padre_id INTEGER REFERENCES fuera(id));"
    target_sql = "CREATE TABLE t (id INTEGER PRIMARY KEY, alta DATE NOT NULL, opcional TEXT, padre_id INTEGER);"
    source, target = _endpoints(tmp_path, source_sql + "CREATE TABLE fuera (id INTEGER PRIMARY KEY);", target_sql)

    table = build_preview(source, target, DumpOptions(tables=("T",), on_error=on_error))["tables"][0]

    assert (table["table"], table["target_table"]) == ("t", "t")
    assert table["skipped_columns"] == ["extra"]
    assert table["missing_target_columns"] == ["alta"]
    assert table["outside_references"] == ["fuera"]


def test_structure_hash_ignores_rows_but_not_columns() -> None:
    base: dict[str, Any] = {
        "tables": [{"table": "t", "target_table": "t", "skipped_columns": [], "missing_target_columns": [],
                    "position": 0, "source_rows": 1, "target_rows": 0}],
        "cycles": [], "source_schema": None, "target_schema": None,
    }  # fmt: skip
    more_rows = {**base, "tables": [{**base["tables"][0], "source_rows": 99, "target_rows": 5}]}
    fewer_columns = {**base, "tables": [{**base["tables"][0], "skipped_columns": ["x"]}]}

    assert structure_hash(base) == structure_hash(more_rows)
    assert structure_hash(base) != structure_hash(fewer_columns)


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, ()), ("", ()), (" a , b,c ", ("a", "b", "c")), ("dbo.x", ("dbo.x",))]
)
def test_parse_tables(raw: str | None, expected: tuple[str, ...]) -> None:
    assert parse_tables(raw) == expected


def test_result_errors_never_carry_row_data() -> None:
    error = (
        "(sqlite3.IntegrityError) NOT NULL constraint failed: clientes.nombre\n"
        "[SQL: INSERT INTO clientes (id, nombre) VALUES (?, ?)]\n[parameters: [(1, 'secreto'), (2, None)]]"
    )
    table = SimpleNamespace(
        table_name="clientes", status="error", source_rows=2, target_rows_before=0, target_rows_after=0,
        rows_rejected=0, skipped_columns=[], load_order_position=0, in_cycle=False, error_msg=error,
    )  # fmt: skip
    constraint = SimpleNamespace(table_name="p", constraint_name="fk", status="failed", error_msg=error)
    result = SimpleNamespace(
        load_order=["clientes"], cycles_detected=[], table_results=[table], constraint_results=[constraint],
        pk_sync_results=None,
    )  # fmt: skip

    data = result_to_dict(result, report_ok=True)

    assert data["tables"][0]["error"] == "(sqlite3.IntegrityError) NOT NULL constraint failed: clientes.nombre"
    assert "secreto" not in repr(data) and "[parameters" not in repr(data)


@pytest.mark.parametrize(
    "bad",
    [
        {"source_connection": "o", "target_connection": "d", "tables": "a; DROP TABLE b"},
        {"source_connection": "o", "target_connection": "d", "chunk_size": 10},
        {"source_connection": "o", "target_connection": "d", "max_parallel_tables": 9},
        {"source_connection": "o", "target_connection": "d", "output_dir": "/x"},
    ],
)
def test_preview_params_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        validate_params(get_operation("dump_preview"), bad)


def test_apply_params_only_reference_the_preview() -> None:
    fields = set(get_operation("dump_apply").model.model_fields)

    assert fields == {"preview_run", "confirm", "confirm_truncate"}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "(1062, \"Duplicate entry 'ana@x.com' for key 'clientes.email'\")",
            "(1062, \"Duplicate entry '…' for key 'clientes.email'\")",
        ),
        ("The duplicate key value is (42, secreto).", "The duplicate key value is (…)."),
        (
            "Incorrect integer value: 'abc' for column 'id' at row 1",
            "Incorrect integer value: '…' for column 'id' at row 1",
        ),
        (
            "converting the varchar value 'secreto' to data type int.",
            "converting the varchar value '…' to data type int.",
        ),
        ("ORA-00001: unique constraint (BENCH.PK) violated", "ORA-00001: unique constraint (BENCH.PK) violated"),
        (
            'invalid input syntax for type integer: "secreto"',
            'invalid input syntax for type integer: "…"',
        ),
        (
            "Truncated value: 'secreto'.",
            "Truncated value: '…'.",
        ),
    ],
)
def test_redact_values_hides_row_values_and_keeps_names(message: str, expected: str) -> None:
    assert redact_values(message) == expected


def test_work_dir_is_removed_when_util_bbdd_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.integrations.util_bbdd.catalog import build_params

    for name in ("o.db", "d.db"):
        con = sqlite3.connect(tmp_path / name)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        con.close()
    source = Endpoint("sqlite", build_params("sqlite", {"database": str(tmp_path / "o.db")}), None)
    target = Endpoint("sqlite", build_params("sqlite", {"database": str(tmp_path / "d.db")}), None)
    options = DumpOptions()
    expected = build_preview(source, target, options)["structure_hash"]

    def boom(self: Any, **_: Any) -> Any:
        (tmp_path / "work" / "dump_report_parcial.xlsx").write_text("x")
        raise RuntimeError("fallo a mitad")

    monkeypatch.setattr("util_bbdd.dump.DumpOrchestrator.run", boom)
    with pytest.raises(RuntimeError):
        run_dump(
            source, target, options=options, expected_structure=expected, outputs_dir=tmp_path / "out",
            work_dir=tmp_path / "work",
        )  # fmt: skip

    assert not (tmp_path / "work").exists()


def _event(phase: str, current: int, total: int | None, message: str = "") -> Any:
    from util_bbdd.progress import ProgressEvent

    return ProgressEvent("dump", phase, current, total, message)


def test_dump_progress_counts_tables_and_rows() -> None:
    reported: list[tuple[str, int | None]] = []
    progress = DumpProgress(lambda message, pct: reported.append((message, pct)), lambda: False, poll_seconds=0)

    for event in (
        _event("tables", 0, 4),
        _event("rows", 500, 1000, "clientes"),
        _event("tables", 1, 4, "clientes"),
        _event("rows", 10, None, "pedidos"),
        _event("tables", 4, 4, "lineas"),
    ):
        progress(event)

    assert reported == [
        ("Volcado: 0 de 4 tablas", 0),
        ("Cargando clientes: 500 de 1000 filas (0 de 4 tablas)", 12),
        ("Volcado: 1 de 4 tablas", 25),
        ("Cargando pedidos: 10 filas (1 de 4 tablas)", 25),
        ("Volcado: 2 de 4 tablas", 50),
    ]
    assert progress.completed == ["clientes", "lineas"]


def test_cancelled_dump_keeps_finished_tables_and_undoes_the_rest(tmp_path: Path) -> None:
    """G1 con util_bbdd real: cancelar tras la primera tabla para antes de la siguiente; ``result.json`` lo cuenta."""
    data = "INSERT INTO clientes VALUES (1, 'x'); INSERT INTO pedidos VALUES (10, 1, 5); INSERT INTO sueltas VALUES (1, 'v');"
    source, target = _endpoints(tmp_path, SCHEMA + data, SCHEMA)
    options = DumpOptions()
    preview = build_preview(source, target, options)
    progress = DumpProgress(lambda *_: None, lambda: len(progress.completed) >= 1, poll_seconds=0)

    result = run_dump(
        source, target, options=options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "out",
        work_dir=tmp_path / "work", progress=progress,
    )  # fmt: skip

    assert result["cancelled"] is True and result["completed_tables"] == ["clientes"]
    assert result["tables"] == [] and result["load_order"] == preview["load_order"]
    con = sqlite3.connect(tmp_path / "d.db")
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("clientes", "pedidos", "sueltas")}  # noqa: S608
    con.close()
    assert counts == {"clientes": 1, "pedidos": 0, "sueltas": 0}


def _apply_ctx(tmp_path: Path, cancel: bool) -> Any:
    import logging

    progress: list[tuple[str, str | None, int | None]] = []
    return SimpleNamespace(
        params={"preview_run": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "confirm": "destino"},
        run_dir=tmp_path,
        logger=logging.getLogger("test"),
        progress=lambda phase, message=None, pct=None: progress.append((phase, message, pct)),
        cancel_requested=lambda: cancel,
    )


@pytest.mark.parametrize("cancel_before", [True, False])
def test_apply_job_ends_cancelled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_before: bool) -> None:
    """Cancelado antes de escribir: no llama a util_bbdd. Cancelado entre lotes: ``result.json`` y run ``cancelled``."""
    import json

    from app.domain.runs.operations import DumpPreviewParams
    from app.jobs.context import JobError
    from app.jobs.operations import dump as job

    preview = {
        "structure_hash": "h", "load_order": ["a", "b", "c"], "cycles": [], "target_connection_id": 2,
        "tables": [{"table": t, "target_table": None if t == "c" else t} for t in ("a", "b", "c")],
    }  # fmt: skip
    params = DumpPreviewParams.model_validate({"source_connection": "origen", "target_connection": "destino"})
    calls: list[Any] = []
    monkeypatch.setattr(job, "_recheck", lambda ctx, p: (params, preview))
    monkeypatch.setattr(job, "_endpoints", lambda ctx, p: (None, None))
    monkeypatch.setattr(job, "run_dump", lambda *a, **k: calls.append(k) or cancelled_result(preview, ["a"]))

    with pytest.raises(JobError) as raised:
        job.run_apply(_apply_ctx(tmp_path, cancel_before))

    assert raised.value.code == "cancelled"
    if cancel_before:
        assert calls == [] and not (tmp_path / "outputs").exists()
    else:
        assert "1 de 2 tablas cargadas" in raised.value.message
        assert isinstance(calls[0]["progress"], DumpProgress)
        result = json.loads((tmp_path / "outputs" / "dump" / "result.json").read_text(encoding="utf-8"))
        assert result["cancelled"] is True and result["completed_tables"] == ["a"]
        target = json.loads((tmp_path / "work" / "target.json").read_text(encoding="utf-8"))
        assert target == {"alias": "destino", "connection_id": 2}  # junto al diario, por si el proceso muere (G31)


def test_work_dir_is_kept_when_constraints_are_left_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Con el diario de util_bbdd pendiente (G31), ``work/`` se conserva para ``dump_restore``."""
    from app.integrations.util_bbdd.dump import JOURNAL_FILE

    source, target = _endpoints(
        tmp_path, "CREATE TABLE t (id INTEGER PRIMARY KEY);", "CREATE TABLE t (id INTEGER PRIMARY KEY);"
    )
    options = DumpOptions()
    expected = build_preview(source, target, options)["structure_hash"]

    def boom(self: Any, **_: Any) -> Any:
        (tmp_path / "work" / JOURNAL_FILE).write_text("{}")
        raise RuntimeError("no se pudieron reactivar")

    monkeypatch.setattr("util_bbdd.dump.DumpOrchestrator.run", boom)
    with pytest.raises(RuntimeError):
        run_dump(
            source, target, options=options, expected_structure=expected, outputs_dir=tmp_path / "out",
            work_dir=tmp_path / "work",
        )  # fmt: skip

    assert (tmp_path / "work" / JOURNAL_FILE).exists()


def test_journal_names_match_util_bbdd() -> None:
    from util_bbdd.dump import _constraints

    from app.domain.runs.dumps import JOURNAL_FORMAT
    from app.domain.runs.service import DUMP_JOURNAL_PATH
    from app.integrations.util_bbdd.dump import JOURNAL_FILE

    assert JOURNAL_FILE == _constraints.JOURNAL_FILENAME and DUMP_JOURNAL_PATH == f"work/{JOURNAL_FILE}"
    assert JOURNAL_FORMAT == _constraints.JOURNAL_FORMAT


def test_restore_constraints_reports_sanitised_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from util_bbdd.dump import ConstraintResult

    from app.integrations.util_bbdd.dump import restore_constraints

    _, target = _endpoints(tmp_path, "", "")
    journal = tmp_path / "constraints_journal.json"
    journal.write_text("{}")
    error = "(1452, \"Cannot add row: Duplicate entry 'secreto' for key 'PRIMARY'\")\n[parameters: ('secreto',)]"
    results = [
        ConstraintResult("clientes", "*", "postgresql", "enabled"),
        ConstraintResult("pedidos", "fk_cli", "postgresql", "failed", error),
    ]
    monkeypatch.setattr("util_bbdd.dump.restore_constraints", lambda engine, path: results)

    data = restore_constraints(target, journal)

    assert data["pending"] is True
    assert data["constraints"][0] == {"table": "clientes", "constraint": "*", "status": "enabled", "error": None}
    assert "secreto" not in repr(data) and data["constraints"][1]["status"] == "failed"


@pytest.mark.parametrize(
    "message",
    [
        # Ya saneado por util_bbdd 4.4.0 (G34): pasa igual.
        "(1062, \"Duplicate entry '…' for key 'clientes.PRIMARY'\")",
        'invalid input syntax for type integer: "…"',
    ],
)
def test_messages_already_sanitised_by_util_bbdd_pass_unchanged(message: str) -> None:
    from app.integrations.util_bbdd.dump import _clean

    assert _clean(message) == message


def test_raw_pk_sync_messages_are_still_cleaned() -> None:
    """El ``error_msg`` de los contadores PK viene de ``bulk`` y util_bbdd no lo sanea: la web sí."""
    from app.integrations.util_bbdd.dump import _clean

    raw = (
        '(psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type integer: "secreto" '
        "postgresql://u:clave@host/db\n[SQL: SELECT setval(%(s)s)]\n[parameters: {'s': 'secreto'}]"
    )

    cleaned = _clean(raw)

    assert cleaned == ('(psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type integer: "…" [url]')
    assert _clean("") is None and _clean("  \n ") is None
