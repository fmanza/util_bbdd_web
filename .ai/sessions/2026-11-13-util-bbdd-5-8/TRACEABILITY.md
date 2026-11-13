# TRACEABILITY

## Session metadata
- id: 2026-11-13-util-bbdd-5-8
- fecha: 2026-11-13
- rama: develop
- skill: new_feature + version_closure (sesiones hermanas en util_bbdd: `2026-11-13b-plan-pendientes-post-5-6`,
  `2026-11-13c-mermaid-nombre-tipo`)
- fase: PLAN + AUDIT_PLAN (GO) + IMPLEMENT (W-13.0–W-13.2) + VERSION → 1.18.0

## Prompt issued
«Hacemos lo pendiente»: adoptar G49 (util_bbdd 5.7.0; el usuario indicó que ya existe la 5.8.0), recordatorio del
`uv lock --upgrade` del 2026-11-25 (issue #24 en GitHub, sin agente programado) y publicar la 1.18.0. El despliegue
en el servidor lo hace el usuario.

## Context supplied
- Web 1.17.0 con util_bbdd 5.6.0; util_bbdd 5.8.0 (tag `v5.8.0`, release con wheel y `.sha256`).

## AI output summary
- `919603b` chore(backend): util_bbdd 5.8.0 (hash `fb236ab7…c75f70`; lock con uv 0.12.22).
- `9931145` feat(backend): `trace_map_error` (capa anticorrupción) valida el mapa al subirlo con
  `util_bbdd.doc.validate_trace_map`; 422 con todos los errores, nombre del usuario y sin rutas; no se guarda.
- `4ea423f` docs: G49 resuelto, guías (validación al subir, `driver_name` opcional con pyodbc), W-13 y CHANGELOG.
- Issue #24: recordatorio del `uv lock --upgrade` a partir del 2026-11-25.

## Evidencias
- Backend 802 passed, 2 skipped; ruff, mypy, test de arquitectura y `export_openapi --check` en verde.
- `trace_map_error` con el mapa erróneo de los tests: mensaje «El mapa de trazabilidad (ventas.toml) no es válido:
  …» con los dos errores, sin rutas ni `.tmp-`.
- `zensical build --strict` sin avisos. Imagen Docker 1.18.0 y suite E2E: ver Veredicto final.

## Directrices para Futuras IAs
- **[backend/plantillas]**: un mapa `trace` se valida al subirlo en `domain/templates/service.py` con
  `trace_map_error` (`integrations/util_bbdd/documentation.py`); el temporal `.tmp-<ulid>.<toml|json>` conserva la
  extensión porque util_bbdd elige el formato por ella. La sintaxis la sigue comprobando `files.py` (mensajes propios).
- **[backend/job]**: `markdown_input_error`/`public_message` se mantienen aunque util_bbdd 5.7.0 ya no ponga rutas:
  sustituyen el nombre del fichero de `inputs/` por el que subió el usuario. Los mapas subidos antes de la 1.18.0 no
  están validados: el job puede seguir fallando con `invalid_trace_map`.
- **[tests]**: las plantillas de proyecto viven en `users/<id>/projects/<id>/templates`, no en `templates/`: para
  comprobar que no queda un fichero, busca en todo el workspace.
- **[util_bbdd 5.8.0]**: los `erDiagram` llevan nombre antes que tipo; con pyodbc sin `driver_name`, el driver ODBC
  más reciente instalado.

## Veredicto final
Veredicto: CLOSED (1.18.0)
Pendientes al cierre: despliegue en el servidor (usuario); issue #24 a partir del 2026-11-25.
