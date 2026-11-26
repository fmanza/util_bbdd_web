"""Idioma de los mensajes del backend (ADR-015): catálogo completo y sin textos sueltos en el código."""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import app
from app.core.errors import AppError
from app.i18n import LocalizedError, Msg, negotiate, translate
from app.i18n.catalog import CATALOG, MODULES

APP_DIR = Path(__file__).resolve().parents[2] / "app"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _all_modules() -> None:
    for info in pkgutil.walk_packages(app.__path__, "app."):
        importlib.import_module(info.name)


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found |= {sub, *_subclasses(sub)}
    return found


def test_same_keys_and_placeholders_in_both_languages() -> None:
    for module in MODULES:
        es, en = module.ES, module.EN
        assert set(es) == set(en), f"{module.__name__}: claves distintas {set(es) ^ set(en)}"
        for key in es:
            assert set(_PLACEHOLDER.findall(es[key])) == set(_PLACEHOLDER.findall(en[key])), (
                f"{module.__name__}: marcadores distintos en {key}"
            )


def test_no_key_is_defined_twice() -> None:
    seen: dict[str, str] = {}
    for module in MODULES:
        for key in module.ES:
            assert key not in seen, f"{key} en {module.__name__} y en {seen[key]}"
            seen[key] = module.__name__


def test_every_app_error_has_a_title() -> None:
    _all_modules()
    missing = [
        f"{cls.__module__}.{cls.__name__} -> {cls.title.key}"
        for cls in _subclasses(AppError)
        if cls.__module__.startswith("app.") and cls.title.key not in CATALOG["es"]
    ]
    assert missing == [], f"Títulos sin entrada en el catálogo: {missing}"


def _calls(tree: ast.AST) -> list[ast.Call]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def test_every_msg_key_exists() -> None:
    """``Msg("clave")`` con una clave literal debe estar en el catálogo (las claves compuestas se comprueban aparte)."""
    missing = []
    for path in APP_DIR.rglob("*.py"):
        for call in _calls(ast.parse(path.read_text(encoding="utf-8"))):
            if _name(call.func) == "Msg" and call.args and isinstance(call.args[0], ast.Constant):
                key = call.args[0].value
                if isinstance(key, str) and key not in CATALOG["es"]:
                    missing.append(f"{path.relative_to(APP_DIR)}:{call.lineno} {key}")
    assert missing == [], f"Claves sin entrada en el catálogo: {missing}"


def _is_text(node: ast.expr) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(node, ast.JoinedStr)


def test_user_facing_errors_carry_a_msg() -> None:
    """Ningún error que llega al usuario se construye con un texto: ``AppError``, ``LocalizedError`` y ``JobError``
    reciben un :class:`Msg`, y los errores por campo (``"msg": …``) también."""
    _all_modules()
    localized = {cls.__name__ for cls in _subclasses(AppError) | _subclasses(LocalizedError)} | {
        "AppError",
        "LocalizedError",
    }
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls(tree):
            name = _name(call.func)
            args = list(call.args) + [k.value for k in call.keywords if k.arg in {"detail", "message", "msg"}]
            if name in localized and any(_is_text(a) for a in args):
                offenders.append(f"{path.relative_to(APP_DIR)}:{call.lineno} {name}")
            if name == "JobError" and any(_is_text(a) for a in args[1:]):
                offenders.append(f"{path.relative_to(APP_DIR)}:{call.lineno} JobError")
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if isinstance(key, ast.Constant) and key.value == "msg" and value is not None and _is_text(value):
                        offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno} errors[].msg")
    assert offenders == [], f"Errores con texto en lugar de Msg (ADR-015): {offenders}"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "es"),
        ("", "es"),
        ("en", "en"),
        ("en-GB,en;q=0.9,es;q=0.8", "en"),
        ("es;q=0.1, en;q=0.9", "en"),
        ("fr, de", "es"),
        ("fr, en;q=0.5", "en"),
        ("en;q=0, es", "es"),
        ("en;q=abc, es", "es"),
        ("*", "es"),
    ],
)
def test_negotiate(header: str | None, expected: str) -> None:
    assert negotiate(header) == expected


def test_translate_falls_back() -> None:
    assert translate("no.such.key", "en") == "no.such.key"
    assert translate("jobs.timeout", "en", {}) == "Exceeded the maximum time ({limit} s)."
    assert translate("jobs.timeout", "en", {"limit": 3}) == "Exceeded the maximum time (3 s)."


def test_msg_round_trip_with_nested_msg() -> None:
    msg = Msg("jobs.unexpected", exc_type=Msg("jobs.interrupted"))
    restored = Msg.from_dict(msg.to_dict())
    assert restored == msg
    assert restored.render("en") == "Unexpected error (The worker stopped during the run.)."


def test_app_error_code_and_title_from_class_name() -> None:
    class SampleThingError(AppError):
        status = 409

    assert SampleThingError.code == "sample_thing"
    assert SampleThingError.title == Msg("title.sample_thing")
    assert SampleThingError().error_code == "sample_thing"
    assert SampleThingError(Msg("jobs.interrupted")).error_code == "jobs.interrupted"
