"""Mensajes del área ``api``: routers, dependencias de la petición y guardián de subidas (ADR-015)."""

from __future__ import annotations

from typing import Final

ES: Final[dict[str, str]] = {
    # Clases de error de app/api
    "title.not_authenticated": "No autenticado",
    "title.permission_denied": "No tienes permiso para esta acción",
    "title.invalid_csrf_token": "Token CSRF ausente o no válido",
    "title.preview_unavailable": "Este artefacto no tiene vista previa",
    "title.preview_too_large": "El artefacto es demasiado grande para la vista previa; descárgalo",
    # Guardián de subidas
    "api.upload_length_required_title": "Falta Content-Length",
    "api.upload_length_required": "La subida debe indicar su tamaño.",
    "api.upload_too_large_title": "El fichero es demasiado grande",
    "api.upload_too_large": "El máximo es {max_mb} MB.",
    "api.max_size_mb": "El máximo es {max_mb} MB.",
    # Ejecuciones
    "api.runs.not_migration_apply": "Esta ejecución no es una aplicación de migración.",
    "api.runs.no_artifacts": "La ejecución no tiene artefactos.",
    "api.runs.no_artifacts_of_format": "La ejecución no tiene ese formato.",
    # Validación
    "api.preferences_empty": "Indica al menos una preferencia",
}

EN: Final[dict[str, str]] = {
    "title.not_authenticated": "Not authenticated",
    "title.permission_denied": "You do not have permission for this action",
    "title.invalid_csrf_token": "CSRF token missing or invalid",
    "title.preview_unavailable": "This artefact has no preview",
    "title.preview_too_large": "The artefact is too large to preview; download it",
    "api.upload_length_required_title": "Content-Length missing",
    "api.upload_length_required": "The upload must state its size.",
    "api.upload_too_large_title": "The file is too large",
    "api.upload_too_large": "The maximum is {max_mb} MB.",
    "api.max_size_mb": "The maximum is {max_mb} MB.",
    "api.runs.not_migration_apply": "This run is not a migration apply.",
    "api.runs.no_artifacts": "The run has no artefacts.",
    "api.runs.no_artifacts_of_format": "The run has no output in that format.",
    "api.preferences_empty": "Specify at least one preference",
}
