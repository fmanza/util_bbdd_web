"""Fase 10: ``request_id``, cabeceras de seguridad, rate limiting y ``/metrics``."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import MutableHeaders

from app.core.config import Settings, get_settings
from app.core.middleware import API_CSP, SPA_CSP, HttpMetrics, HttpMiddleware
from app.core.ratelimit import SlidingWindowLimiter
from app.core.ulid import ULID_PATTERN
from app.db.models import User
from app.main import create_app
from tests.conftest import USER_PASSWORD, do_login

AppFactory = Callable[..., TestClient]


@pytest.fixture
def app_with(migrated: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[AppFactory]:
    """Cliente con variables ``UBW_*`` adicionales (límites bajos, token de métricas…)."""
    clients: list[TestClient] = []

    def _make(**env: str) -> TestClient:
        for name, value in env.items():
            monkeypatch.setenv(f"UBW_{name.upper()}", value)
        get_settings.cache_clear()
        client = TestClient(create_app(get_settings()), base_url="https://testserver")
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


# --- request_id ------------------------------------------------------------------------------------------------


def test_request_id_is_generated_echoed_or_replaced(client: TestClient) -> None:
    generated = client.get("/api/health").headers["X-Request-ID"]
    assert ULID_PATTERN.fullmatch(generated)
    assert client.get("/api/health", headers={"X-Request-ID": "proxy-abc.123"}).headers["X-Request-ID"] == (
        "proxy-abc.123"
    )
    injected = client.get("/api/health", headers={"X-Request-ID": "bad id\n{json}"}).headers["X-Request-ID"]
    assert ULID_PATTERN.fullmatch(injected)


def test_problem_details_and_logs_carry_the_request_id(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/api/v1/auth/me", headers={"X-Request-ID": "req-00000001"})
    assert response.status_code == 401
    assert response.json()["request_id"] == "req-00000001"
    access = [r for r in caplog.records if r.name == "app.access"]
    assert access, "falta la línea de acceso"
    record = access[-1]
    assert record.__dict__["request_id"] == "req-00000001"
    assert record.__dict__["route"] == "/api/v1/auth/me"
    assert record.__dict__["status"] == 401


def test_access_log_uses_the_route_template(user_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        user_client.get("/api/v1/runs/01JABCDEFGHJKMNPQRSTVWXYZ0")
    routes = [r.__dict__["route"] for r in caplog.records if r.name == "app.access"]
    assert routes[-1] == "/api/v1/runs/{run_id}"


# --- cabeceras -------------------------------------------------------------------------------------------------


def test_api_responses_have_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    assert headers["Content-Security-Policy"] == API_CSP
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Cache-Control"] == "no-store"
    assert "camera=()" in headers["Permissions-Policy"]
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "Strict-Transport-Security" not in headers  # entorno de test


def test_spa_gets_its_csp(migrated: Settings) -> None:
    migrated.static_dir.mkdir(parents=True)
    (migrated.static_dir / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    with TestClient(create_app(migrated), base_url="https://testserver") as client:
        response = client.get("/projects/5")
    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == SPA_CSP
    assert "Cache-Control" not in response.headers
    assert "script-src 'self';" in SPA_CSP and "unsafe-eval" not in SPA_CSP


def test_route_specific_csp_is_kept(migrated: Settings) -> None:
    """Las vistas previas y el sitio HTML ponen su CSP (``sandbox``, ADR-007): el middleware no la pisa."""
    middleware = HttpMiddleware(
        lambda *_: None,  # type: ignore[arg-type]
        settings=migrated, limiter=SlidingWindowLimiter(), metrics=HttpMetrics(),
    )  # fmt: skip
    out = MutableHeaders(raw=[(b"content-security-policy", b"sandbox; default-src 'none'")])
    middleware._decorate(out, "/api/v1/runs/x/artifacts/1/preview", {"scheme": "https"}, "rid-00000001")
    assert out["Content-Security-Policy"] == "sandbox; default-src 'none'"
    # Sus subrecursos se piden desde un origen opaco: CORP same-origin los bloquearía.
    assert "Cross-Origin-Resource-Policy" not in out
    assert out["X-Content-Type-Options"] == "nosniff"


def test_hsts_only_in_production_over_https(migrated: Settings) -> None:
    production = migrated.model_copy(update={"environment": "production"})
    middleware = HttpMiddleware(
        lambda *_: None,  # type: ignore[arg-type]
        settings=production, limiter=SlidingWindowLimiter(), metrics=HttpMetrics(),
    )  # fmt: skip
    secure, plain = MutableHeaders(), MutableHeaders()
    middleware._decorate(secure, "/api/health", {"scheme": "https"}, "rid-00000001")
    middleware._decorate(plain, "/api/health", {"scheme": "http"}, "rid-00000001")
    assert secure["Strict-Transport-Security"] == "max-age=31536000"
    assert "Strict-Transport-Security" not in plain


# --- rate limiting ---------------------------------------------------------------------------------------------


def test_anonymous_api_is_limited_per_ip_and_health_is_exempt(app_with: AppFactory) -> None:
    client = app_with(rate_limit_anonymous_per_minute="3")
    statuses = [client.get("/api/v1/auth/me").status_code for _ in range(4)]
    assert statuses == [401, 401, 401, 429]
    limited = client.get("/api/v1/auth/me")
    assert limited.json()["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1
    assert limited.headers["X-Request-ID"]
    assert all(client.get("/api/health").status_code == 200 for _ in range(5))


def test_sessions_have_their_own_budget(app_with: AppFactory, user: User) -> None:
    client = app_with(rate_limit_api_per_minute="4", rate_limit_anonymous_per_minute="100")
    do_login(client, user.username, USER_PASSWORD)
    statuses = [client.get("/api/v1/auth/me").status_code for _ in range(5)]
    assert statuses.count(429) >= 1
    other = TestClient(client.app, base_url="https://testserver")
    assert other.get("/api/v1/auth/me").status_code == 401  # sin sesión: otra cuenta


def test_login_failures_per_ip_are_limited(app_with: AppFactory, user: User) -> None:
    client = app_with(rate_limit_login_failures="3")
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]

    def attempt(password: str, username: str = "ana") -> int:
        return client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}, headers={"X-CSRF-Token": csrf}
        ).status_code

    # Fallos contra cuentas distintas (el bloqueo por cuenta no los frena): a la tercera, la IP espera.
    assert [attempt("mala-contraseña-1", f"nadie{i}") for i in range(3)] == [401, 401, 401]
    assert attempt(USER_PASSWORD) == 429


def test_successful_logins_do_not_consume_the_failure_budget(app_with: AppFactory, user: User) -> None:
    client = app_with(rate_limit_login_failures="2", rate_limit_login_per_minute="100")
    for _ in range(4):
        do_login(client, user.username, USER_PASSWORD)


def test_login_attempts_per_minute(app_with: AppFactory, user: User) -> None:
    client = app_with(rate_limit_login_per_minute="2", rate_limit_anonymous_per_minute="100")
    do_login(client, user.username, USER_PASSWORD)
    do_login(client, user.username, USER_PASSWORD)
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": USER_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert "Retry-After" in response.headers


def test_uploads_have_their_own_limit(app_with: AppFactory, user: User) -> None:
    client = app_with(rate_limit_uploads_per_hour="1")
    do_login(client, user.username, USER_PASSWORD)
    project = client.post("/api/v1/projects", json={"name": "Carga", "description": ""}).json()["id"]

    def send() -> int:
        return client.post(
            f"/api/v1/projects/{project}/uploads", files={"file": ("a.csv", b"id\n1\n", "text/csv")}
        ).status_code

    assert send() == 201
    assert send() == 429
    assert client.get(f"/api/v1/projects/{project}/uploads").status_code == 200


def test_rate_limit_can_be_disabled(app_with: AppFactory) -> None:
    client = app_with(rate_limit_enabled="false", rate_limit_anonymous_per_minute="1")
    assert {client.get("/api/v1/auth/me").status_code for _ in range(3)} == {401}


# --- métricas --------------------------------------------------------------------------------------------------


def test_metrics_disabled_without_token(client: TestClient) -> None:
    assert client.get("/metrics").status_code == 404


def test_metrics_need_the_bearer_token(app_with: AppFactory, user_client: TestClient) -> None:
    client = app_with(metrics_token="m" * 32)
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer otro"}).status_code == 401
    client.get("/api/v1/runs/01JABCDEFGHJKMNPQRSTVWXYZ0")
    response = client.get("/metrics", headers={"Authorization": f"Bearer {'m' * 32}"})
    assert response.status_code == 200
    body = response.text
    assert "ubw_http_requests_total" in body
    assert 'route="/api/v1/runs/{run_id}"' in body
    assert "01JABCDEFGHJKMNPQRSTVWXYZ0" not in body
    assert "ubw_info{" in body
    assert "ubw_worker_heartbeat_age_seconds -1.0" in body
    assert response.headers["Content-Security-Policy"] == API_CSP


# --- cookies y exposición ---------------------------------------------------------------------------------------


def test_cookies_use_the_host_prefix_only_with_tls(client: TestClient, app_with: AppFactory) -> None:
    client.get("/api/v1/auth/csrf")
    assert "__Host-ubw_csrf" in client.cookies
    development = app_with(environment="development")
    development.get("/api/v1/auth/csrf")
    assert "ubw_csrf" in development.cookies
    assert "__Host-ubw_csrf" not in development.cookies


def test_openapi_is_not_published_in_production(migrated: Settings) -> None:
    production = migrated.model_copy(update={"environment": "production", "app_secret_key": "k" * 40})
    with TestClient(create_app(production), base_url="https://testserver") as client:
        assert client.get("/api/openapi.json").status_code == 404
        assert client.get("/api/docs").status_code == 404
