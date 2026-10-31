"""Fase 9: nombres y tipos de fichero, lectura (codificación, separador, límite de filas), mapeo de columnas, columnas
obligatorias y recuento por PK compuesta."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.domain.uploads.errors import UploadContentError, UploadTypeError
from app.domain.uploads.files import ReadOptions, display_name, kind_for, read_frame
from app.integrations.util_bbdd.bulk import _count_matches, _required_columns, _resolve_mapping, verify


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


def test_describe_an_empty_excel_sheet_still_lists_the_sheets(tmp_path: Path) -> None:
    """Hoja vacía (también la primera): columnas vacías y la lista de hojas, para poder elegir otra; cargarla, no."""
    from openpyxl import Workbook

    from app.domain.uploads.files import describe

    book = Workbook()
    book.active.title = "Vacía"
    datos = book.create_sheet("Datos")
    datos.append(["id", "nombre"])
    datos.append([7, "ana"])
    path = tmp_path / "libro.xlsx"
    book.save(path)

    empty = describe(path, "xlsx", ReadOptions())
    full = describe(path, "xlsx", ReadOptions(sheet="Datos"))

    assert empty == {"columns": [], "sample": [], "sheets": ["Vacía", "Datos"]}
    assert full["columns"] == ["id", "nombre"] and full["sheets"] == ["Vacía", "Datos"]
    with pytest.raises(UploadContentError, match="no tiene columnas"):
        read_frame(path, "xlsx", ReadOptions(), max_rows=10)  # la vista previa y la carga la siguen rechazando
    csv = tmp_path / "vacio.csv"
    csv.write_text("", encoding="utf-8")
    with pytest.raises(UploadContentError):
        describe(csv, "csv", ReadOptions())  # un CSV vacío sigue siendo un error


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


@pytest.mark.parametrize(
    ("operation", "before", "after", "committed", "matches", "expected"),
    [
        ("insert", 10, 13, 3, None, True),
        ("insert", 10, 12, 3, None, False),  # una fila no llegó: el contador de util_bbdd no cuadra
        ("update", 10, 10, 5, 4, True),
        ("update", 10, 11, 5, 4, False),
        ("delete", 10, 7, 5, 3, True),  # dos claves del fichero no existían: cuentan como enviadas
        ("delete", 10, 8, 5, 3, False),
        ("delete", 10, 7, 5, None, None),
    ],
)
def test_verify_compares_the_target_count_with_util_bbdd(
    operation: str, before: int, after: int, committed: int, matches: int | None, expected: bool | None
) -> None:
    assert verify(operation, before, after, committed, matches) is expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("plan", "expected"),
    [
        ({"workers": 4, "atomic": False}, False),
        ({"workers": 1, "atomic": True}, True),
        ({"workers": 1, "atomic": False}, False),  # p. ej. commit_every_n_chunks: manda util_bbdd
        ({"workers": 4}, False),  # vista previa anterior a la 1.5.0: por los hilos
        ({"workers": 1}, True),
        (None, True),
    ],
)
def test_plan_atomic_comes_from_util_bbdd(plan: dict[str, object] | None, expected: bool) -> None:
    from app.domain.runs.bulks import plan_atomic

    assert plan_atomic({"parallel": plan}) is expected


def test_require_atomic_is_passed_to_util_bbdd() -> None:
    """Sin aceptar la no atomicidad, util_bbdd fuerza un hilo aunque su plan cambie entre la vista previa y la carga."""
    from app.integrations.util_bbdd.bulk import BulkOptions, _parallel

    assert _parallel(BulkOptions(table="t", operation="insert")) is None
    strict = _parallel(BulkOptions(table="t", operation="insert", parallel=True, require_atomic=True))
    loose = _parallel(BulkOptions(table="t", operation="insert", parallel=True))
    assert (strict.mode, strict.require_atomic, loose.require_atomic) == ("auto", True, False)


def _sqlite_target(tmp_path: Path) -> tuple[object, Path]:
    import sqlite3

    from app.integrations.util_bbdd.bulk import Target
    from app.integrations.util_bbdd.catalog import build_params

    database = tmp_path / "destino.db"
    con = sqlite3.connect(database)
    con.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT)")
    con.execute("INSERT INTO clientes VALUES (1, 'ana')")
    con.commit()
    con.close()
    return Target("sqlite", build_params("sqlite", {"database": str(database)}), None), database


def test_cancelled_atomic_load_is_undone_entirely(tmp_path: Path) -> None:
    """G1 con util_bbdd real: cancelar tras el primer lote de una carga de una sola transacción no deja nada."""
    import sqlite3

    import pandas as pd

    from app.integrations.util_bbdd.bulk import BulkOptions, build_bulk_preview, run_bulk
    from app.integrations.util_bbdd.progress import RunProgress

    target, database = _sqlite_target(tmp_path)
    frame = pd.DataFrame({"id": range(2, 12), "nombre": [f"n{i}" for i in range(10)]})
    options = BulkOptions(table="clientes", operation="insert", chunk_size=2)
    preview = build_bulk_preview(target, frame, options, outputs_dir=tmp_path / "p", work_dir=tmp_path / "w")  # type: ignore[arg-type]
    reported: list[tuple[str, int | None]] = []
    progress = RunProgress(
        lambda message, pct: reported.append((message, pct)),
        lambda: any(pct for _, pct in reported),  # cancela en cuanto hay filas enviadas
        ["rows"],
        {"rows": "Filas"},
        poll_seconds=0,
        total=10,  # por bloques util_bbdd no sabe el total: lo da la vista previa
    )

    result = run_bulk(
        target, frame, options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "o",  # type: ignore[arg-type]
        progress=progress,
    )  # fmt: skip

    assert reported[0] == ("Filas: 0 de 10 (clientes)", 0) and reported[1][0] == "Filas: 2 de 10 (clientes)"
    assert (result["cancelled"], result["error"], result["committed"], result["verified"]) == (True, None, 0, None)
    assert result["target_rows_before"] == result["target_rows_after"] == 1
    con = sqlite3.connect(database)
    try:
        assert con.execute("SELECT COUNT(*) FROM clientes").fetchone() == (1,)
    finally:
        con.close()


def _result(
    operation: str, rows: int, committed: int, rejected: int, before: int, after: int | None
) -> dict[str, object]:
    return {"operation": operation, "rows": rows, "committed": committed, "rejected": rejected,
            "target_rows_before": before, "target_rows_after": after, "verified": None}  # fmt: skip


@pytest.mark.parametrize(
    ("result", "applied", "message"),
    [
        # Caso real: todas las filas con PK duplicada; util_bbdd las cuenta como confirmadas (G37).
        (_result("insert", 400, 400, 400, 7386111, 7386111), 0,
         "INSERT terminado sin cargar ninguna fila: las 400 se apartaron en rechazos.csv"),
        (_result("insert", 3, 3, 1, 10, 12), 2, "INSERT terminado: 2 filas insertadas, 1 filas apartadas en rechazos.csv"),
        (_result("delete", 5, 5, 0, 10, 7), 3, "DELETE terminado: 3 filas borradas"),
        (_result("update", 5, 5, 1, 10, 10), 4,
         "UPDATE terminado: 4 filas actualizadas (enviadas sin rechazo), 1 filas apartadas en rechazos.csv"),
        (_result("insert", 0, 0, 0, 10, 10), 0, "INSERT terminado: 0 filas insertadas"),
        # Sin recuento posterior (read_timeout): lo que util_bbdd confirmó, menos las apartadas.
        (_result("delete", 5, 5, 1, 10, None), 4,
         "DELETE terminado: 4 filas borradas, 1 filas apartadas en rechazos.csv; no se pudo contar el destino tras la "
         "carga (¿read_timeout de la conexión?): compruébalo en la tabla"),
    ],
)  # fmt: skip
def test_bulk_message_counts_applied_rows_not_committed(result: dict[str, object], applied: int, message: str) -> None:
    from app.jobs.operations.bulk import applied_rows, result_message

    assert applied_rows(result) == applied
    assert result_message(result) == message


def test_failed_count_after_the_load_leaves_it_unverified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hotfix: el recuento tras una carga ya confirmada falla (read_timeout de MariaDB): resultado sin verificar."""
    import sqlite3

    import pandas as pd

    from app.integrations.util_bbdd import bulk
    from app.integrations.util_bbdd.bulk import BulkOptions, build_bulk_preview, run_bulk
    from app.jobs.operations.bulk import applied_rows, result_message

    target, database = _sqlite_target(tmp_path)
    frame = pd.DataFrame({"id": [2, 3], "nombre": ["eva", "luis"]})
    options = BulkOptions(table="clientes", operation="insert")
    preview = build_bulk_preview(target, frame, options, outputs_dir=tmp_path / "p", work_dir=tmp_path / "w")  # type: ignore[arg-type]
    real_count = bulk._count
    calls: list[int] = []

    def count(engine: object, table: object) -> int:
        calls.append(1)
        if len(calls) == 2:  # el de después de cargar
            raise TimeoutError("Lost connection to server during query")
        return real_count(engine, table)

    monkeypatch.setattr(bulk, "_count", count)
    result = run_bulk(target, frame, options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "o")  # type: ignore[arg-type]

    assert (result["error"], result["committed"], result["target_rows_before"]) == (None, 2, 1)
    assert (result["target_rows_after"], result["verified"]) == (None, None)
    assert applied_rows(result) == 2
    assert result_message(result) == (
        "INSERT terminado: 2 filas insertadas; no se pudo contar el destino tras la carga (¿read_timeout de la "
        "conexión?): compruébalo en la tabla"
    )
    con = sqlite3.connect(database)
    try:
        assert con.execute("SELECT COUNT(*) FROM clientes").fetchone() == (3,)
    finally:
        con.close()


def test_override_identity_is_passed_only_to_the_insert() -> None:
    from app.integrations.util_bbdd.bulk import BulkOptions, _call

    calls: list[tuple[str, dict[str, object]]] = []
    crud = SimpleNamespace(
        bulk_insert_from_df=lambda df, table, **kw: calls.append(("insert", kw)),
        bulk_update_from_df=lambda df, table, **kw: calls.append(("update", kw)),
        bulk_delete_from_df=lambda df, table, **kw: calls.append(("delete", kw)),
    )

    _call(crud, BulkOptions(table="t", operation="insert", override_identity=True), None, "t", dry_run=True)
    _call(crud, BulkOptions(table="t", operation="update", override_identity=True), None, "t", dry_run=True)

    assert calls == [
        ("insert", {"override_identity": True, "exclude_autoincrement_pk": False, "dry_run": True}),
        ("update", {"dry_run": True}),
    ]


def test_exclude_autoincrement_pk_is_passed_only_to_the_insert() -> None:
    from app.integrations.util_bbdd.bulk import BulkOptions, _call

    calls: list[dict[str, object]] = []
    crud = SimpleNamespace(bulk_insert_from_df=lambda df, table, **kw: calls.append(kw))

    _call(crud, BulkOptions(table="t", operation="insert", exclude_autoincrement_pk=True), None, "t", dry_run=True)

    assert calls == [{"override_identity": False, "exclude_autoincrement_pk": True, "dry_run": True}]


def test_autoincrement_pk_uses_the_util_bbdd_criterion() -> None:
    """``is_identity_pk`` de util_bbdd: ``autoincrement is True`` o con ``identity`` (no ``"auto"``, como SQLite)."""
    from sqlalchemy import Identity

    from app.integrations.util_bbdd.bulk import BulkOptions, _autoincrement_pk, _counts_pk, _excluded

    meta = MetaData()
    auto = Table("a", meta, Column("id", Integer, primary_key=True, autoincrement=True), Column("n", String(5)))
    identity = Table("i", meta, Column("id", Integer, Identity(), primary_key=True))
    natural = Table("n", meta, Column("id", Integer, primary_key=True))  # autoincrement="auto", como refleja SQLite
    insert = BulkOptions(table="a", operation="insert", exclude_autoincrement_pk=True)
    frame = SimpleNamespace(columns=["id", "n"])

    assert (_autoincrement_pk(auto), _autoincrement_pk(identity), _autoincrement_pk(natural)) == (["id"], ["id"], [])
    assert _excluded(auto, insert) == {"id"}
    assert _excluded(auto, BulkOptions(table="a", operation="update", exclude_autoincrement_pk=True)) == set()
    assert not _counts_pk(auto, insert, frame, ["id"])  # excluida: no hay duplicados posibles por PK
    assert _counts_pk(auto, BulkOptions(table="a", operation="insert"), frame, ["id"])


def test_exclude_and_override_identity_are_incompatible(tmp_path: Path) -> None:
    import pandas as pd

    from app.integrations.util_bbdd.bulk import BulkOptions, build_bulk_preview

    target, _ = _sqlite_target(tmp_path)
    options = BulkOptions(table="clientes", operation="insert", exclude_autoincrement_pk=True, override_identity=True)

    preview = build_bulk_preview(
        target, pd.DataFrame({"id": [7], "nombre": ["eva"]}), options,  # type: ignore[arg-type]
        outputs_dir=tmp_path / "p", work_dir=tmp_path / "w",
    )  # fmt: skip

    assert preview["sql_file"] is None
    assert preview["errors"] == [
        "«Que la BD asigne los ids» y «Conservar los valores de columnas identity» son incompatibles: elige una."
    ]


def test_preview_reports_the_autoincrement_pk_and_skips_matches_when_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La vista previa dice qué PK asigna la BD; excluida, no cuenta coincidencias. SQLite no la marca: se simula."""
    import pandas as pd

    from app.integrations.util_bbdd import bulk
    from app.integrations.util_bbdd.bulk import BulkOptions, build_bulk_preview

    target, _ = _sqlite_target(tmp_path)  # clientes con id = 1
    monkeypatch.setattr(bulk, "_autoincrement_pk", lambda table: ["id"])
    frame = pd.DataFrame({"id": [1], "nombre": ["eva"]})

    def preview(exclude: bool) -> dict[str, object]:
        options = BulkOptions(table="clientes", operation="insert", exclude_autoincrement_pk=exclude)
        out = tmp_path / ("e" if exclude else "n")
        return build_bulk_preview(target, frame, options, outputs_dir=out / "p", work_dir=out / "w")  # type: ignore[arg-type]

    kept, excluded = preview(False), preview(True)

    assert (kept["autoincrement_pk"], kept["matches"]) == (["id"], 1)  # el id 1 ya existe
    assert (excluded["autoincrement_pk"], excluded["matches"], excluded["errors"]) == (["id"], None, [])


def test_identity_always_columns_of_the_mapped_frame() -> None:
    from sqlalchemy import Identity

    from app.integrations.util_bbdd.bulk import _identity_always

    table = Table(
        "t", MetaData(),
        Column("id", Integer, Identity(always=True), primary_key=True),
        Column("otro", Integer, Identity(always=False)),
        Column("nombre", String(10)),
    )  # fmt: skip

    assert _identity_always(table, ["id", "otro", "nombre"]) == ["id"]
    assert _identity_always(table, ["nombre"]) == []


@pytest.mark.parametrize("override", [False, True])
def test_identity_always_without_override_is_a_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: bool
) -> None:
    """util_bbdd rechaza en el modo seco las columnas GENERATED ALWAYS sin override_identity: error de validación."""
    import pandas as pd

    from app.integrations.util_bbdd import bulk
    from app.integrations.util_bbdd.bulk import BulkOptions, build_bulk_preview

    target, _ = _sqlite_target(tmp_path)
    # SQLite no tiene columnas identity: se simula que «id» es GENERATED ALWAYS (PostgreSQL).
    monkeypatch.setattr(bulk, "_identity_always", lambda table, columns: [c for c in ["id"] if c in set(columns)])
    frame = pd.DataFrame({"id": [7], "nombre": ["eva"]})
    options = BulkOptions(table="clientes", operation="insert", override_identity=override)

    preview = build_bulk_preview(target, frame, options, outputs_dir=tmp_path / "p", work_dir=tmp_path / "w")  # type: ignore[arg-type]

    if override:
        assert preview["errors"] == [] and preview["sql_file"] and preview["identity_always"] == ["id"]
    else:
        assert preview["sql_file"] is None
        assert preview["errors"] == [
            "Columnas GENERATED ALWAYS AS IDENTITY: id. Activa «Conservar los valores de columnas identity» o ponlas "
            "en «(no cargar)» para que las asigne la BD."
        ]


def test_sync_pk_results_are_json_ready_and_sanitized() -> None:
    from decimal import Decimal

    from app.integrations.util_bbdd.bulk import _sync_pk

    asked: list[list[str]] = []
    results = [
        SimpleNamespace(column_name="id", status="synced", max_value=Decimal("1000400"), error_msg=None),
        SimpleNamespace(column_name="id2", status="error", max_value=None,
                        error_msg="permission denied for sequence t_id_seq\nDETAIL: fila (1, 'secreto')"),
    ]  # fmt: skip
    crud = SimpleNamespace(sync_pk_sequences=lambda tables: asked.append(tables) or results)

    synced, failed = _sync_pk(crud, "s.t")

    assert asked == [["s.t"]]
    assert synced == {"column": "id", "status": "synced", "max_value": 1000400, "error": None}
    assert failed["status"] == "error" and "secreto" not in failed["error"]
    assert "permission denied" in failed["error"]


def test_bulk_message_warns_when_the_pk_counter_was_not_adjusted() -> None:
    from app.jobs.operations.bulk import result_message

    result = {**_result("insert", 2, 2, 0, 10, 12),
              "pk_sync": [{"column": "id", "status": "error", "max_value": None, "error": "permission denied"}]}  # fmt: skip

    assert result_message(result) == (
        "INSERT terminado: 2 filas insertadas; no se pudo ajustar el contador de la PK: permission denied"
    )


def test_insert_without_the_autoincrement_primary_key(tmp_path: Path) -> None:
    """Un insert sin la columna de la PK (la asigna la BD): vista previa y carga, sin contar coincidencias por PK."""
    import sqlite3

    import pandas as pd

    from app.integrations.util_bbdd.bulk import BulkOptions, Target, build_bulk_preview, run_bulk
    from app.integrations.util_bbdd.catalog import build_params

    database = tmp_path / "destino.db"
    con = sqlite3.connect(database)
    con.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT)")
    con.execute("INSERT INTO clientes (nombre) VALUES ('ana')")
    con.commit()
    con.close()
    target = Target("sqlite", build_params("sqlite", {"database": str(database)}), None)
    frame = pd.DataFrame({"nombre": ["eva", "luis"]})
    options = BulkOptions(table="clientes", operation="insert")

    preview = build_bulk_preview(target, frame, options, outputs_dir=tmp_path / "p", work_dir=tmp_path / "w")
    result = run_bulk(target, frame, options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "o")

    assert preview["errors"] == [] and preview["matches"] is None
    assert (result["error"], result["matches"], result["target_rows_after"]) == (None, None, 3)
    assert result["pk_sync"] == []  # SQLite: util_bbdd no ajusta contadores
    con = sqlite3.connect(database)
    try:
        assert con.execute("SELECT id, nombre FROM clientes ORDER BY id").fetchall() == [
            (1, "ana"), (2, "eva"), (3, "luis"),
        ]  # fmt: skip
    finally:
        con.close()


@pytest.mark.parametrize("operation", ["insert", "update"])
def test_preview_sql_with_dates_as_text(tmp_path: Path, operation: str) -> None:
    """G48 (util_bbdd 5.2.0): las fechas de un CSV llegan como texto; el SQL del modo seco las escribe tal cual."""
    import sqlite3

    from app.integrations.util_bbdd.bulk import BulkOptions, Target, build_bulk_preview
    from app.integrations.util_bbdd.catalog import build_params

    database = tmp_path / "destino.db"
    con = sqlite3.connect(database)
    con.execute("CREATE TABLE eventos (id INTEGER PRIMARY KEY, alta DATETIME, dia DATE)")
    con.execute("INSERT INTO eventos VALUES (1, '2026-01-01 00:00:00', '2026-01-01')")
    con.commit()
    con.close()
    target = Target("sqlite", build_params("sqlite", {"database": str(database)}), None)
    csv = tmp_path / "eventos.csv"
    csv.write_text("id;alta;dia\n1;2026-10-18 20:45:24.000;2026-10-18\n", encoding="utf-8")
    frame = read_frame(csv, "csv", ReadOptions(), max_rows=10)
    assert isinstance(frame["alta"].iloc[0], str)  # pandas no convierte las fechas del CSV

    preview = build_bulk_preview(
        target, frame, BulkOptions(table="eventos", operation=operation),  # type: ignore[arg-type]
        outputs_dir=tmp_path / "p", work_dir=tmp_path / "w",
    )  # fmt: skip

    assert preview["errors"] == [] and preview["sql_file"] == f"sql/carga_{operation}.sql"
    sql = (tmp_path / "p" / preview["sql_file"]).read_text(encoding="utf-8")
    assert "'2026-10-18 20:45:24.000'" in sql and "'2026-10-18'" in sql


@pytest.mark.parametrize(
    ("cancel_before", "committed", "message"),
    [
        (True, 0, "antes de escribir en el destino"),
        (False, 0, "la carga se deshizo entera"),
        (False, 4, "quedan confirmadas 4 filas de las particiones terminadas"),
    ],
)
def test_apply_job_ends_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_before: bool, committed: int, message: str
) -> None:
    import json
    import logging
    from types import SimpleNamespace

    from app.domain.runs.operations import BulkPreviewParams
    from app.jobs.context import JobError
    from app.jobs.operations import bulk as job

    params = BulkPreviewParams.model_validate(
        {"upload": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "target_connection": "destino", "table": "t", "operation": "insert"}
    )
    preview = {"operation": "insert", "rows": 6, "table": "t", "structure_hash": "h"}
    calls: list[dict[str, object]] = []
    result = {
        "operation": "insert", "rows": 6, "committed": committed, "target_rows_before": 0, "target_rows_after": committed,
        "cancelled": True, "error": None, "partitions": [], "rejected": 0, "verified": None,
    }  # fmt: skip
    monkeypatch.setattr(job, "_recheck", lambda ctx, p: (params, preview))
    monkeypatch.setattr(job, "_source", lambda ctx, p: (tmp_path / "f.csv", "csv", {}))
    monkeypatch.setattr(job, "_frames", lambda *a: None)
    monkeypatch.setattr(job, "run_bulk", lambda *a, **k: calls.append(k) or result)
    ctx = SimpleNamespace(
        params={"preview_run": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "confirm": "destino"},
        run_dir=tmp_path,
        logger=logging.getLogger("test"),
        progress=lambda *a, **k: None,
        cancel_requested=lambda: cancel_before,
        connection_params=lambda alias: ("sqlite", {}),
    )

    with pytest.raises(JobError) as raised:
        job.run_apply(ctx)  # type: ignore[arg-type]

    assert raised.value.code == "cancelled" and message in raised.value.message
    if cancel_before:
        assert calls == []
    else:
        assert calls[0]["progress"] is not None
        written = json.loads((tmp_path / "outputs" / "bulk" / "result.json").read_text(encoding="utf-8"))
        assert written["cancelled"] is True
