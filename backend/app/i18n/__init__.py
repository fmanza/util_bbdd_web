"""Idioma de los mensajes que genera el backend (ADR-015).

Los errores de la API y los fallos de las ejecuciones no llevan texto, sino un :class:`Msg`: una clave del catálogo
(``app/i18n/catalog/``) con sus parámetros. El texto se compone al responder, en el idioma de la petición
(``Accept-Language``, :func:`negotiate`), o al leer una ejecución, en el de quien la consulta. La clave es además el
``code`` estable del *problem details*.

Los parámetros que vienen del usuario o de la base de datos (nombres de proyecto, de tabla…) se interpolan tal cual;
los que son valores de una lista cerrada (operación, permiso…) se pasan como otro :class:`Msg` y se traducen también.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token
from typing import Any, Final, Literal, get_args

Lang = Literal["es", "en"]
LANGUAGES: Final[tuple[Lang, ...]] = get_args(Lang)
DEFAULT_LANG: Final[Lang] = "es"

_lang: ContextVar[Lang] = ContextVar("lang", default=DEFAULT_LANG)


def current_lang() -> Lang:
    """Idioma de la petición en curso (``es`` fuera de una petición)."""
    return _lang.get()


def bind_lang(lang: Lang) -> Token[Lang]:
    """Fija el idioma del contexto; devuelve el token para restaurarlo con :func:`reset_lang`."""
    return _lang.set(lang)


def reset_lang(token: Token[Lang]) -> None:
    _lang.reset(token)


def negotiate(header: str | None) -> Lang:
    """Primer idioma soportado de ``Accept-Language`` por orden de preferencia (``q``); ``es`` si no hay ninguno.

    Solo cuenta el idioma principal (``en-GB`` → ``en``); una cabecera mal formada no falla: se ignora la entrada.
    """
    if not header:
        return DEFAULT_LANG
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")[:20]):
        tag, _, rest = part.strip().partition(";")
        quality = 1.0
        for param in rest.split(";"):
            name, _, value = param.strip().partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        primary = tag.strip().split("-")[0].lower()
        if primary and quality > 0:
            candidates.append((-quality, index, primary))
    for _, _, primary in sorted(candidates):
        if primary in LANGUAGES:
            return primary
    return DEFAULT_LANG


class Msg:
    """Mensaje traducible: clave del catálogo y parámetros (inmutable, serializable con :meth:`to_dict`)."""

    __slots__ = ("key", "params")

    key: str
    params: Mapping[str, object]

    def __init__(self, key: str, /, **params: object) -> None:
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "params", dict(params))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Msg es inmutable")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Msg) and other.key == self.key and dict(other.params) == dict(self.params)

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"Msg({self.key!r}, **{dict(self.params)!r})"

    def __str__(self) -> str:
        return self.render()

    def render(self, lang: Lang | None = None) -> str:
        """Texto en ``lang`` (por defecto el de la petición); ver :func:`translate`."""
        return translate(self.key, lang or current_lang(), self.params)

    def to_dict(self) -> dict[str, Any]:
        """``{"key", "params"}`` solo con tipos JSON (los :class:`Msg` anidados, también como diccionario)."""
        return {"key": self.key, "params": {name: _dump(value) for name, value in self.params.items()}}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Msg:
        params = data.get("params") or {}
        return cls(str(data["key"]), **{str(name): _load(value) for name, value in dict(params).items()})


def _dump(value: object) -> object:
    if isinstance(value, Msg):
        return {"$msg": value.to_dict()}
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _load(value: object) -> object:
    if isinstance(value, dict) and isinstance(value.get("$msg"), dict):
        return Msg.from_dict(value["$msg"])
    return value


class _Params(dict[str, object]):
    """Un marcador sin valor se deja visible (``{nombre}``) en lugar de fallar: el error nunca debe romper la respuesta."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def translate(key: str, lang: Lang, params: Mapping[str, object] | None = None) -> str:
    """Texto de ``key`` en ``lang``; si falta, en español; si tampoco existe, la propia clave."""
    from app.i18n.catalog import CATALOG

    template = CATALOG[lang].get(key) or CATALOG[DEFAULT_LANG].get(key)
    if template is None:
        return key
    values = _Params(
        {name: value.render(lang) if isinstance(value, Msg) else value for name, value in (params or {}).items()}
    )
    try:
        return template.format_map(values)
    except (ValueError, IndexError, AttributeError, KeyError):
        return template


def has_key(key: str) -> bool:
    from app.i18n.catalog import CATALOG

    return key in CATALOG[DEFAULT_LANG]


class LocalizedError(Exception):
    """Excepción interna (capa de integración, jobs) cuyo mensaje para el usuario es un :class:`Msg`.

    ``str(exc)`` da la clave, no el texto: así un log que registre la excepción no depende del idioma.
    """

    def __init__(self, msg: Msg, *args: object) -> None:
        super().__init__(msg.key, *args)
        self.msg = msg
