# TRACEABILITY

## Session metadata
- id: 2026-10-23-fase10
- fecha: 2026-10-23
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 10 del ROADMAP)

## Prompt issued
`/phase 10`. Respuestas: alcance completo, util_bbdd en GitHub Releases, `prometheus-client` y rate limiting
propio, ninguna mejora opcional. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites». Durante IMPLEMENT:
«Sí, súbelo» (wheel a la release `v4.0.0`).

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: `GO_CONDICIONAL`. Condiciones:
  - publicar el wheel: `gh` estaba instalado fuera del PATH de Git Bash y autenticado; se subió con confirmación;
  - mantener util_bbdd 4.0.0;
  - migración solo si ASVS la pedía: no hizo falta.
- Backend (`core/`):
  - `middleware.py`: ASGI puro con `request_id`, cabeceras, rate limiting, línea de acceso con ruta plantilla y
    métricas;
  - `ratelimit.py` (ventana deslizante) y `request_context.py`.
- Backend (resto):
  - `api/metrics.py`: `/metrics` con *bearer*;
  - `db/backup.py` y los comandos `backup`, `verify-backup` y `restore` de `cli.py`;
  - límites del login por IP en `auth.py`;
  - `request_id` en los *problem details*.
- Remediación ASVS (`docs/security/ASVS_L2.md`):
  - cookies `__Host-`;
  - lista de 45 578 contraseñas comunes;
  - OpenAPI oculto en producción;
  - `Cache-Control: no-store`;
  - opentelemetry-api 1.45.1 (CVE) y Vite 8.3.4.
- H11: wheel 4.0.0 (mismo SHA-256) en la release `v4.0.0`, `[tool.uv.sources]` por URL con hash en `uv.lock`
  (se verificó que `--frozen` rechaza otro hash) y `vendor/` retirado.
- Frontend: «Referencia» (`request_id`) en `ErrorAlert` y lectura de las cookies CSRF con o sin prefijo.
- E2E:
  - `fixtures.ts` vigila la CSP en todos los specs;
  - nuevos `members.spec.ts` y `security.spec.ts`.
- Hallazgos durante IMPLEMENT:
  - `CORP: same-origin` rompía los recursos del sitio sandbox (origen opaco). Ahora solo se pone sin CSP propia;
    lo detectó compare.spec.
  - El límite anónimo de 120/min se agotaba con muchos usuarios detrás de una IP: el valor por defecto pasa a 300.
  - `route.path` de FastAPI no lleva el prefijo de los routers anidados: la plantilla se reconstruye desde la URL.
  - `auto_describe` del registro de Prometheus consultaba la BD al registrar: se añadió `describe()` vacío.
  - La restauración se reordenó: primero se validan los `tar` y después se sustituye nada.
- Variantes: imagen con HSQLDB + ODBC (1,06 GB frente a 770 MB). Conexión real con HSQLDB 2.7.4 por JDBC y con SQL
  Server 16 por `pyodbc` y ODBC Driver 18.
- Carga, 20 usuarios durante 60 s:
  - solo lecturas: p95 de 104 ms;
  - con ~85 `noop`/min: p95 de 591 ms en el historial del proyecto, por la CPU de los subprocesos (documentado).
- AUDIT_CODE:
  - Backend local y en `backend-dev`: 550 (+32), ruff, mypy y contrato OK.
  - Integración en el bench: 79/79.
  - Frontend: format, lint, tsc, Vitest 105 (+3) y build OK.
  - Imagen 1.0.0: `/api/health` con worker ok y `/metrics` comprobado.
  - Playwright: 38 + 4 omitidos con `--repeat-each=2 --workers=2`, migración incluida.
  - Copia → verificación → restauración real con `docker compose run`.
  - `npm audit` sin vulnerabilidades; `pip-audit` solo deja mariadb, riesgo aceptado.
  - Salidas en `build/logs/fase10_*.txt`.
- VERSION:
  - 1.0.0, CHANGELOG, ROADMAP;
  - ADR-006 revisado, informe ASVS;
  - guías: despliegue reescrita; problemas, usuarios y onboarding;
  - arquitectura, README, `.ai/product.md`, `.ai/architecture.md`, `sync.instructions.md` y SHARED;
  - sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones resueltas) |
| Middleware y límites | `backend/app/core/{middleware,ratelimit,request_context}.py` | completado |
| Métricas | `backend/app/api/metrics.py` | completado |
| Copias | `backend/app/db/backup.py`, `backend/app/cli.py` | completado |
| Contraseñas comunes | `backend/app/domain/identity/data/` | completado |
| Tests | `backend/tests/{api/test_hardening.py,api/test_backup.py,unit/test_ratelimit.py}`, `frontend/src/components/ErrorAlert.test.tsx` | completado |
| E2E | `frontend/e2e/{fixtures,members.spec,security.spec}.ts` | ejecutado |
| Prueba de carga | `scripts/load_test.py` | ejecutado |
| Docs | `docs/security/ASVS_L2.md`, `docs/guides/deployment.md`, ADR-006 | completado |
| Release util_bbdd | `github.com/fmanza/util_bbdd/releases/tag/v4.0.0` (wheel + `.sha256`) | publicado |

## Directrices para Futuras IAs
- **[cookies]**: con `UBW_ENVIRONMENT` distinto de `development` las cookies son `__Host-ubw_session`/`__Host-ubw_csrf` (`Settings.cookie_prefix`, `api/deps.session_cookie|csrf_cookie`). Los tests (`https://testserver`) usan el prefijo. Las rutas leen los ajustes con `get_settings()`, no con los que recibe `create_app`: para probar otro entorno, hay que cambiar el entorno y limpiar la caché (fixture `app_with` en `test_hardening.py`).
- **[cabeceras]**: `HttpMiddleware._decorate` no pisa las cabeceras que pone la ruta. Si una ruta pone su CSP (sitio HTML y vistas previas), no se añade `Cross-Origin-Resource-Policy`, porque sus subrecursos se piden desde un origen opaco. Una ruta nueva que se sirva en un iframe `sandbox` debe poner su propia CSP.
- **[rate-limit]**: los límites viven en `app.state.limiter`, uno por aplicación y en memoria. Una suite E2E completa necesita límites altos (`UBW_RATE_LIMIT_ANONYMOUS_PER_MINUTE=2000`, `..._LOGIN_PER_MINUTE=300`, `..._LOGIN_FAILURES=100` al hacer `docker compose up`). Reiniciar `web` pone los contadores a cero.
- **[metricas]**: el registro Prometheus es propio por app (`HttpMetrics`). Todo colector nuevo debe implementar `describe()`; si no, `auto_describe` lo ejecuta al registrarlo. Las etiquetas solo pueden ser rutas plantilla y estados, nunca ids ni usuarios.
- **[util_bbdd-wheel]**: util_bbdd se instala desde `https://github.com/fmanza/util_bbdd/releases/download/v<versión>/…whl` con hash en `uv.lock`. Para subir de versión: comprobar que la release tiene el wheel (`"C:\Program Files\GitHub CLI\gh.exe" release view v<x> -R fmanza/util_bbdd`), cambiar la URL y la versión, y ejecutar `uv lock`. `gh` no está en el PATH de Git Bash: se usa desde PowerShell.
- **[secure-cookies-http]**: httpx y PowerShell no reenvían cookies `Secure` por HTTP; Chromium sí en `127.0.0.1`. Los scripts contra `http://127.0.0.1:8080` gestionan la cabecera `Cookie` a mano (`scripts/load_test.py:_keep_cookies`). Lo más simple es probar en el contenedor (`docker compose exec web python …`).
- **[backup]**: `restore` necesita la aplicación parada. En una parada limpia el worker se da de baja (`unregister_worker`) y no queda latido; si el worker murió sin darse de baja, hay que esperar 60 s. Los `tar` se extraen con `filter="data"`.
- **[e2e-usuarios]**: la lista de usuarios está paginada y ordenada por nombre, y el volumen de pruebas acumula usuarios `e2e-*`. Tras crear uno, hay que esperar a que se cierre el diálogo y buscarlo con «Buscar por usuario o nombre».
- **[carga]**: con lanzamientos continuos de jobs, el p95 del historial sube por la CPU de los subprocesos (ADR-002), no por la BD. El umbral de lecturas se cumple sin lanzamientos. Hay que medir en el servidor real antes de dimensionar.
- **[heredoc-escapes]**: en esta sesión el Bash tool volvió a convertir `\n` dentro de heredocs en saltos reales: se corrompió el código (`passwords.py`, `test_bulk.py`), y una fase anterior dejó `docs/guides/deployment.md` con un `printf` partido. Los scripts con escapes deben escribirse con Write.

## Veredicto final
Veredicto: CLOSED (Fase 10 completa; release 1.0.0 con ASVS L2 revisado, E2E de todos los flujos y variantes verificadas)
Pendientes al cierre:
- Riesgos aceptados: los del informe ASVS (sin MFA propio, `style-src 'unsafe-inline'`, limitador por proceso,
  mariadb PYSEC-2026-217).
- El CI no ejecuta Playwright, la integración ni la prueba de carga.
- Sin tag ni commit (pendientes de petición).
- Mejoras opcionales del ROADMAP para 1.x.
