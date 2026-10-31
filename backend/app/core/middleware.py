"""Middleware HTTP (ASGI puro, no rompe el *streaming* de SSE ni de los ZIP): ``request_id``, cabeceras de
seguridad, rate limiting de la API, línea de acceso JSON y métricas por ruta (Fase 10).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.errors import problem
from app.core.ratelimit import Limit, SlidingWindowLimiter
from app.core.request_context import REQUEST_ID_HEADER, accept_or_generate, bind_request_id, reset_request_id

access_logger = logging.getLogger("app.access")

SESSION_COOKIES: Final = ("__Host-ubw_session", "ubw_session")
#: SPA: sin scripts inline ni de terceros. Mantine inyecta ``<style>`` y usa ``style=``: ``'unsafe-inline'`` en
#: estilos. Los iframes de la SPA (vistas previas y sitio HTML) son del mismo origen y traen su propia CSP.
SPA_CSP: Final = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; frame-src 'self'; worker-src 'self' blob:; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
API_CSP: Final = "default-src 'none'; frame-ancestors 'none'"
_COMMON: Final = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "same-origin"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
)
#: Solo en respuestas sin CSP propia: el sitio HTML y las vistas previas se cargan en un iframe ``sandbox`` con
#: origen opaco, y sus subrecursos (JS, CSS, imágenes) serían *cross-origin* para ``CORP: same-origin``.
_CORP: Final = ("Cross-Origin-Resource-Policy", "same-origin")
#: Subidas de ficheros: carga bulk y plantillas de documento (ADR-011), con su propio límite por hora.
UPLOAD_PATH: Final = re.compile(r"^/api/v1/(projects/\d+/(uploads|document-templates)|admin/document-templates)$")
_UNLIMITED: Final = frozenset({"/api/health", "/metrics"})


class HttpMetrics:
    """Métricas HTTP en un registro propio por aplicación (los tests crean varias)."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.requests = Counter(
            "ubw_http_requests", "Peticiones HTTP por método, ruta (plantilla) y estado.",
            ["method", "route", "status"], registry=self.registry,
        )  # fmt: skip
        self.duration = Histogram(
            "ubw_http_request_duration_seconds", "Duración de las peticiones HTTP por método y ruta (plantilla).",
            ["method", "route"], registry=self.registry,
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        )  # fmt: skip
        self.rate_limited = Counter(
            "ubw_rate_limited", "Peticiones rechazadas con 429 por regla.", ["rule"], registry=self.registry
        )


def client_ip(scope: Scope) -> str:
    """IP del cliente (la de ``X-Forwarded-For`` si uvicorn confía en el proxy: ``FORWARDED_ALLOW_IPS``)."""
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


def _route_template(scope: Scope) -> str:
    """Ruta plantilla (``/api/v1/runs/{run_id}``): sin identificadores en métricas ni en logs."""
    raw = str(scope.get("path", ""))
    route = scope.get("route")
    template, path_format = getattr(route, "path", None), getattr(route, "path_format", None)
    if isinstance(template, str) and isinstance(path_format, str):
        # En routers anidados ``route.path`` no lleva el prefijo (``/api/v1``): se toma de la URL real.
        try:
            rendered = path_format.format(**scope.get("path_params", {}))
        except (KeyError, IndexError, ValueError):
            rendered = None
        if rendered is not None and raw.endswith(rendered):
            return raw[: len(raw) - len(rendered)] + template
        return template
    if raw.startswith("/assets/"):
        return "/assets"
    return "/api/<unmatched>" if raw.startswith("/api/") else "<spa>"


class HttpMiddleware:
    """Una sola capa para todo lo transversal de cada petición HTTP."""

    def __init__(self, app: ASGIApp, *, settings: Settings, limiter: SlidingWindowLimiter, metrics: HttpMetrics):
        self.app = app
        self.settings = settings
        self.limiter = limiter
        self.metrics = metrics
        self.api_rule = Limit(settings.rate_limit_api_per_minute, 60)
        self.anonymous_rule = Limit(settings.rate_limit_anonymous_per_minute, 60)
        self.upload_rule = Limit(settings.rate_limit_uploads_per_hour, 3600)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        request_id = accept_or_generate(headers.get(REQUEST_ID_HEADER))
        token = bind_request_id(request_id)
        started = time.perf_counter()
        path = str(scope.get("path", ""))
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                self._decorate(MutableHeaders(scope=message), path, scope, request_id)
            await send(message)

        try:
            limited = self._rate_limit(scope, headers, path)
            if limited is not None:
                rule, retry_after = limited
                self.metrics.rate_limited.labels(rule).inc()
                response = problem(
                    429, "Demasiadas peticiones", f"Espera {retry_after} s antes de reintentar.", code="rate_limited"
                )
                response.headers["Retry-After"] = str(retry_after)
                await response(scope, receive, send_wrapper)
            else:
                await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            route = _route_template(scope)
            method = str(scope.get("method", ""))
            self.metrics.requests.labels(method, route, str(status)).inc()
            self.metrics.duration.labels(method, route).observe(elapsed)
            if path.startswith("/api/") and path != "/api/health":
                access_logger.info(
                    "Petición",
                    extra={"method": method, "route": route, "status": status, "ms": round(elapsed * 1000, 1)},
                )
            reset_request_id(token)

    def _rate_limit(self, scope: Scope, headers: Headers, path: str) -> tuple[str, int] | None:
        if not self.settings.rate_limit_enabled or not path.startswith("/api/") or path in _UNLIMITED:
            return None
        cookie = next((v for name in SESSION_COOKIES if (v := _cookie(headers, name))), None)
        if cookie:
            key = "s:" + hashlib.sha256(cookie.encode("utf-8")).hexdigest()[:24]
            rule, name = self.api_rule, "api"
        else:
            key, rule, name = "ip:" + client_ip(scope), self.anonymous_rule, "anonymous"
        if scope.get("method") == "POST" and UPLOAD_PATH.match(path):
            wait = self.limiter.hit("up:" + key, self.upload_rule)
            if wait is not None:
                return "uploads", wait
        wait = self.limiter.hit(key, rule)
        return (name, wait) if wait is not None else None

    def _decorate(self, out: MutableHeaders, path: str, scope: Scope, request_id: str) -> None:
        """Cabeceras de seguridad que la ruta no haya puesto (las CSP del sitio y las vistas previas mandan)."""
        out[REQUEST_ID_HEADER] = request_id
        for name, value in _COMMON:
            if name not in out:
                out[name] = value
        is_api = path.startswith("/api/") or path == "/metrics"
        if "Content-Security-Policy" not in out:
            out["Content-Security-Policy"] = API_CSP if is_api else SPA_CSP
            out.setdefault(*_CORP)
        if is_api and "Cache-Control" not in out:
            out["Cache-Control"] = "no-store"
        if scope.get("scheme") == "https" and self.settings.environment == "production":
            out.setdefault("Strict-Transport-Security", "max-age=31536000")


def _cookie(headers: Headers, name: str) -> str | None:
    for part in headers.get("cookie", "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == name and value:
            return value
    return None
