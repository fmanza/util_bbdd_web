"""Ficheros grandes en la carga: lectura de CSV por bloques, vista previa con SQL de muestra y carga por bloques
(``bulk_*_from_chunks`` de util_bbdd) sobre SQLite real."""

from __future__ import annotations

import sqlite3
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domain.uploads.errors import UploadContentError
from app.domain.uploads.files import ReadOptions, describe, iter_frames
from app.integrations.util_bbdd import bulk
from app.integrations.util_bbdd.bulk import BulkOptions, Target, build_bulk_preview, run_bulk
from app.integrations.util_bbdd.catalog import build_params
from app.integrations.util_bbdd.progress import RunProgress


def _csv(tmp_path: Path, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / "f.csv"
    path.write_bytes(text.encode(encoding))
    return path


def test_iter_frames_reads_a_csv_in_chunks_with_the_row_limit(tmp_path: Path) -> None:
    path = _csv(tmp_path, " id ;nombre\n" + "".join(f"{i};n{i}\n" for i in range(5)))

    chunks = list(iter_frames(path, "csv", ReadOptions(), max_rows=10, chunk_rows=2))

    assert [len(c) for c in chunks] == [2, 2, 1]
    assert all(list(c.columns) == ["id", "nombre"] for c in chunks)  # separador detectado y nombres limpios
    with pytest.raises(UploadContentError, match="más de 4 filas"):
        list(iter_frames(path, "csv", ReadOptions(), max_rows=4, chunk_rows=2))


def test_iter_frames_of_a_header_only_csv_gives_one_empty_chunk(tmp_path: Path) -> None:
    (chunk,) = iter_frames(_csv(tmp_path, "id,nombre\n"), "csv", ReadOptions(), max_rows=10)

    assert list(chunk.columns) == ["id", "nombre"] and chunk.empty


def test_the_encoding_is_checked_on_the_whole_file_not_on_its_head(tmp_path: Path) -> None:
    """Un carácter de Windows-1252 más allá de lo que se mira para el separador: no es UTF-8."""
    path = _csv(tmp_path, "id,nombre\n" + "1,ana\n" * 20_000 + "2,Begoña\n", "cp1252")

    info = describe(path, "csv", ReadOptions())
    last = list(iter_frames(path, "csv", ReadOptions(), max_rows=100_000))[-1]

    assert (info["encoding"], info["delimiter"]) == ("cp1252", ",")
    assert last.iloc[-1]["nombre"] == "Begoña"
    with pytest.raises(UploadContentError, match="no está en utf-8"):
        list(iter_frames(path, "csv", ReadOptions(encoding="utf-8"), max_rows=100_000))


def _target(tmp_path: Path) -> tuple[Target, Path]:
    database = tmp_path / "destino.db"
    con = sqlite3.connect(database)
    con.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT)")
    con.executemany("INSERT INTO clientes VALUES (?, ?)", [(1, "ana"), (2, "luis")])
    con.commit()
    con.close()
    return Target("sqlite", build_params("sqlite", {"database": str(database)}), None), database


def _rows(database: Path) -> list[tuple[object, ...]]:
    con = sqlite3.connect(database)
    try:
        return con.execute("SELECT id, nombre FROM clientes ORDER BY id").fetchall()
    finally:
        con.close()


def test_preview_counts_every_chunk_and_writes_a_sample_of_the_sql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, database = _target(tmp_path)
    path = _csv(tmp_path, "id,nombre\n" + "".join(f"{i},n{i}\n" for i in (1, 2, 3, 4, 5)))
    frames = partial(iter_frames, path, "csv", ReadOptions(), max_rows=10, chunk_rows=2)
    monkeypatch.setattr(bulk, "SQL_SAMPLE_ROWS", 1)  # salen del primer bloque
    options = BulkOptions(table="clientes", operation="update")

    preview = build_bulk_preview(target, frames, options, outputs_dir=tmp_path / "p", work_dir=tmp_path / "w")

    assert (preview["rows"], preview["matches"], preview["sql_sample_rows"]) == (5, 2, 1)  # 1 y 2 existen
    sql = (tmp_path / "p" / preview["sql_file"]).read_text(encoding="utf-8")
    assert sql.startswith("-- SQL de muestra: primeras 1 de 5 filas\n")
    assert sql.count("UPDATE") == 1
    assert len(preview["sample"]) == 2  # la muestra sale del primer bloque
    assert _rows(database) == [(1, "ana"), (2, "luis")]


def test_preview_of_a_small_file_has_the_whole_sql(tmp_path: Path) -> None:
    target, _ = _target(tmp_path)
    frames = partial(iter_frames, _csv(tmp_path, "id,nombre\n7,eva\n"), "csv", ReadOptions(), max_rows=10)

    preview = build_bulk_preview(
        target, frames, BulkOptions(table="clientes", operation="insert"),
        outputs_dir=tmp_path / "p", work_dir=tmp_path / "w",
    )  # fmt: skip

    assert preview["sql_sample_rows"] is None
    assert not (tmp_path / "p" / preview["sql_file"]).read_text(encoding="utf-8").startswith("--")


def test_chunked_insert_isolates_the_rejected_rows_in_one_transaction(tmp_path: Path) -> None:
    """Sin plan paralelo la carga va por ``bulk_insert_from_chunks``: los rechazos (``isolate``) funcionan igual."""
    target, database = _target(tmp_path)
    path = _csv(tmp_path, "id,nombre\n3,eva\n4,leo\n2,repetido\n5,max\n6,sol\n")
    frames = partial(iter_frames, path, "csv", ReadOptions(), max_rows=10, chunk_rows=2)
    options = BulkOptions(table="clientes", operation="insert", on_error="isolate", chunk_size=1)
    preview = build_bulk_preview(target, frames, options, outputs_dir=tmp_path / "p", work_dir=tmp_path / "w")
    reported: list[tuple[str, int | None]] = []
    progress = RunProgress(lambda m, p: reported.append((m, p)), lambda: False, ["rows"], {"rows": "Filas"}, total=5)

    result = run_bulk(
        target, frames, options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "o",
        progress=progress,
    )  # fmt: skip

    assert (result["rows"], result["rejected"], result["error"], result["matches"]) == (5, 1, None, 1)
    assert (result["target_rows_before"], result["target_rows_after"]) == (2, 6)
    assert _rows(database)[2:] == [(3, "eva"), (4, "leo"), (5, "max"), (6, "sol")]
    assert (tmp_path / "o" / "rejects" / "rechazos.csv").read_text(encoding="utf-8").count("repetido") == 1
    assert reported[-1][0].startswith("Filas: 5 de 5") and reported[-1][1] == 99


def test_chunked_delete_and_parallel_update(tmp_path: Path) -> None:
    """Borrado por bloques (``bulk_delete_from_chunks``) y, con plan paralelo, el fichero junto en memoria."""
    target, database = _target(tmp_path)
    path = _csv(tmp_path, "id,nombre\n1,ANA\n2,LUIS\n")
    frames = partial(iter_frames, path, "csv", ReadOptions(), max_rows=10, chunk_rows=1)

    def apply(options: BulkOptions) -> dict[str, object]:
        out = tmp_path / options.operation
        preview = build_bulk_preview(target, frames, options, outputs_dir=out / "p", work_dir=out / "w")
        return run_bulk(target, frames, options, expected_structure=preview["structure_hash"], outputs_dir=out / "o")

    updated = apply(BulkOptions(table="clientes", operation="update", parallel=True))
    assert (updated["rows"], updated["error"], _rows(database)) == (2, None, [(1, "ANA"), (2, "LUIS")])

    deleted = apply(BulkOptions(table="clientes", operation="delete"))
    assert (deleted["rows"], deleted["matches"], deleted["verified"], _rows(database)) == (2, 2, True, [])


def test_run_progress_uses_the_known_total_when_util_bbdd_has_none() -> None:
    progress = RunProgress(lambda m, p: None, lambda: False, ["rows"], {"rows": "Filas"}, total=200)
    event = SimpleNamespace(phase="rows", current=50, total=None, fraction=None, message="clientes")

    assert (progress.message(event), progress.percent(event)) == ("Filas: 50 de 200 (clientes)", 25)
