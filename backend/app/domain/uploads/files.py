"""Lectura segura de los ficheros de la carga bulk (CSV y Excel), sin util_bbdd.

El fichero viene del usuario: se comprueba que el contenido corresponde a la extensión (texto sin NUL para CSV, ZIP
con ``xl/workbook.xml`` para ``.xlsx``), se limita el tamaño descomprimido de un ``.xlsx`` (*zip bombs*) y el número
de filas. Las macros (``.xlsm``) no se admiten.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Final, Literal

from app.domain.uploads.errors import UploadContentError, UploadTypeError

Kind = Literal["csv", "xlsx"]
KINDS: Final[dict[str, Kind]] = {".csv": "csv", ".xlsx": "xlsx"}
ENCODINGS: Final = ("utf-8", "cp1252", "latin-1")
DELIMITERS: Final = (",", ";", "\t", "|")
_SNIFF_BYTES: Final = 64 * 1024
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def display_name(filename: str | None) -> str:
    """Nombre que se muestra: solo la última parte, sin caracteres de control y acotado (nunca es una ruta)."""
    name = PurePath((filename or "").replace("\\", "/")).name
    return _CONTROL.sub("", name).strip()[:255] or "fichero"


def kind_for(filename: str | None) -> Kind:
    """Tipo por la extensión.

    Raises:
        UploadTypeError: No es ``.csv`` ni ``.xlsx``.
    """
    kind = KINDS.get(PurePath(display_name(filename)).suffix.lower())
    if kind is None:
        raise UploadTypeError()
    return kind


def check_content(path: Path, kind: Kind, *, max_uncompressed: int) -> None:
    """Comprueba que el contenido es del tipo declarado.

    Raises:
        UploadContentError: Binario disfrazado de CSV, ZIP que no es un libro de Excel, con macros o que descomprimido
            supera ``max_uncompressed`` bytes.
    """
    if kind == "csv":
        with path.open("rb") as handle:
            head = handle.read(_SNIFF_BYTES)
        if b"\x00" in head:
            raise UploadContentError("El CSV contiene bytes nulos: no parece un fichero de texto.")
        return
    if not zipfile.is_zipfile(path):
        raise UploadContentError("El .xlsx no es un libro de Excel (no es un ZIP).")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "xl/workbook.xml" not in names:
            raise UploadContentError("El .xlsx no es un libro de Excel.")
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise UploadContentError("No se admiten libros con macros.")
        if sum(info.file_size for info in archive.infolist()) > max_uncompressed:
            raise UploadContentError("El .xlsx descomprimido es demasiado grande.")


@dataclass(frozen=True)
class ReadOptions:
    """Cómo leer el fichero: hoja de Excel o separador y codificación del CSV (``None`` = automático)."""

    sheet: str | None = None
    delimiter: str | None = None
    encoding: str | None = None


def _csv_text(path: Path, encoding: str | None) -> tuple[str, str]:
    """Texto del CSV y la codificación usada (la primera que funcione si no se indica)."""
    raw = path.read_bytes()
    for candidate in (encoding,) if encoding else ENCODINGS:
        try:
            return raw.decode("utf-8-sig" if candidate == "utf-8" else candidate), candidate
        except (UnicodeDecodeError, LookupError):
            continue
    raise UploadContentError(f"El CSV no está en {encoding or 'UTF-8, Windows-1252 ni Latin-1'}.")


def _delimiter(text: str, delimiter: str | None) -> str:
    if delimiter:
        return delimiter
    try:
        return csv.Sniffer().sniff(text[:_SNIFF_BYTES], delimiters="".join(DELIMITERS)).delimiter
    except csv.Error:
        return ","


def sheet_names(path: Path) -> list[str]:
    """Hojas de un ``.xlsx`` (lectura en modo solo lectura, sin cargar celdas)."""
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        raise UploadContentError("No se pudo abrir el libro de Excel.") from None
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def read_frame(path: Path, kind: Kind, options: ReadOptions, *, max_rows: int, nrows: int | None = None) -> Any:
    """``DataFrame`` del fichero (todas las columnas como las infiere pandas; celdas vacías → ``NaN``/``NULL``).

    Args:
        nrows: Leer solo las primeras filas (vista de columnas); ``None`` = todo, con el límite ``max_rows``.

    Raises:
        UploadContentError: No se puede leer, la hoja no existe, no tiene columnas o supera ``max_rows``.
    """
    import pandas as pd

    limit = nrows if nrows is not None else max_rows + 1
    try:
        if kind == "csv":
            text, _ = _csv_text(path, options.encoding)
            frame = pd.read_csv(io.StringIO(text), sep=_delimiter(text, options.delimiter), nrows=limit)
        else:
            sheets = sheet_names(path)
            sheet = options.sheet or sheets[0]
            if sheet not in sheets:
                raise UploadContentError(f"El libro no tiene la hoja «{sheet}».")
            frame = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", nrows=limit)
    except UploadContentError:
        raise
    except Exception as exc:  # errores de pandas/openpyxl: solo el tipo, nunca el contenido
        raise UploadContentError(f"No se pudo leer el fichero ({type(exc).__name__}).") from None
    if len(frame.columns) == 0:
        raise UploadContentError("El fichero no tiene columnas.")
    if nrows is None and len(frame) > max_rows:
        raise UploadContentError(f"El fichero tiene más de {max_rows} filas.")
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame


def describe(path: Path, kind: Kind, options: ReadOptions) -> dict[str, Any]:
    """Hojas (Excel), separador y codificación detectados (CSV), columnas y primeras filas para el mapeo."""
    frame = read_frame(path, kind, options, max_rows=0, nrows=5)
    info: dict[str, Any] = {"columns": list(frame.columns), "sample": _records(frame)}
    if kind == "xlsx":
        info["sheets"] = sheet_names(path)
    else:
        text, encoding = _csv_text(path, options.encoding)
        info["encoding"] = encoding
        info["delimiter"] = _delimiter(text, options.delimiter)
    return info


def _records(frame: Any) -> list[list[Any]]:
    """Filas JSON (``NaN`` → ``None``, el resto como texto acotado)."""
    rows: list[list[Any]] = []
    for row in frame.itertuples(index=False):
        rows.append([None if _is_nan(v) else str(v)[:200] for v in row])
    return rows


def _is_nan(value: Any) -> bool:
    try:
        return bool(value != value)  # NaN es distinto de sí mismo
    except (TypeError, ValueError):
        return False
