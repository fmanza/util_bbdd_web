# TRACEABILITY

## Session metadata
- id: 2026-10-26-feat-storage-admin
- fecha: 2026-10-26
- rama: develop (sin commit; cambios en el árbol de trabajo)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
«Cual es el tamaño definido de almacenamiento para forzar la purga. Queremos que sea una opción administrable.»
Respuesta: ningún tamaño fuerza la purga (la cuota de 1024 MB solo bloquea con 409; la retención es por días y por
número). Opciones 1 (ajustes globales en la web), 2 (cuota por usuario) y 3 (purga por cuota); el usuario eligió las
tres. Decisiones del AUDIT_PLAN: objetivo 80 % (10–95), protección de 60 minutos y de las ejecuciones citadas por una
activa, purga al encolar/subir y en el worker, solo ejecuciones (S1) y vista «Mi espacio» para todos los usuarios.
Después: «IMPLEMENT» y «Si» (AUDIT_CODE y VERSION).

## Context supplied
- Código: `usage_bytes`/`enqueue` (cuota), `retention_candidates`/`apply_retention`/`purge_run`, `purge_old_uploads`,
  `Worker.maintenance` (cada hora), referencias entre ejecuciones (`preview_run`, `plan_run`, `dry_run_run` y sus 60
  minutos de validez), `update_user`/`UserUpdate`, despliegue local sin variables sobrescritas.

## AI output summary
- Backend:
  - migración `0010` (`app_settings`, `users.storage_quota_mb`); `UBW_QUOTA_PURGE` y `UBW_QUOTA_PURGE_TARGET_PCT`;
  - `domain/storage/settings.py` (ajustes efectivos = `Settings` con las filas encima, rangos, cuota por usuario,
    petición de mantenimiento), `purge.py` (selección y purga por cuota con protecciones), `service.py` (estado,
    cambio auditado, vista previa, «Aplicar ahora», uso por usuario, «Mi espacio»);
  - `enqueue` y `save_upload` con cuota efectiva y purga; `Worker.maintenance` con ajustes efectivos, purga por
    cuota y «Aplicar ahora»; `retention_candidates` extraído en `uploads/service.py` para la vista previa;
  - API `/api/v1/admin/storage` (GET, PATCH, `/preview`, `/maintenance`, `/usage`) y `/api/v1/auth/me/storage`;
    `storage_quota_mb` en `UserOut`/`UserUpdate` (`null` explícito = la global).
- Contrato exportado y cliente regenerado.
- Frontend: `admin/StoragePage.tsx`, `storage/MyStoragePage.tsx`, `storage/useStorage.ts`, cuota en
  `UserFormModal`, «Mi espacio» en el menú, rutas e i18n.
- Docs: ADR-012, ADR-005 (nota), arquitectura, usuarios y sesiones («Almacenamiento»), guía de usuario, solución de
  problemas, índice, Zensical y CHANGELOG.
- Tests: `tests/api/test_storage.py` (9), `storage.test.tsx` (7), `e2e/storage.spec.ts`; `test_backup` (revisión
  0010).
- AUDIT_CODE: dos hallazgos corregidos:
  - una variable `UBW_*` fuera del rango de la web (p. ej. `UBW_RUN_RETENTION_DAYS=5000`) hacía fallar con 500 toda
    ejecución (se validaban las filas junto con los valores por defecto); ahora cada fila se valida sola con su
    `TypeAdapter`; test de regresión que fallaba antes del arreglo;
  - los botones «Restablecer» tenían el mismo nombre accesible; ahora «Restablecer <campo>».
- Validación: ruff, mypy, `export_openapi.py --check`, pytest 627 passed (87 skipped), format:check, lint,
  typecheck, Vitest 121, build, `zensical build --strict`; imagen Docker en un stack aislado (`ubw_e2e`, 8091) con
  `/api/health` 200 y suite E2E completa `--repeat-each=2 --workers=2`: 39 passed, 7 skipped; tras el cambio de
  localizador, `storage.spec.ts` y `login.spec.ts` repetidos en un stack reconstruido (4 passed). Stacks e imágenes
  eliminados; el despliegue local no se tocó.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT backend | `backend/app/domain/storage/`, `backend/app/api/v1/admin_storage.py`, `backend/app/api/v1/schemas_storage.py`, `backend/alembic/versions/0010_storage_settings.py` y modificados | completado |
| Contrato | `openapi/openapi.json`, `frontend/src/api/schema.d.ts` | regenerado |
| IMPLEMENT frontend | `frontend/src/features/admin/StoragePage.tsx`, `frontend/src/features/storage/` y modificados | completado |
| Tests | `backend/tests/api/test_storage.py`, `frontend/src/features/storage/storage.test.tsx`, `frontend/e2e/storage.spec.ts` | en verde |
| Docs | `docs/adr/ADR-012-almacenamiento-administrable.md`, `docs/guides/usuarios_y_sesiones.md`, `docs/architecture.md`, `CHANGELOG.md` | completado |
| Logs | `build/logs/pytest_storage_full.txt`, `build/logs/e2e_*storage*.txt`, `build/logs/docker_e2e_build_storage.txt` | generados |

## Directrices para Futuras IAs
- **[almacenamiento]**: la cuota y la retención **no** se leen de `settings` directamente: usar
  `effective_settings(db, settings)` (`domain/storage/settings.py`). Las variables `UBW_*` son solo el valor por
  defecto; si un admin cambió el ajuste en la web, manda la fila de `app_settings`.
- **[almacenamiento]**: las filas de `app_settings` se validan una a una (`_ADAPTERS`); los valores por defecto de
  `UBW_*` no se validan contra los rangos de la web (pueden ser mayores) — no volver a validarlos juntos.
- **[almacenamiento]**: la cuota de un usuario es `users.storage_quota_mb` si no es `NULL` (`0` = sin límite); usar
  `quota_bytes(user, effective)`, nunca `settings.user_quota_mb`.
- **[purga]**: la purga por cuota (`domain/storage/purge.py`) nunca toca ejecuciones terminadas hace menos de 60
  minutos ni las citadas por una activa (`preview_run`, `plan_run`, `dry_run_run`); si aparece otra operación que
  cite ejecuciones, añadir su parámetro a `_LINKS`.
- **[purga]**: `storage.purge` importa `runs.service`; `runs.service` y `uploads.service` lo importan dentro de la
  función para evitar el ciclo.
- **[api]**: en los PATCH de esta app, `null` explícito significa «volver al valor por defecto» (`model_fields_set`);
  omitir el campo significa «no cambiar».
- **[e2e]**: una `Progress` de Mantine al 0 % no tiene ancho y Playwright la da por oculta: comprobar
  `aria-valuenow`.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit, push y actualizar el despliegue local (pendiente de confirmación del usuario).
- «Mi espacio» no lista ejecuciones (decisión de seguridad); al activar una cuota propia, el campo parte de 1024 MB y
  no de la cuota global vigente.
