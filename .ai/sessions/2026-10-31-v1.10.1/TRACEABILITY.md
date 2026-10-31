# TRACEABILITY

## Session metadata
- id: 2026-10-31-v1.10.1
- fecha: 2026-10-31
- rama: develop
- skill: new_feature (PLAN + AUDIT_PLAN) + audit_code + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE de *Almacenamiento* en dos apartados; VERSION → 1.10.1

## Prompt issued
1. «En Almacenamiento el botón "Aplicar ahora" comprobar que pertenece a Ajustes, si es así, separar Ajustes de
   "Carga de ficheros" ya que son dos apartados diferentes. PLAN y AUDIT_PLAN».
2. «Cambiamos los títulos e IMPLEMENT» (primer apartado: «Ajustes» → «Cuota y retención»).
3. `/audit-code`; «commit»; «reconstruir el contenedor local para poner estos cambios».
4. `/version-closure v1.10.1, revisa los ultimos cambios, actualizar etiquetas y revisar si existen contenedores
   antiguos y eliminar`.

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`; prompts `audit_code` y `version_closure`; agentes Frontend Reviewer y Version
  Closer; `sync.instructions.md`; `docs/guides/publicar_version.md`.
- `StoragePage.tsx`, `useStorage.ts`, `storage.test.tsx`, `admin_storage.py` y `domain/storage/service.py` (`preview`).

## AI output summary
- Verificado: «Aplicar ahora» llama a `POST /admin/storage/maintenance` (retención y purga del worker); pertenece a la
  cuota y retención, no a los límites de la carga.
- `408f330` feat: dos tarjetas (`RetentionForm`, `UploadLimitsForm`) con borrador común `useSettingsDraft` y
  `SettingsCard` (`section` + `aria-labelledby`); los límites se guardan sin vista previa de la purga; test nuevo.
- AUDIT_CODE: APROBADO (observaciones menores, ver Pendientes).
- Release 1.10.1 (PATCH): incluye además `aba3c6e` (hotfix: carga sin verificar si falla el recuento) y `a04b3e4`
  (security: UploadGuard, rechazo temprano de subidas). Versión en CHANGELOG, pyproject, `__init__`, package*.json,
  uv.lock, openapi.json, `.env.example` y `.ai/product.md`.
- Docker local: `.env` `UBW_TAG=1.10.1`, `docker compose up -d --build`; borradas las imágenes sin uso
  `util_bbdd_web:1.9.0`, `1.8.0`, `1.7.1` y `variants` y la caché de build (`docker builder prune -f`, 23 GB).

## Evidencias
- Backend: `uv sync --frozen`, ruff format/check, mypy, `export_openapi.py --check` y pytest
  `-m "not integration" -W error::FutureWarning -W error::DeprecationWarning` → 744 passed, 2 skipped, 99 deselected
  (`build/logs/v1.10.1_backend.txt`).
- Frontend: `npm ci`, format, lint, typecheck y build en verde; `npm test` 153/154 en la primera pasada (fallo
  intermitente en `auth.test.tsx` › menú de usuario, con el backend en paralelo), 154/154 al repetir y `auth.test.tsx`
  3/3 aislado (`build/logs/v1.10.1_frontend*.txt`); `gen:api` sin cambios en `schema.d.ts`.
- `zensical build --strict` sin incidencias.
- `docker compose up -d --build` + `/api/health`: `status ok`, `version 1.10.1`, util_bbdd 5.2.0, `worker ok`.
- Sin revisiones Alembic nuevas desde v1.10.0.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Almacenamiento en dos apartados | `frontend/src/features/admin/StoragePage.tsx` | completado |
| Tests | `frontend/src/features/storage/storage.test.tsx` | completado |
| Guía | `docs/guides/usuarios_y_sesiones.md#almacenamiento` | completado |
| Release | `CHANGELOG.md` `## [1.10.1] - 2026-10-31` y campos de versión | completado |

## Directrices para Futuras IAs
- **[storage]**: *Administración → Almacenamiento* tiene dos formularios con borrador propio sobre el mismo
  `PATCH /admin/storage`: `RetentionForm` (`NUMBERS` + purga; Guardar pasa por `/preview`) y `UploadLimitsForm`
  (`LIMITS`; Guardar directo). Un ajuste nuevo va a `NUMBERS` o a `LIMITS` según lo aplique el worker o no.
- **[storage]**: «Aplicar ahora» (`/admin/storage/maintenance`) solo se desactiva con cambios pendientes de
  *Cuota y retención*.
- **[frontend-tests]**: en `storage.test.tsx` los botones «Guardar» están duplicados: buscar dentro de la región
  (`findByRole('region', { name: 'Cuota y retención' | 'Carga de ficheros' })`).
- **[frontend-tests]**: `auth.test.tsx` › «cierra sesión con la cabecera CSRF» puede fallar con la máquina cargada
  (menú de Mantine aún en `display: none`); no lanzar `npm test` en paralelo con pytest al validar una release.
- **[docker]**: la etiqueta de la imagen local sale de `UBW_TAG` en `.env` (git-ignored), no de la versión del código;
  al publicar, actualizarla también en `.env` además de `.env.example`.

## Rollback
- Sin migraciones ni variables nuevas: `git checkout v1.10.0`, `UBW_TAG=1.10.0` en `.env` y
  `docker compose up -d --build` (las imágenes anteriores se borraron en local: hay que reconstruir).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Push de `develop` y del tag `v1.10.1`, avance de `main` y release de GitHub: a decisión del usuario.
- Opcionales de AUDIT_CODE: no refrescar el uso al guardar límites de carga; tests de 422 y de «Restablecer» en
  *Carga de ficheros*.
- Heredados de 1.10.0: banco real con carga de 1 GB en MariaDB/PostgreSQL; integración de SQL Server.
