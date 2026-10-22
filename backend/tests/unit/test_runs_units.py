"""Piezas puras del motor de ejecuciones: ULID, workspace, ZIP, ``RunAuditSink`` y catálogo de operaciones."""

from __future__ import annotations

import io
import json
import threading
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from util_bbdd.audit import AuditEvent, AuditSink

from app.core.ulid import is_ulid, new_ulid
from app.domain.runs.errors import RunParamsError, UnknownOperationError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd.audit_sink import RunAuditSink
from app.workspace.layout import (
    UnsafePathError,
    ensure_layout,
    run_relative_path,
    safe_path,
    scan_artifacts,
    write_json_atomic,
    zip_stream,
)

# --- ULID --------------------------------------------------------------------------------------------------------


def test_ulid_format_and_time_order() -> None:
    first = new_ulid(1_700_000_000_000)
    second = new_ulid(1_700_000_000_001)

    assert is_ulid(first) and len(first) == 26
    assert first < second
    assert len({new_ulid() for _ in range(1000)}) == 1000
    assert not is_ulid("../../etc/passwd")


# --- workspace ---------------------------------------------------------------------------------------------------


def test_run_relative_path_uses_only_ids() -> None:
    path = run_relative_path(3, 7, datetime(2026, 10, 20, 8, 5, 9, tzinfo=UTC), "noop", "01JABCDEFGHJKMNPQRSTVWXYZ0")

    assert path == "users/3/projects/7/runs/20261020-080509_noop_01JABCDEFGHJKMNPQRSTVWXYZ0"
    with pytest.raises(UnsafePathError):
        run_relative_path(3, 7, datetime.now(UTC), "../x", "01J")


@pytest.mark.parametrize("relative", ["../fuera.txt", "/etc/passwd", "a/../../b", "", "C:\\Windows\\win.ini", "."])
def test_safe_path_rejects_escapes(tmp_path: Path, relative: str) -> None:
    with pytest.raises(UnsafePathError):
        safe_path(tmp_path / "run", relative)


def test_safe_path_accepts_inside(tmp_path: Path) -> None:
    assert safe_path(tmp_path, "outputs/html/a.html") == (tmp_path / "outputs" / "html" / "a.html").resolve()


def _sample_run(directory: Path) -> None:
    ensure_layout(directory)
    write_json_atomic(directory / "run.json", {"id": "x", "estado": "ok"})
    (directory / "logs" / "run.log").write_text('{"msg": "hola"}\n', encoding="utf-8")
    (directory / "outputs" / "html" / "a.html").write_text("<p>a</p>", encoding="utf-8")
    (directory / "outputs" / "graphs" / "g.svg").write_text("<svg/>", encoding="utf-8")
    (directory / "outputs" / "html" / ".tmp-x.json").write_text("{}", encoding="utf-8")
    (directory / "inputs" / "subida.csv").write_text("a,b", encoding="utf-8")


def test_scan_artifacts_classifies_and_hashes(tmp_path: Path) -> None:
    _sample_run(tmp_path)

    files = {f.path: f for f in scan_artifacts(tmp_path)}

    assert set(files) == {"run.json", "logs/run.log", "outputs/html/a.html", "outputs/graphs/g.svg"}
    assert files["run.json"].kind == "manifest"
    assert files["logs/run.log"].kind == "log"
    assert files["outputs/graphs/g.svg"].mime == "image/svg+xml"
    assert len(files["outputs/html/a.html"].sha256) == 64
    assert json.loads((tmp_path / "run.json").read_text(encoding="utf-8")) == {"id": "x", "estado": "ok"}


def test_zip_stream_contains_files_under_prefix(tmp_path: Path) -> None:
    _sample_run(tmp_path)

    data = b"".join(
        zip_stream(tmp_path, ["run.json", "outputs/html/a.html", "outputs/html/no-existe.html"], prefix="run-x")
    )

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == ["run-x/outputs/html/a.html", "run-x/run.json"]
        assert archive.read("run-x/outputs/html/a.html") == b"<p>a</p>"


def test_zip_stream_rejects_traversal(tmp_path: Path) -> None:
    _sample_run(tmp_path)

    with pytest.raises(UnsafePathError):
        b"".join(zip_stream(tmp_path / "outputs", ["../run.json"], prefix="x"))


# --- RunAuditSink (contrato de util_bbdd.audit.AuditSink) ---------------------------------------------------------


def _event(n: int) -> AuditEvent:
    return AuditEvent.now(
        source="bulk", kind="operation", status="ok", engine="sqlite", target=f"t{n}", operation="INSERT", rows=n,
        message="Key (id)=(42) already exists",
    )  # fmt: skip


def test_run_audit_sink_follows_util_bbdd_contract(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "run.log"
    sink = RunAuditSink(log)

    assert isinstance(sink, AuditSink)
    sink.write([])
    assert not log.exists()
    threads = [threading.Thread(target=sink.write, args=([_event(i), _event(i + 100)],)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    sink.close()
    sink.close()
    with pytest.raises(ValueError):
        sink.write([_event(1)])

    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 40
    assert all(line["logger"] == "util_bbdd.audit" and line["source"] == "bulk" for line in lines)
    assert all("message" not in line for line in lines)
    assert sink.counts["ok"] == 40


# --- catálogo de operaciones -------------------------------------------------------------------------------------


def test_noop_params_defaults_and_validation() -> None:
    spec = get_operation("noop")

    assert validate_params(spec, {}) == {"steps": 3, "step_seconds": 1.0, "fail": False, "connection": None}
    assert {p.name: p.type for p in spec.params} == {
        "steps": "integer",
        "step_seconds": "float",
        "fail": "boolean",
        "connection": "connection",
    }
    assert spec.connection_params({"connection": "origen"}) == ["origen"]
    with pytest.raises(RunParamsError) as info:
        validate_params(spec, {"steps": 99, "extra": 1})
    locs = {tuple(e["loc"]) for e in info.value.extra["errors"]}  # type: ignore[attr-defined]
    assert ("body", "params", "steps") in locs
    assert ("body", "params", "extra") in locs
    with pytest.raises(UnknownOperationError):
        get_operation("rm -rf")
