"""Rechazo temprano de las subidas (``UploadGuard``): 401, 403, 411 y 413 sin leer el cuerpo multipart."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

_BULK = "/api/v1/projects/999/uploads"  # el guard no mira la membresía: eso lo hace el endpoint
_TEMPLATES = "/api/v1/projects/999/document-templates"


def _post(client: TestClient, path: str, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    """``POST`` directo a la app ASGI con un ``receive`` que falla: la respuesta no puede depender del cuerpo."""
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "https",
        "server": ("testserver", 443), "client": ("127.0.0.1", 50000), "root_path": "", "path": path,
        "raw_path": path.encode(), "query_string": b"",
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
    }  # fmt: skip
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        raise AssertionError("el guard leyó el cuerpo")

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    asyncio.run(client.app(scope, receive, send))  # type: ignore[arg-type]
    start, body = messages[0], b"".join(m.get("body", b"") for m in messages[1:])
    assert dict(start["headers"])[b"content-type"] == b"application/problem+json"
    return start["status"], json.loads(body)


def _auth(client: TestClient, *, csrf: bool = True) -> dict[str, str]:
    headers = {"cookie": "; ".join(f"{name}={value}" for name, value in client.cookies.items())}
    if csrf:
        headers["X-CSRF-Token"] = client.headers["X-CSRF-Token"]
    return headers


def test_without_session_is_rejected_before_reading_the_body(client: TestClient) -> None:
    status, body = _post(client, _BULK, {"content-length": "1000"})

    assert status == 401 and body["request_id"]


def test_without_csrf_is_rejected_before_reading_the_body(user_client: TestClient) -> None:
    status, _ = _post(user_client, _BULK, {**_auth(user_client, csrf=False), "content-length": "1000"})

    assert status == 403


@pytest.mark.parametrize("length", [None, "", "-1", "mucho"])
def test_without_a_valid_content_length_is_411(user_client: TestClient, length: str | None) -> None:
    headers = _auth(user_client) | ({} if length is None else {"content-length": length})

    status, body = _post(user_client, _BULK, headers)

    assert status == 411 and body["title"] == "Falta Content-Length"


@pytest.mark.parametrize(("path", "max_mb"), [(_BULK, 50), (_TEMPLATES, 10)])
def test_declared_size_over_the_limit_is_413(user_client: TestClient, path: str, max_mb: int) -> None:
    too_big = str(max_mb * 1024 * 1024 + 64 * 1024 + 1)

    status, body = _post(user_client, path, {**_auth(user_client), "content-length": too_big})

    assert status == 413 and f"{max_mb} MB" in body["detail"]


def test_the_admin_upload_limit_applies_before_reading_the_body(
    admin_client: TestClient,
) -> None:
    changed = admin_client.patch("/api/v1/admin/storage", json={"upload_max_mb": 1})
    assert changed.status_code == 200

    status, body = _post(admin_client, _BULK, {**_auth(admin_client), "content-length": str(2 * 1024 * 1024)})

    assert status == 413 and "1 MB" in body["detail"]


def test_a_valid_upload_still_reaches_the_endpoint(user_client: TestClient) -> None:
    response = user_client.post(_BULK, files={"file": ("a.csv", b"id\n1\n")})

    assert response.status_code == 404  # pasa el guard; el endpoint comprueba la membresía del proyecto
