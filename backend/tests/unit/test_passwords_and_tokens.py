from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.security import (
    MissingSecretKeyError,
    hash_token,
    new_session_token,
    require_secret_key,
    session_csrf_token,
    tokens_match,
)
from app.domain.identity.errors import PasswordPolicyError
from app.domain.identity.passwords import MAX_PASSWORD_LENGTH, check_policy, hash_password, verify_password


def test_hash_is_argon2id_and_salted() -> None:
    first = hash_password("correcto-caballo-bateria")
    second = hash_password("correcto-caballo-bateria")

    assert first.startswith("$argon2id$")
    assert first != second
    assert "correcto-caballo-bateria" not in first


def test_verify_accepts_right_and_rejects_wrong_password() -> None:
    stored = hash_password("correcto-caballo-bateria")

    assert verify_password("correcto-caballo-bateria", stored) == (True, None)
    assert verify_password("incorrecto", stored)[0] is False


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("corta", "al menos 12"),
        ("x" * (MAX_PASSWORD_LENGTH + 1), "superar"),
        ("Usuario-Largo1", "nombre de usuario"),
    ],
)
def test_policy_rejects(password: str, fragment: str) -> None:
    with pytest.raises(PasswordPolicyError) as info:
        check_policy(password, username="usuario-largo1", min_length=12)

    assert fragment in (info.value.detail or "")


def test_policy_accepts_valid_password() -> None:
    check_policy("una-frase-de-paso-larga", username="ana", min_length=12)


def test_session_token_is_256_bits_and_only_hash_is_stored() -> None:
    token = new_session_token()

    assert len(token) >= 43
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_csrf_token_is_bound_to_session_and_key() -> None:
    a = Settings(app_secret_key="clave-a")  # type: ignore[arg-type]
    b = Settings(app_secret_key="clave-b")  # type: ignore[arg-type]

    assert session_csrf_token(a, "s1") == session_csrf_token(a, "s1")
    assert session_csrf_token(a, "s1") != session_csrf_token(a, "s2")
    assert session_csrf_token(a, "s1") != session_csrf_token(b, "s1")
    assert tokens_match("abc", "abc")
    assert not tokens_match("abc", "abd")


def test_production_requires_secret_key() -> None:
    with pytest.raises(MissingSecretKeyError):
        require_secret_key(Settings(environment="production"))
    require_secret_key(Settings(environment="production", app_secret_key="k"))  # type: ignore[arg-type]
    require_secret_key(Settings(environment="development"))


def test_cookie_secure_except_in_development() -> None:
    assert Settings(environment="production").cookie_secure
    assert Settings(environment="test").cookie_secure
    assert not Settings(environment="development").cookie_secure
