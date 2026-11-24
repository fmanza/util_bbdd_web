# TRACEABILITY

## Session metadata
- id: 2026-11-24-usuarios-transferencia
- fecha: 2026-11-24
- rama: develop
- skill: new_feature + audit_code + version_closure
- fase: PLAN + AUDIT_PLAN entrega B (GO_CONDICIONAL, aprobado con las propuestas por defecto) → IMPLEMENT →
  AUDIT_CODE (APROBADO CON CONDICIONES; m1, m2 y n1 corregidos) → VERSION 1.22.0 (entregas A y B)

## Prompt issued
«haz el commit y PLAN de la entrega B» → «adelante, implementa la entrega B» → «AUDIT_CODE y VERSION».

## Context supplied
- Entrega A en `dd40024` ([sesión](../2026-11-24-usuarios-borrado/TRACEABILITY.md)): borrado bloqueado por
  pertenencia, creación de proyectos y conexiones en uso.
- Rutas que dependen de `projects.owner_id`: calculadas (`project_folder`, `uploads_folder`, `templates_folder`,
  `run_relative_path`) y guardadas (`runs.workspace_path`, `uploads.path`, `document_templates.path`; el PLAN las
  creía calculadas para las plantillas). Artefactos relativos al run.
- Decisiones aprobadas: no ceder conexiones privadas sin uso; el destino no pasa a ser miembro de un proyecto creado
  del que el origen ya no lo era; diario y recuperación incluidos.

## AI output summary
- Backend:
  - `domain/identity/transfer.py` (nuevo): `transfer_preview` / `TransferPlan` (motivos `same_user`,
    `target_inactive`, `target_not_admin`, `busy`), `_renamed` / `_free_name` (« (de <origen>)», « 2»…, máximo 100),
    `transfer_user` (bloqueo de escritura, `refresh` del destino, `owner_id`, `_repoint` con
    `new || substr(col, len(old) + 1)` en las tres tablas, propiedad, conexiones, `remove_memberships`, auditoría
    `user.transfer`), `_apply_moves` (diario `.transfers/<ulid>.json` → mover → `commit` → borrar diario; deshace si
    falla), `recover_transfers`, `relocate_if_transferred`.
  - `workspace/layout.py`: `project_prefix`. `uploads/service.py` y `templates/service.py`: `flush` +
    `relocate_if_transferred` antes de guardar la fila. `jobs/worker.py`: `recover_transfers()` en `start()`.
  - `errors.py`: `TransferBlockedError`. `audit.py`: `USER_TRANSFER`. API: `GET /users/{id}/transfer-preview`,
    `POST /users/{id}/transfer`; esquemas `TransferItem`, `UserTransfer`, `UserTransferRequest`.
- Contrato: `openapi.json` exportado y `schema.d.ts` regenerado.
- Frontend: `TransferUserModal.tsx` (nuevo: destino con búsqueda en servidor, vista previa, «Quitarlo además de todos
  los proyectos» activado, confirmación); `DeleteUserModal.tsx` (botón *Transferir…* salvo `self`/`last_admin`, vuelve
  a comprobar al terminar); `useAdmin.ts` (`useActiveUserOptions`, `useTransferPreview`, `useTransferUser`); i18n.
- AUDIT_CODE: m1 destino leído antes del bloqueo → `db.refresh(target)`; m2 el `Select` buscaba por la etiqueta
  elegida y la sacaba de la lista → no se busca por ella y el elegido se conserva en `data`; n1 renombrados con origen =
  destino → sin renombrados. Riesgos residuales documentados en la enmienda de ADR-013.
- Docs: enmiendas de ADR-013 y ADR-005, `usuarios_y_sesiones.md` («Transferir proyectos y conexiones»),
  `CHANGELOG.md`.
- Tests: backend `test_user_transfer.py` (15: flujo completo con run, fichero y plantilla reales y borrado posterior,
  pertenencias, nombres, motivos, permisos, CSRF, fallo al mover, fallo al confirmar, recuperación en los dos
  sentidos, worker, recolocación, sin carpetas); frontend `admin.test.tsx` (+2).
- VERSION 1.22.0: versión sincronizada en los siete sitios de `sync.instructions.md`.
- Validaciones ejecutadas (con 1.22.0): ruff format/check, mypy, `export_openapi.py --check`, pytest completo
  (865 passed, 101 skipped, 20 min); frontend format:check, lint, typecheck, `npm run build`, `zensical build
  --strict`; Vitest 242/257 con `--no-file-parallelism`: los 15 fallos son timeouts de 5 s en ficheros no tocados
  (carga, ejecuciones, conexiones); repetidos uno a uno quedan 6, y 3 de ellos fallan igual en una copia limpia de
  `dd40024` (máquina cargada, no regresión). `admin.test.tsx` 16/16. No ejecutados: Docker + `/api/health`,
  Playwright.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | respuesta de la sesión (resumen en este documento) | aprobado |
| IMPLEMENT (B) | `backend/…` · `frontend/…` · `openapi/openapi.json` · `docs/…` | completado |
| Versión | 1.22.0 | preparada, sin commit |

## Directrices para Futuras IAs
- **[workspace]**: tres tablas guardan rutas bajo `users/<owner_id>/projects/<id>`: `runs.workspace_path`,
  `uploads.path` y `document_templates.path`. Una ruta nueva guardada ahí debe añadirse a `_repoint` en
  `domain/identity/transfer.py` (ADR-005, enmienda).
- **[workspace]**: `workspace/.transfers/*.json` son diarios de transferencias a medias; no borrarlos a mano: el worker
  los resuelve al arrancar comparando `projects.owner_id` con el destino del diario.
- **[transferencia]**: en Linux mover la carpeta con una subida en curso hace fallar esa subida (el `tmp.replace` usa la
  ruta antigua) y deja un `.tmp-*` en la carpeta nueva; `relocate_if_transferred` solo cubre el tramo entre escribir
  el fichero y guardar la fila.
- **[frontend]**: un `Select` de Mantine con búsqueda en servidor pone la etiqueta elegida como `searchValue`: no buscar
  por ella y conservar la opción elegida en `data`.
- **[tests]**: no relanzar código mientras corre la suite completa de pytest (~15-20 min): los módulos ya importados
  no ven los cambios.
- **[tests]**: con la máquina cargada, `bulk.test.tsx`, `markdown.test.tsx` y `runs.test.tsx` superan el límite de 5 s
  de Vitest también en `dd40024`; no tomar esos timeouts por regresiones sin repetirlos en serie.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commits (`feat` de la entrega B y `release: v1.22.0`) propuestos, no ejecutados.
- `docker compose up -d --build` + `/api/health` y Playwright antes de publicar; tag y despliegue
  (`docs/guides/publicar_version.md`, pasos 5-8).
