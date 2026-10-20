# TRACEABILITY

## Session metadata
- id: 2026-10-20-fase1
- fecha: 2026-10-20
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 1 del ROADMAP)

## Prompt issued
```text
/phase

Fase: 1
Alcance: completa
Mejoras opcionales: no
Restricciones: dependencias nuevas permitidas: pwdlib[argon2]; sin servicios externos
```
Tras AUDIT_PLAN: «IMPLEMENT».

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`, prompt `phase_implementation` y agentes (ver `00_CONTEXT_SNAPSHOT.md`)

## AI output summary
- PLAN y AUDIT_PLAN: veredicto `GO_CONDICIONAL` (formularios sin RHF + Zod por la restricción de dependencias;
  `403` para el rol `user` en endpoints de admin). Aprobado por el usuario.
- `pwdlib[argon2]` 0.3.1 añadido con `uv add` (dentro de `exclude-newer`); API verificada en el paquete instalado
  (`PasswordHash`, `Argon2Hasher`, `verify_and_update`).
- Backend: `core/security.py` (tokens, HMAC CSRF, clave obligatoria en producción), `AppError` en `core/errors.py`,
  ajustes `UBW_SESSION_*`/`UBW_LOGIN_*`/`UBW_PASSWORD_MIN_LENGTH`, `db/models.py` (`User`, `UserSession`,
  `AuditEntry`, tipo `UTCDateTime`), migración `0002_identity` (verificada con `alembic check` y
  upgrade/downgrade/upgrade), `domain/identity/` (passwords, sessions, users, auth, audit, errors), `api/deps.py`
  (sesión, admin, CSRF, cookies), routers `auth`, `users`, `sessions`, `audit`, `cli.py`.
- Tests backend: 61 nuevos (73 en total): unitarios de hash, política, tokens, bloqueo, caducidad y último admin;
  API de cookies, CSRF (incluida la inyección de cookie), rotación, 401/403/404/409/422, revocación, auditoría,
  ausencia de secretos en logs y auditoría, CLI y migraciones.
- Contrato: `openapi/openapi.json` exportado y `schema.d.ts` regenerado (estable al regenerar).
- Frontend: middleware CSRF en `api/client.ts`, `QueryCache` que revalida `me` ante un 401, `features/auth`
  (login, guardas, menú, cambio de contraseña), `features/admin` (usuarios, sesiones, auditoría; `lazy`),
  `components/` (ErrorAlert, NoPermission, formato), i18n. 16 tests nuevos de Vitest (19), helper `test/api.ts`.
- E2E: `smoke.spec.ts` actualizado y `login.spec.ts` (3 flujos).
- Docs: guía `usuarios_y_sesiones.md`, despliegue (primer admin), incorporación, solución de problemas,
  arquitectura (variables nuevas), notas en ADR-003, README.
- AUDIT_CODE:
  - Backend local: `uv sync`, `ruff format --check`, `ruff check`, `mypy --platform linux`, `pytest` (73 passed),
    `export_openapi.py --check` OK. En la imagen `backend-dev` (Linux, como el CI): los mismos comandos con
    `mypy` sin opciones, todo OK.
  - Frontend: `format:check`, `lint`, `typecheck`, `test` (19 passed), `build` OK; el bundle principal baja a
    454 kB (el aviso de > 500 kB de la Fase 0 desaparece gracias a `lazy`).
  - `docker compose build` + `up`: web *healthy*, migración 0001 → 0002 aplicada sobre el volumen existente,
    `/api/health` → `ok` 0.2.0; imagen 767 MB (+1 MB).
  - CLI dentro del contenedor (`create-admin --password-stdin`, duplicado → código 1).
  - Playwright contra el contenedor: 5/5 OK.
  - Verificación manual con curl: login sin CSRF → 403; cookies `HttpOnly; Secure; SameSite=lax; Path=/`;
    `/api/docs` → 404 en producción.
  - Revisión de seguridad propia (checklist del Security Reviewer, puntos 1–3, 9–11): sin hallazgos bloqueantes;
    residuales abajo.
  - Salidas en `build/logs/fase1_*.txt`.
- VERSION: 0.2.0 en `backend/app/__init__.py`, `pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`;
  CHANGELOG, ROADMAP (Fase 1 cerrada), `.ai/product.md`, esta sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, aprobado) |
| Backend | `backend/app/{core,db,domain/identity,api}`, `backend/app/cli.py`, `backend/alembic/versions/0002_identity.py` | completado |
| Tests backend | `backend/tests/{unit,api}/` | completado (73) |
| Contrato | `openapi/openapi.json`, `frontend/src/api/schema.d.ts` | completado |
| Frontend | `frontend/src/{api,app,components,features/auth,features/admin,i18n,test}` | completado (19 tests) |
| E2E | `frontend/e2e/{smoke,login}.spec.ts` | ejecutado (5/5) |
| Docs | `docs/guides/usuarios_y_sesiones.md` y guías, ADR-003, arquitectura, README, CHANGELOG, ROADMAP | completado |

## Directrices para Futuras IAs
- **[mypy-windows]**: `uv run --frozen mypy` en Windows da 3 errores en `app/jobs/worker.py` (`signal.sigwait`, `pthread_sigmask`, `SIG_BLOCK` no existen en win32); usar `mypy --platform linux` en local o la imagen `backend-dev`. El CI (Linux) está limpio.
- **[tests-backend]**: la fixture `client` aplica Alembic (`run_migrations()`) sobre una `config.db` en `tmp_path` y usa `base_url="https://testserver"`, porque las cookies llevan `Secure` fuera de `development`. Sin HTTPS, `TestClient` no reenvía la cookie.
- **[tests-backend]**: para iniciar sesión en tests usa `do_login(client, usuario, contraseña)` de `tests/conftest.py`; deja `X-CSRF-Token` en `client.headers`. Para una segunda sesión: `TestClient(client.app, base_url="https://testserver")`.
- **[csrf]**: todo método no seguro bajo `/api/v1` pasa por `csrf_protect` (dependencia del router v1). Con cookie de sesión, el token válido es `HMAC(ubw_app_secret_key, token)`; los routers nuevos no tienen que hacer nada.
- **[auth-deps]**: en los routers usa `CurrentUser`, `CurrentSession`, `AdminUser`, `DbSession`, `SettingsDep` y `Context` de `app/api/deps.py`; los errores de dominio heredan de `AppError` (`app/core/errors.py`) con `status`/`title` y se convierten solos en *problem details*.
- **[sqlite-fechas]**: las columnas de fecha usan `UTCDateTime` (`app/db/models.py`): se guardan sin zona y se devuelven con UTC; pasar siempre `datetime` con zona (`utcnow()`), o `process_bind_param` lanza `ValueError`.
- **[windows-eol]**: `Path.write_text()` en Windows escribe CRLF; el repo es LF (`.gitattributes`/`.editorconfig`). Para editar con Python usar `write_bytes` o `newline="\n"`, o comprobar `grep -l $'\r'` antes de cerrar.
- **[frontend-tests]**: `src/test/api.ts` tiene `stubApi({"MÉTODO /ruta": respuesta})`, `session(ADMIN|USER|null)` y `callsTo()`; todas las rutas de la app exigen `GET /api/v1/auth/me` en el stub.
- **[mantine-jsdom]**: `Select`/`Combobox` de Mantine 9 necesitan `Element.prototype.scrollIntoView` (stub en `src/test/setup.ts`) y en jsdom sus opciones no aparecen de forma fiable al hacer clic; para pocos valores, `SegmentedControl` (rol `radio`) es más fácil de probar.
- **[i18n]**: i18next usa `.` como separador de claves: una clave no puede terminar en punto (`filters.auth.` no funciona). Las acciones de auditoría `auth.login` se traducen con claves anidadas `admin.audit.actions.auth.login`.
- **[e2e]**: `login.spec.ts` necesita `UBW_E2E_ADMIN_USER`/`UBW_E2E_ADMIN_PASSWORD` y el admin creado con `docker compose exec -T web python -m app.cli create-admin --username e2e-admin --password-stdin`; sin esas variables se omite. Chromium acepta cookies `Secure` sobre `http://127.0.0.1:8080` (verificado).
- **[imagen]**: con `pwdlib[argon2]` la imagen runtime mide 767 MB (+1 MB respecto a la 0.1.0).

## Veredicto final
Veredicto: CLOSED (Fase 1 cumplida; DoD común y de la fase verificadas, E2E incluido)
Pendientes al cierre:
- Riesgos residuales para la Fase 10:
  - *Rate limiting* por IP del login: el bloqueo es por cuenta, así que un atacante puede bloquear cuentas 15 min.
  - Prefijo `__Host-` en las cookies.
  - Cabeceras CSP/HSTS.
  - `FORWARDED_ALLOW_IPS` de uvicorn tras el proxy: la IP auditada puede ser la del *gateway* de Docker.
- La auditoría guarda el `username` tecleado en los logins fallidos: si alguien escribe su contraseña en ese campo,
  queda registrada (riesgo bajo, práctica habitual).
- Carrera teórica: dos admins degradándose a la vez podrían dejar el sistema sin admins. Se recupera con el CLI.
- El CI no ejecuta Playwright: el E2E es manual contra `docker compose up`.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 2`.
