"""Fase 9: nombres y tipos de fichero, lectura (codificación, separador, límite de filas), mapeo de columnas, columnas
obligatorias y recuento por PK compuesta."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.domain.uploads.errors import UploadContentError, UploadTypeError
from app.domain.uploads.files import ReadOptions, display_name, kind_for, read_frame
from app.integrations.util_bbdd.bulk import _count_matches, _required_columns, _resolve_mapping


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.csv", "passwd.csv"),
        ("C:\\Users\\x\\datos.xlsx", "datos.xlsx"),
        ("con\x00trol\x1f.csv", "control.csv"),
        ("", "fichero"),
        (None, "fichero"),
    ],
)
def test_display_name_is_never_a_path(raw: str | None, expected: str) -> None:
    assert display_name(raw) == expected


def test_kind_for() -> None:
    assert kind_for("A.CSV") == "csv" and kind_for("b.xlsx") == "xlsx"
    for bad in ("c.xls", "d.xlsm", "e.txt", "f"):
        with pytest.raises(UploadTypeError):
            kind_for(bad)


def test_read_csv_encodings_delimiters_and_limits(tmp_path: Path) -> None:
    latin = tmp_path / "latin.csv"
    latin.write_bytes("id|nombre\n1|Begoña\n".encode("cp1252"))
    big = tmp_path / "big.csv"
    big.write_text("id\n" + "\n".join(str(i) for i in range(11)) + "\n", encoding="utf-8")

    frame = read_frame(latin, "csv", ReadOptions(), max_rows=10)

    assert list(frame.columns) == ["id", "nombre"] and frame.iloc[0]["nombre"] == "Begoña"
    with pytest.raises(UploadContentError, match="más de 10 filas"):
        read_frame(big, "csv", ReadOptions(), max_rows=10)
    with pytest.raises(UploadContentError):
        read_frame(latin, "csv", ReadOptions(encoding="utf-8"), max_rows=10)


def test_resolve_mapping_by_name_and_explicit() -> None:
    by_name = _resolve_mapping(["ID", "Nombre", "otra"], ["id", "nombre", "email"], {})
    explicit = _resolve_mapping(["cliente", "mail"], ["id", "nombre", "email"], {"cliente": "NOMBRE", "mail": "x"})

    assert by_name["resolved"] == {"ID": "id", "Nombre": "nombre"} and by_name["ignored"] == ["otra"]
    assert explicit["resolved"] == {"cliente": "nombre"} and explicit["unknown"] == ["x"]
    assert _resolve_mapping(["a"], ["a"], {"b": "a"})["missing_in_file"] == ["b"]


def test_required_columns_skip_defaults_nullables_and_autoincrement() -> None:
    meta = MetaData()
    table = Table(
        "t", meta,
        Column("id", Integer, primary_key=True),
        Column("nombre", String(10), nullable=False),
        Column("alta", String(10), nullable=False, server_default="x"),
        Column("nota", String(10)),
    )  # fmt: skip

    assert _required_columns(table) == ["nombre"]


def test_count_matches_with_composite_key() -> None:
    engine = create_engine("sqlite://")
    meta = MetaData()
    table = Table("l", meta, Column("a", Integer, primary_key=True), Column("b", Integer, primary_key=True))
    meta.create_all(engine)
    with engine.begin() as connection:
        connection.execute(table.insert(), [{"a": 1, "b": 1}, {"a": 1, "b": 2}, {"a": 2, "b": 1}])

    distinct = [(i, i) for i in range(10, 400)] + [(1, 1), (1, 2)]  # más de un lote (200 con PK compuesta)
    repeated = [(1, 1), (1, 2), (9, 9)] * 150  # claves repetidas en lotes distintos: cuentan una vez

    assert _count_matches(engine, table, distinct, ["a", "b"]) == 2
    assert _count_matches(engine, table, repeated, ["a", "b"]) == 2
    assert _count_matches(engine, table, [], ["a"]) == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"upload": "x", "target_connection": "d", "table": "t", "operation": "insert"},
        {"upload": "01JABCDEFGHJKMNPQRSTVWXYZ0", "target_connection": "d", "table": "s.t", "operation": "insert"},
        {"upload": "01JABCDEFGHJKMNPQRSTVWXYZ0", "target_connection": "d", "table": "t", "operation": "merge"},
        {"upload": "01JABCDEFGHJKMNPQRSTVWXYZ0", "target_connection": "d", "table": "t", "operation": "insert",
         "mapping": {"a\x00": "b"}},
        {"upload": "01JABCDEFGHJKMNPQRSTVWXYZ0", "target_connection": "d", "table": "t", "operation": "insert",
         "delimiter": "::"},
    ],
)  # fmt: skip
def test_preview_params_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        validate_params(get_operation("bulk_preview"), bad)
