# TRACEABILITY

## Session metadata
- id: 2026-10-26-gaps-ola1
- fecha: 2026-10-26
- rama: claude/practical-ride-44fot0
- skill: new_feature + version_closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de W-1 del plan de huecos (util_bbdd 4.1.0) → 1.1.0

## Prompt issued
Ejecutar el plan `docs/plan/UTIL_BBDD_GAPS_PLAN.md` (aprobado con D1-D5) tras publicar util_bbdd v4.1.0: fases
W-1.0, W-D1…W-D6 y W-G1, un commit por fase, y cerrar la ola con la versión 1.1.0 (D5).

## Context supplied
- Plan canónico y su registro de ejecución (§6); `UTIL_BBDD_GAPS.md`; ADR-002, ADR-006 y ADR-011.
- Release `v4.1.0` de util_bbdd: wheel descargado y SHA-256 comprobado contra su `.sha256` (`706ad06f…3fa1`).

## AI output summary
- W-1.0 `60ae275`: pin 4.1.0 (lock con uv 0.12.22, el de la imagen: con uv 0.11 el lock bajaba de `revision = 5` a 3);
  extras `sqlserver` y `sqlite-async`; `word_template_failed` reconoce «plantilla Word» sin distinguir mayúsculas.
- W-D1 `fec28c6`: `schema=` en documentación y grafo; fuera `with_schema` y el aviso de Oracle del formulario.
- W-D2 `8cfd07f`: **cambio de alcance**, se mantiene el reintento sin plantilla (util_bbdd falla antes de leer la BD).
- W-D3 `2f31d20`: «Relaciones en ángulo recto» (`graph_orthogonal` / `orthogonal_edges`).
- W-D4 `473890d`: `plantilla_excel` / `table_style_excel`; reintento sin plantilla para Word y Excel.
- W-D5 `254abff`: `RunProgress`, cancelación cooperativa y margen de 60 s del worker (ADR-002 enmendado).
- W-G1 `d6cf670`: progreso y cancelación del grafo de todas las tablas.
- W-D6 `8bfdce6`: guía (G38) y GAPS G2/G38.
- VERSION: 1.1.0 (este commit). Backend: ruff, mypy, pytest; frontend: format, lint, typecheck, vitest y build;
  OpenAPI sin cambios; `zensical build --strict` limpio. **No ejecutado**: `docker compose build` y `/api/health`
  (sin demonio de Docker en el contenedor) y los tests de integración contra el bench.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Puente de progreso | `backend/app/integrations/util_bbdd/progress.py` | completado |
| Registro de la ola | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` §6 | completado |

## Directrices para Futuras IAs
- **[dependencias]**: regenera `backend/uv.lock` con la versión de uv de `docker/Dockerfile` (`UV_IMAGE`); otra
  versión cambia `revision` del lock.
- **[dependencias]**: los assets de GitHub Releases responden 401 a `HEAD` (la URL firmada solo vale para `GET`). `uv
  lock` hace `HEAD` si el wheel no está en caché: `uv sync --frozen` lo descarga con `GET` y lo deja en caché; no
  vacíes la caché de `util-bbdd` antes de `uv lock`. Comprueba con `uv lock --check --offline`.
- **[jobs]**: `RunProgress` (`integrations/util_bbdd/progress.py`) es el puente común de `util_bbdd.progress`; una
  operación nueva cooperativa entra en `COOPERATIVE_OPERATIONS` del worker y mapea `is_cancellation` a
  `JobError("cancelled")`, que el runner cierra como `cancelled`.
- **[plantillas]**: util_bbdd 4.1.0 rechaza las plantillas al construir `DatabaseDocumentation` con mensajes que
  contienen «plantilla Word» / «plantilla Excel»; `word_template_failed` y `excel_template_failed` los reconocen y
  `_document_with_template` reintenta sin la plantilla que falló (como mucho, sin las dos).
- **[tests]**: tras `finalize_run` desde el hijo, el proceso puede seguir vivo un momento: `process.join()` antes de
  mirar `exitcode`.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- `docker compose build` + `/api/health` 200 y E2E (`npm run e2e`) en un equipo con Docker antes de desplegar.
- Integración contra el bench (G21: owner de Oracle distinto del usuario).
