# TRACEABILITY

## Session metadata
- id: 2026-11-13-ddl-resaltado
- fecha: 2026-11-13
- rama: develop
- skill: refactor (tests E2E) + new_feature + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION → 1.17.0

## Prompt issued
1. Arreglar `security.spec` y `storage.spec` (E2E desfasados) y retirar las excepciones de `exclude-newer` de
   zensical; el usuario decidió adelantar el corte a 2026-11-11 aunque no cumple las 2 semanas hasta el 2026-11-25.
2. «Al mostrar Markdown en “Ejecución documentation” la visualización DDL que se visualice en colores según el formato
   correcto y permitir poder copiar el contenido»; ampliado al DDL del explorador y a la vista previa de los `.sql`.

## Context supplied
- Código de la web 1.16.0 (util_bbdd 5.6.0); el DDL de util_bbdd va en bloques ```` ```sql ```` (`_pages.py:118`).

## AI output summary
- `a0833d9` test(frontend): E2E de la CSP (hash del puente, nunca `'unsafe-inline'`) y del «Guardar» de Almacenamiento.
- `ceb79a2` chore(backend): `exclude-newer` = 2026-11-11 sin excepciones; el lock solo cambia sus opciones.
- `923ef7e` feat: DDL resaltado (`highlightSqlBlocks` antes de DOMPurify) y «Copiar» en el visor Markdown (el puente
  copia dentro del iframe); DDL resaltado en el explorador (`SqlCode`); nuevo hash del puente en las dos CSP;
  ADR-007 enmendado.
- `c804bac` feat(frontend): vista previa de los `.sql` resaltada con «Copiar SQL»; tope `MAX_HIGHLIGHT_CHARS`.
- Fuera de esta sesión, en paralelo: `a6afbdf` docs(plan) G49 (util_bbdd 5.7.0, pendiente de adoptar).

## Evidencias
- Vitest 210/210; lint, typecheck, prettier y build; backend `test_hardening` (hash del puente), ruff, mypy y
  `export_openapi --check`; `zensical build --strict`.
- Verificación en Chromium con la CSP real (instancia aislada, puerto 8099): la copia desde la SPA a petición del
  iframe falla (`NotAllowedError`, el foco es del iframe); dentro del iframe funciona con y sin permiso.
- E2E contra la instancia aislada (`UBW_E2E_URL`): documentation (resaltado, «Copiar», portapapeles), explorer, runs
  (SQL resaltado y «Copiar SQL») y bulk: 5/5. Suite E2E completa en Docker tras la release: ver Veredicto final.

## Directrices para Futuras IAs
- **[frontend/visor Markdown]**: el puente del iframe (`BRIDGE_SCRIPT`) copia al portapapeles **dentro** del iframe
  (`allow="clipboard-write"` + `execCommand('copy')` de respaldo). No intentes copiar desde la SPA por `postMessage`:
  Chromium lo rechaza porque el foco es del iframe. Si cambias el puente, recalcula el hash en `markdownFrame.ts` y
  `backend/app/core/middleware.py` (el script no admite `\` ni `${`: lo vigila `test_hardening.py`).
- **[frontend/SQL]**: el resaltado vive en `src/features/runs/sqlHighlight.ts` (cargador único de `highlight.js` y
  `MAX_HIGHLIGHT_CHARS`); `SqlCode` (sin scroll) y `SqlBlock` (con alto máximo) están en `migrate/SqlBlock.tsx`. En
  tests, el SQL resaltado queda repartido en `<span class="hljs-…">`: compara `textContent` del bloque `.ubw-sql`,
  no `getByText` del texto completo.
- **[frontend/tests]**: en Git Bash, entra en `frontend/` con `cd "C:/…"`; con `cd /c/…` Vitest falla en todos los
  ficheros con «failed to find the current suite».
- **[e2e]**: `UBW_E2E_URL` apunta Playwright a otra instancia (p. ej. API + worker con `uv run` y
  `UBW_STATIC_DIR=frontend/dist`) sin reconstruir la imagen Docker de una versión publicada.
- **[backend/dependencias]**: `exclude-newer` = 2026-11-11 sin excepciones; hasta el 2026-11-25 no ejecutes
  `uv lock --upgrade` sin revisar lo que entra.

## Veredicto final
Veredicto: CLOSED (1.17.0)
Pendientes al cierre: ver el Handoff de la conversación (push, CI, `main`, tag y despliegue).
