"""Errores de la API en el idioma de ``Accept-Language`` y con ``code`` estable (ADR-015)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Run
from app.i18n import Msg
from tests.api.test_projects import new_project

EN = {"Accept-Language": "en-GB,en;q=0.9"}
ES = {"Accept-Language": "es-ES"}


def test_domain_error_in_both_languages_with_the_same_code(user_client: TestClient) -> None:
    english = user_client.get("/api/v1/projects/999999", headers=EN)
    spanish = user_client.get("/api/v1/projects/999999", headers=ES)
    default = user_client.get("/api/v1/projects/999999")

    assert english.status_code == spanish.status_code == 404
    assert english.headers["content-type"].startswith("application/problem+json")
    assert english.json()["code"] == spanish.json()["code"] == default.json()["code"] == "project_not_found"
    assert english.json()["title"] != spanish.json()["title"]
    assert default.json()["title"] == spanish.json()["title"]
    assert english.headers["Content-Language"] == "en"
    assert spanish.headers["Content-Language"] == "es"
    assert "Accept-Language" in english.headers["Vary"]


def test_unsupported_language_falls_back_to_spanish(user_client: TestClient) -> None:
    french = user_client.get("/api/v1/projects/999999", headers={"Accept-Language": "fr-FR"})
    spanish = user_client.get("/api/v1/projects/999999", headers=ES)

    assert french.json()["title"] == spanish.json()["title"]
    assert french.headers["Content-Language"] == "es"


def test_validation_errors_are_translated_and_carry_a_code(user_client: TestClient) -> None:
    english = user_client.post("/api/v1/projects", json={}, headers=EN)
    spanish = user_client.post("/api/v1/projects", json={}, headers=ES)

    assert english.status_code == spanish.status_code == 422
    assert english.json()["code"] == "validation_error"
    assert english.json()["title"] == "Invalid input data"
    assert spanish.json()["title"] == "Datos de entrada no válidos"
    missing_en = next(e for e in english.json()["errors"] if e["loc"][-1] == "name")
    missing_es = next(e for e in spanish.json()["errors"] if e["loc"][-1] == "name")
    assert (missing_en["code"], missing_en["msg"]) == ("missing", "Required field.")
    assert (missing_es["code"], missing_es["msg"]) == ("missing", "Campo obligatorio.")


def test_unknown_route_and_unauthenticated(client: TestClient) -> None:
    unknown = client.get("/api/v1/does-not-exist", headers=EN)
    anonymous_en = client.get("/api/v1/projects", headers=EN)
    anonymous_es = client.get("/api/v1/projects", headers=ES)

    assert (unknown.status_code, unknown.json()["code"], unknown.json()["title"]) == (404, "http_404", "Not found")
    assert anonymous_en.status_code == anonymous_es.status_code == 401
    assert anonymous_en.json()["code"] == anonymous_es.json()["code"]
    assert anonymous_en.json()["title"] != anonymous_es.json()["title"]


def test_run_failure_is_shown_in_the_reader_language(user_client: TestClient, db: Session) -> None:
    project = new_project(user_client)
    response = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "noop", "params": {}})
    run_id = response.json()["id"]
    db.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(
            status="failed",
            error_code="job_timeout",
            error_detail=Msg("jobs.timeout", limit=60).to_dict(),
            error_message="Superó el tiempo máximo (60 s).",
        )
    )
    db.commit()

    english = user_client.get(f"/api/v1/runs/{run_id}", headers=EN).json()
    spanish = user_client.get(f"/api/v1/runs/{run_id}", headers=ES).json()

    assert english["error_message"] == "Exceeded the maximum time (60 s)."
    assert spanish["error_message"] == "Superó el tiempo máximo (60 s)."
    assert english["error_code"] == spanish["error_code"] == "job_timeout"


def test_old_run_without_detail_keeps_its_text(user_client: TestClient, db: Session) -> None:
    project = new_project(user_client)
    response = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "noop", "params": {}})
    run_id = response.json()["id"]
    db.execute(
        update(Run).where(Run.id == run_id).values(status="failed", error_code="x", error_message="Texto de la 1.24.0")
    )
    db.commit()

    assert user_client.get(f"/api/v1/runs/{run_id}", headers=EN).json()["error_message"] == "Texto de la 1.24.0"
