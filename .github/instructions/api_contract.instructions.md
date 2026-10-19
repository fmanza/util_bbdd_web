---
applyTo: "backend/app/api/**/*.py,frontend/src/api/**,openapi/**"
---
# Contrato HTTP — reglas

- Versión en la ruta: `/api/v1`. Cambios incompatibles → `/api/v2` o deprecación documentada.
- `openapi/openapi.json` es el contrato: tras tocar routers o esquemas, `uv run python scripts/export_openapi.py`
  (desde `backend/`) y `npm run gen:api` (desde `frontend/`) en el mismo cambio. El CI lo comprueba con `--check`.
- Errores: `application/problem+json` (RFC 9457) con `title`, `status`, `detail` opcional y campos extra tipados
  (p. ej. `errors` de validación). Nunca texto de excepciones de drivers.
- Códigos: `200/201/204` éxito; `202` job encolado (cuerpo: el `run`); `400` regla de negocio; `401` sin sesión;
  `403` sin permiso; `404` no existe **o no es visible para el usuario** (no filtrar existencia); `409` conflicto;
  `422` validación; `429` límite.
- Colecciones: `{"items": [...], "total": n}` con `limit` (máx. 200) y `offset`.
- Fechas en ISO 8601 UTC; identificadores de ejecución ULID.
- Campos secretos (`password`, claves) solo de escritura: nunca aparecen en respuestas (`exclude=True` / esquemas
  de salida distintos).
