# TRACEABILITY

## Session metadata
- id: 2026-10-26-gaps-ola2
- fecha: 2026-10-26
- rama: claude/practical-ride-44fot0
- skill: new_feature + version_closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de W-2 del plan de huecos (util_bbdd 4.2.0) → 1.2.0

## Prompt issued
Continuar con la ola 2 (comparación de esquemas): util_bbdd 4.2.0 y, publicada su release, las fases W-2.0 y
W-C1…W-C4, un commit por fase, y cerrar con la versión 1.2.0 (D5).

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md` (G1, G23, G24, G25); ADR-002, ADR-006 y ADR-007.
- Release `v4.2.0` de util_bbdd: wheel descargado y SHA-256 comprobado contra su `.sha256` (`5357688d…529f`).

## AI output summary
- W-2.0 `aed4164`: pin 4.2.0 (lock con uv 0.12.22). **Compatibilidad**: la etiqueta de Mermaid de 4.2.0 lleva
  `integrity`/`crossorigin` y la regex del sustituto dejó de reconocerla (fallaba `test_compare_generates_diff_and_reports`).
- W-C1 `b62d66a`: `source_label`/`target_label` = `alias (motor) [schema]`; `relabel` retirado.
- W-C2 `a43129b`: escritura con `SchemaDiff.to_dict()`; `read_diff` lee con `from_dict()` y mantiene el formato 1 propio;
  evolución probada entre un run de la 1.1.0 y uno nuevo.
- W-C3 `c39ac14`: `mermaid_src=None`; fuera `localize_mermaid` y `assets/mermaid-stub.js`. **Decisión**: no se sirve
  Mermaid desde la web (dependencia nueva, ~3 MB por informe); los diagramas siguen como texto.
- W-C4 `51ad8de`: `RunProgress` en la comparación, `compare` en `COOPERATIVE_OPERATIONS`.
- VERSION: 1.2.0 (este commit).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Registro de la ola | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` §6 | completado |

## Directrices para Futuras IAs
- **[comparación]**: `schema_diff.json` tiene dos formatos: `format == 1` (propio, runs hasta 1.1.0) y
  `format == "util_bbdd.schema_diff"` (desde 1.2.0). `read_diff` (integración) los unifica con los contadores; no
  quitar el lector del formato 1 mientras queden runs de la 1.1.0 sin purgar.
- **[comparación]**: el informe HTML se genera con `mermaid_src=None`: no reintroducir URLs de CDN (CSP de ADR-007).
  Para dibujar los diagramas haría falta servir `mermaid.min.js` propio (URL relativa o `Path` incrustado).
- **[jobs]**: la cancelación cooperativa de `compare` solo cubre la comparación; durante los informes cuenta el margen
  de 60 s del worker.
- **[dependencias]**: uv 0.12.22 (el de `docker/Dockerfile`) hizo `uv lock` directamente con la release de 4.2.0
  publicada; comprobar con `uv lock --check --offline`.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- `docker compose build` + `/api/health` 200 y E2E (`npm run e2e`, incluye el cambio de `compare.spec.ts`) en un equipo
  con Docker antes de desplegar.
- Merge a `main` y tag `v1.2.0` (propietario).
