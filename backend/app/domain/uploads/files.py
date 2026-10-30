"""Lectura segura de los ficheros de la carga bulk (CSV y Excel), sin util_bbdd.

El fichero viene del usuario: se comprueba que el contenido corresponde a la extensión (texto sin NUL para CSV, ZIP
con ``xl/workbook.xml`` para ``.xlsx``), se limita el tamaño descomprimido de un ``.xlsx`` (*zip bombs*) y el número
de filas. Las macros (``.xlsm``) no se admiten.

Un CSV nunca se carga entero en memoria: la codificación se comprueba decodificándolo por bloques y ``iter_frames`` lo
lee en bloques de ``CHUNK_ROWS`` filas (vista previa y carga de ficheros grandes). Un Excel se lee entero (su tamaño lo
acota ``upload_max_uncompressed_mb``).
"""

from __future__ import annotations

import codecs
import csv
import re
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Final, Literal

from app.domain.uploads.errors import NoColumnsError, UploadContentError, UploadTypeError

Kind = Literal["csv", "xlsx"]
KINDS: Final[dict[str, Kind]] = {".csv": "csv", ".xlsx": "xlsx"}
ENCODINGS: Final = ("utf-8", "cp1252", "latin-1")
DELIMITERS: Final = (",", ";", "\t", "|")
#: Filas de cada bloque al leer un CSV por partes (vista previa y carga).
CHUNK_ROWS: Final = 50_000
_SNIFF_BYTES: Final = 64 * 1024
_DECODE_BLOCK: Final = 1024 * 1024
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


def _codec(encoding: str) -> str:
    return "utf-8-sig" if encoding == "utf-8" else encoding  # sin el BOM en la primera columna


def _decodes(path: Path, encoding: str) -> bool:
    """Si el fichero entero se decodifica con ``encoding`` (por bloques, sin cargarlo en memoria)."""
    try:
        decoder = codecs.getincrementaldecoder(_codec(encoding))()
        with path.open("rb") as handle:
            while block := handle.read(_DECODE_BLOCK):
                decoder.decode(block)
        decoder.decode(b"", final=True)
    except (UnicodeDecodeError, LookupError):
        return False
    return True


def _csv_format(path: Path, options: ReadOptions) -> tuple[str, str]:
    """Codificación (la indicada o la primera de ``ENCODINGS`` que funcione) y separador (el indicado o detectado)."""
    candidates = (options.encoding,) if options.encoding else ENCODINGS
    encoding = next((c for c in candidates if _decodes(path, c)), None)
    if encoding is None:
        raise UploadContentError(f"El CSV no está en {options.encoding or 'UTF-8, Windows-1252 ni Latin-1'}.")
    if options.delimiter:
        return encoding, options.delimiter
    with path.open(encoding=_codec(encoding), newline="") as handle:
        head = handle.read(_SNIFF_BYTES)
    try:
        return encoding, csv.Sniffer().sniff(head, delimiters="".join(DELIMITERS)).delimiter
    except csv.Error:
        return encoding, ","


@contextmanager
def _reading() -> Iterator[None]:
    """Errores de pandas/openpyxl como ``UploadContentError``: solo el tipo, nunca el contenido."""
    try:
        yield
    except UploadContentError:
        raise
    except Exception as exc:
        raise UploadContentError(f"No se pudo leer el fichero ({type(exc).__name__}).") from None


def _read_csv(path: Path, csv_format: tuple[str, str], **kwargs: Any) -> Any:
    import pandas as pd

    encoding, delimiter = csv_format
    return pd.read_csv(path, sep=delimiter, encoding=_codec(encoding), **kwargs)


def _columns(frame: Any) -> Any:
    """``frame`` con los nombres de columna limpios; sin columnas (p. ej. una hoja vacía), ``NoColumnsError``."""
    if len(frame.columns) == 0:
        raise NoColumnsError("El fichero no tiene columnas.")
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame


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
    with _reading():
        if kind == "csv":
            frame = _read_csv(path, _csv_format(path, options), nrows=limit)
        else:
            sheets = sheet_names(path)
            sheet = options.sheet or sheets[0]
            if sheet not in sheets:
                raise UploadContentError(f"El libro no tiene la hoja «{sheet}».")
            frame = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", nrows=limit)
    frame = _columns(frame)
    if nrows is None and len(frame) > max_rows:
        raise UploadContentError(f"El fichero tiene más de {max_rows} filas.")
    return frame


def iter_frames(
    path: Path, kind: Kind, options: ReadOptions, *, max_rows: int, chunk_rows: int = CHUNK_ROWS
) -> Iterator[Any]:
    """Bloques ``DataFrame`` del fichero, con las mismas columnas; siempre al menos uno (vacío si no hay filas).

    Un CSV se lee por bloques de ``chunk_rows`` filas sin cargarlo entero; un Excel da un solo bloque (``read_frame``).
    Cada llamada vuelve a abrir el fichero: sirve para recorrerlo varias veces (contar, cargar).

    Raises:
        UploadContentError: Como ``read_frame``; las filas de más se detectan al llegar a ellas.
    """
    if kind != "csv":
        yield read_frame(path, kind, options, max_rows=max_rows)
        return
    csv_format = _csv_format(path, options)
    with _reading():
        header = _columns(_read_csv(path, csv_format, nrows=0))
        reader = _read_csv(path, csv_format, chunksize=chunk_rows)
    rows, chunks = 0, 0
    with reader:
        while True:
            with _reading():
                frame = next(reader, None)
            if frame is None:
                break
            rows, chunks = rows + len(frame), chunks + 1
            if rows > max_rows:
                raise UploadContentError(f"El fichero tiene más de {max_rows} filas.")
            yield _columns(frame)
    if not chunks:
        yield header


def describe(path: Path, kind: Kind, options: ReadOptions) -> dict[str, Any]:
    """Hojas (Excel), separador y codificación detectados (CSV), columnas y primeras filas para el mapeo.

    Una hoja de Excel vacía no es un error aquí: columnas vacías y la lista de hojas, para poder elegir otra (también si
    la vacía es la primera). La vista previa y la carga la siguen rechazando (``read_frame``).
    """
    try:
        frame = read_frame(path, kind, options, max_rows=0, nrows=5)
    except NoColumnsError:
        if kind != "xlsx":
            raise
        return {"columns": [], "sample": [], "sheets": sheet_names(path)}
    info: dict[str, Any] = {"columns": list(frame.columns), "sample": _records(frame)}
    if kind == "xlsx":
        info["sheets"] = sheet_names(path)
    else:
        info["encoding"], info["delimiter"] = _csv_format(path, options)
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
