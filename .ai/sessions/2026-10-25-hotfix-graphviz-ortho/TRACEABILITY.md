# TRACEABILITY

## Session metadata
- id: 2026-10-25-hotfix-graphviz-ortho
- fecha: 2026-10-25
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
`/hotfix C:\Users\manza\Downloads\run.log` (log de la ejecución `01M5SGQXTV8J81Y9QFZKVN2F21`). Tras AUDIT_PLAN:
«IMPLEMENT», sin autorizar la reproducción con la conexión SocyalPRO; no se usó.

## Context supplied
- `run.log` y `run.json` de la ejecución: documentación MariaDB, profundidad 3, los tres formatos; falla a los 17 min
  con `unknown` («util_bbdd falló (DocumentationRenderError)»); solo queda `logs/run.log`.
- util_bbdd 4.0.0 (`graphviz_ext.py`, `html_generator.py`, `word_generator.py`, `documentation_orchestrator.py`) y el
  paquete `graphviz` del venv.

## AI output summary
- RCA:
  - `dot` 2.43.0 (Debian bookworm) aborta con `newtrap: Trapezoid-table overflow` en un SVG del HTML; util_bbdd usa
    siempre `splines=ortho`;
  - los renderers capturan solo `(OSError, RuntimeError)` por diagrama y `graphviz.CalledProcessError` deriva de
    `subprocess.CalledProcessError`: el formato entero falla y el orquestador lo envuelve (`from error`) en
    `DocumentationRenderError`;
  - el aviso de Fontconfig es ruido (cachés del sistema en `/var/cache/fontconfig`).
- PLAN/AUDIT_PLAN: `GO`. IMPLEMENT:
  - `docker/dot-wrapper.sh` → `/usr/local/bin/dot` (Dockerfile, etapa runtime): con el grafo por stdin, si `dot` muere
    por una señal, un reintento con `-Gsplines=polyline` (verificado que prevalece sobre el atributo del grafo en 2.43
    y 14.1); con un fichero como argumento, `exec` del `dot` real; `UBW_REAL_DOT` para los tests;
  - `integrations/util_bbdd/documentation.py`: `graphviz_failed(exc)` recorre la cadena de causas;
  - `jobs/operations/documentation.py`: `_job_error` devuelve `graphviz_failed` con mensaje propio;
  - tests: `_job_error` con un `DocumentationRenderError` real causado por `CalledProcessError`; envoltorio con un
    `dot` falso (reintento sin bytes del intento abortado, éxito, error normal sin reintento, fichero como argumento);
    se omiten en Windows y se ejecutan en el CI (ubuntu con el repo completo);
  - docs: G39, `troubleshooting.md`, `documentacion.md`, CHANGELOG (`Fixed`).
- Validación:
  - ruff, mypy y `export_openapi.py --check`; pytest local 565 passed (87 skipped);
  - unitarios en Linux con `backend-dev` montando `docker/`: 46 passed;
  - format:check, lint, typecheck, build, Vitest (105) y `zensical build --strict`;
  - imagen runtime: `command -v dot` → `/usr/local/bin/dot` con `--read-only` y `/tmp` en tmpfs;
  - grafos sintéticos (scratchpad `tools/ortho_fuzz.py`): el `dot` real abortó (`maze.c: chkSgraph`, `rc=-6`) y el
    envoltorio produjo el SVG; la aserción `trapezoid.c` del log no se reprodujo en 3000 grafos;
  - E2E en un stack aislado temporal con la imagen nueva: 19 passed, 2 skipped; stack e imagen eliminados.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Rodeo | `docker/dot-wrapper.sh`, `docker/Dockerfile` | completado |
| Errores | `backend/app/integrations/util_bbdd/documentation.py`, `backend/app/jobs/operations/documentation.py` | completado |
| Tests | `backend/tests/unit/test_documentation_units.py` | en verde |
| Docs | `docs/plan/UTIL_BBDD_GAPS.md` (G39), `docs/guides/troubleshooting.md`, `docs/guides/documentacion.md`, `CHANGELOG.md` | completado |
| Logs | `build/logs/hotfix-dot-*.txt` | generados |

## Directrices para Futuras IAs
- **[graphviz]**: la imagen runtime trae Graphviz 2.43.0; su enrutado ortogonal aborta (SIGABRT) en algunos grafos y
  util_bbdd 4.0.0 usa siempre `splines=ortho`. `/usr/local/bin/dot` es `docker/dot-wrapper.sh`; el real es
  `/usr/bin/dot`.
- **[graphviz]**: `-Gsplines=polyline` en la línea de órdenes prevalece sobre `splines=ortho` del grafo (2.43 y 14.1).
- **[errores]**: los renderers de util_bbdd 4.0.0 no capturan `graphviz.CalledProcessError` por diagrama; llega en la
  cadena de causas de `DocumentationRenderError` (`graphviz_failed`).
- **[documentación]**: si falla un formato se pierden todos; el directorio de trabajo se borra en el `finally` de
  `generate_documentation`.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Desplegar: `docker compose up -d --build` en el despliegue local y relanzar la documentación de SocyalPRO.
- Mejora aparte: conservar Word y Excel cuando falla solo el HTML.
- Verificar si una versión de Graphviz posterior a 2.43 corrige el overflow (PENDIENTE DE VERIFICAR).
