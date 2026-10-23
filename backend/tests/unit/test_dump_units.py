"""Fase 8: orden de carga por FK y ciclos (como util_bbdd), huella de estructura, tablas y errores saneados."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd.dump import (
    DumpOptions,
    Endpoint,
    _required,
    build_preview,
    load_order,
    parse_tables,
    redact_values,
    result_to_dict,
    run_dump,
    structure_hash,
)


def test_load_order_chain_independent_and_self_reference() -> None:
    order, cycles = load_order(
        ["lineas", "clientes", "pedidos", "sueltas", "arbol"],
        {"lineas": ["pedidos"], "pedidos": ["clientes", "fuera"], "arbol": ["arbol"]},
    )

    # Cola en el orden recibido; una FK a sí misma o a una tabla fuera del volcado no cuenta.
    assert order == ["clientes", "sueltas", "arbol", "pedidos", "lineas"]
    assert cycles == []


def test_load_order_puts_cycles_last_as_components() -> None:
    order, cycles = load_order(
        ["a", "b", "c", "x", "y", "z"],
        {"a": ["c"], "b": ["a"], "c": ["b"], "x": ["y"], "y": ["x"], "z": ["a"]},
    )

    assert order == ["a", "b", "c", "x", "y", "z"]  # ninguna es raíz: todas al final, en su orden
    assert sorted(map(sorted, cycles)) == [["a", "b", "c", "z"], ["x", "y"]]


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


def test_required_target_columns() -> None:
    source = {"id"}

    assert _required({"name": "alta", "nullable": False, "default": None}, source) is True
    assert _required({"name": "alta", "nullable": True, "default": None}, source) is False
    assert _required({"name": "alta", "nullable": False, "default": "now()"}, source) is False
    assert _required({"name": "id2", "nullable": False, "default": None, "autoincrement": True}, source) is False
    assert _required({"name": "ID", "nullable": False, "default": None}, source) is False


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

    def boom(self: Any) -> Any:
        (tmp_path / "work" / "dump_report_parcial.xlsx").write_text("x")
        raise RuntimeError("fallo a mitad")

    monkeypatch.setattr("util_bbdd.dump.DumpOrchestrator.run", boom)
    with pytest.raises(RuntimeError):
        run_dump(
            source, target, options=options, expected_structure=expected, outputs_dir=tmp_path / "out",
            work_dir=tmp_path / "work",
        )  # fmt: skip

    assert not (tmp_path / "work").exists()
