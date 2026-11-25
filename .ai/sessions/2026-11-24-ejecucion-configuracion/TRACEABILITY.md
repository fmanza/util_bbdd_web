# TRACEABILITY

## Session metadata
- id: 2026-11-24-ejecucion-configuracion
- fecha: 2026-11-24 (cierre 2026-11-25)
- rama: feat/run-detail-config (desde `develop` en `db14aa3`)
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL; aprobado: detalle de la ejecución, alternativa A + filtro de B, sección
  siempre plegada) → IMPLEMENT → AUDIT_CODE breve → VERSION 1.23.0

## Prompt issued
«Mejorar la visualización de la pantalla Ejecuciones, actualmente sale un listado con las opciones seleccionada, nos
gustaria que pareciera a la de "lanzar Ejcución" pero más copactada, proponer alternativas, Plan y Aduit_Plan» →
«El alcance es el detalle de la ejecución … La recomendada … siempre plegada» → «si» (reconstruir contenedor y commit)
→ `/version-closure` (v1.23.0, esta carpeta).

## Context supplied
- `RunDetailPage.tsx`: tabla con una fila por clave de `run.params` (`<Code>nombre</Code>`); el backend guarda los
  parámetros normalizados con sus valores por defecto (`validate_params` → `model_dump`).
- `GET /api/v1/operations` devuelve todas las operaciones (también `form=false`) con tipo, grupo, opciones y
  `requires`; `launchLayout.ts` (`LAUNCH_LAYOUTS`, `resolveCards`, `DISABLED_WITHOUT`, `SHOWN_WHEN`) define las
  tarjetas de «Lanzar ejecución».
- Alternativas propuestas: A tarjetas de solo lectura, B chips con solo los cambiados, C pestañas.

## AI output summary
- Frontend:
  - `features/runs/runParamsView.ts` (nuevo): `buildParamsView` (tarjetas de `resolveCards`, visibilidad como el
    formulario: `requires`, plantilla sin su formato, `SHOWN_WHEN`, grupos de motor destino, modo de selección del
    volcado; `inactive` por `DISABLED_WITHOUT`; claves desconocidas en «Otros parámetros guardados»; sin catálogo, una
    tarjeta) y `sameValue`.
  - `features/runs/RunParamsSummary.tsx` (nuevo): sección «Configuración» plegada con contador, interruptor «Solo
    distintos del valor por defecto actual», chips para booleanos, `<dl>` para valores; conexiones y plantillas solo se
    piden al desplegar.
  - `RunDetailPage.tsx`: franja de metadatos (`<dl>`) en lugar de la tabla; título con `operation.title`.
  - `launch/launchLayout.ts`: `ENGINE_GROUPS` exportado (movido desde `LaunchForm.tsx`).
  - `projects/useProjects.ts`: `useProjectConnections(projectId, enabled = true)`.
  - i18n `runs.detail.*`.
- Tests: `runParamsView.test.ts` (6), `runs.test.tsx` (+1 «configuración de la ejecución»; cabecera con el título);
  e2e `runs.spec.ts` (cabecera).
- Docs: `CHANGELOG.md` (Changed), `docs/guides/proyectos_y_ejecuciones.md`.
- Commit `d5271de` en `feat/run-detail-config` (pedido por el usuario).
- VERSION 1.23.0: CHANGELOG, `pyproject.toml`, `__init__.py`, `package.json`/`package-lock.json`, `uv.lock`,
  `openapi.json` (`info.version`) y `.env.example` (`UBW_TAG`); `schema.d.ts` sin cambios.
- Validaciones ejecutadas:
  - Frontend: format:check, lint, typecheck y build en verde. Vitest completo con `--maxWorkers=3`: 262/264; los 2
    fallos (timeouts de 5 s en `runs.test.tsx` «envía los parámetros tipados…» y `markdown.test.tsx`) también fallan
    en la rama base en las mismas condiciones (9 fallos allí); los ficheros de ejecuciones aislados, 34/34.
  - Documentación: `zensical build --strict` sin incidencias.
  - Backend: `export_openapi.py --check` OK; pytest de `test_auth`, `test_hardening`, `test_health`, `test_runs`
    (71 passed) con 1.23.0.
  - Docker: imagen `util_bbdd_web:1.23.0` con `docker build --target runtime`; `docker compose up -d --no-build` en el
    puerto 8081; `/api/health` → `"version":"1.23.0"`, `"worker":"ok"`.
  - Manual en navegador (8081): ejecución `noop` en el proyecto «Prueba»; título legible, franja de metadatos,
    «Configuración» plegada con «0 de 4…», tarjeta desplegada y filtro con el aviso.
  - No ejecutados: ruff/mypy y pytest completos (sin cambios de backend salvo la versión), Playwright.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | respuesta de la sesión (resumen en este documento) | aprobado |
| IMPLEMENT | `frontend/src/features/runs/…` · `docs/…` · `CHANGELOG.md` | completado (`d5271de`) |
| Versión | 1.23.0 | preparada, sin commit |

## Directrices para Futuras IAs
- **[frontend]**: el detalle de una ejecución pinta su configuración con `buildParamsView`
  (`features/runs/runParamsView.ts`) sobre el mismo `resolveCards` del formulario; una tarjeta o regla de visibilidad
  nueva en `launchLayout.ts` se ve en los dos sitios, pero una regla que solo vive en `LaunchForm.tsx` (p. ej.
  `ORACLE_SOURCE_PARAMS`) no se aplica al detalle.
- **[frontend]**: «distinto del valor por defecto» compara con el `default` actual del catálogo, no con el de la fecha
  del lanzamiento; las claves guardadas que el catálogo ya no tiene cuentan como distintas.
- **[tests]**: Vitest lanzado desde Git Bash (`cd /c/...`, ruta `C:/`) falla en todas las suites con «Vitest failed to
  find the current suite»; lanzarlo desde PowerShell con `Set-Location c:\...`.
- **[docker]**: `docker compose up --build` con bake pide `--allow=fs.read=docker\Dockerfile` y `COMPOSE_BAKE=false`
  no lo evita en este equipo; construir con `docker build -f docker/Dockerfile --target runtime -t util_bbdd_web:<tag> .`
  y levantar con `docker compose up -d --no-build` (en este equipo `UBW_PORT=8081`: el 8080 lo usa otro proyecto).
- **[versión]**: uv local 0.13.1 frente a 0.12.22 de la imagen; `uv lock` solo cambió la versión del paquete, pero
  revisar el diff de `uv.lock` antes de confirmar.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit `release: v1.23.0 - …` propuesto, no ejecutado.
- Integrar `feat/run-detail-config` en `develop`; Playwright, `main`, tag y despliegue (`docs/guides/publicar_version.md`,
  pasos 4-8).
- Ejecución `noop` de verificación en el proyecto «Prueba» (local); se puede purgar.
