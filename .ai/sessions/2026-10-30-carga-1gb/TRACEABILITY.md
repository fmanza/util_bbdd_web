# TRACEABILITY

## Session metadata
- id: 2026-10-30-carga-1gb
- fecha: 2026-10-30
- rama: develop
- skill: hotfix + new_feature + version_closure
- fase: incidencias de la carga tras la 1.9.0 (hotfixes), ids propios y `exclude_autoincrement_pk` (`/new-feature`);
  PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE de ficheros grandes en la carga (límites administrables y CSV de hasta
  1 GB); VERSION → 1.10.0

## Prompt issued
1. «Hemos cargado un fichero y en "Ejecución bulk_apply" indica que todas las ha apartado» → el mensaje confunde
   (`/hotfix`).
2. «None of [Index(['ID'], dtype='str')] are in the [columns]» en un insert sin la PK (`/hotfix`).
3. Por qué la web no ofrece `exclude_autoincrement_pk` ni `override_identity` de util_bbdd (`/new-feature`, dos
   pasos: ids propios y detección de la PK autoincremental, opción D).
4. Excel: al elegir una hoja vacía no deja elegir otra (`/hotfix`).
5. «Necesito subir archivos de 1 GB para la carga, quiero que sea configurable en la administración» → propuesta,
   PLAN y AUDIT_PLAN (D-1 … D-4 aprobadas con «IMPLEMENT»), dos commits, rebuild del contenedor.
6. Qué significa «El .xlsx descomprimido es demasiado grande»; qué queda pendiente; release 1.10.0.

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, prompts `hotfix`, `new_feature` y `version_closure`; `publicar_version.md`.
- util_bbdd 5.2.0 del wheel instalado (solo lectura): `BulkCrud.bulk_*_from_df`, `bulk_*_from_chunks`,
  `bulk_session`, `sync_pk_sequences`, `progress.ProgressEvent`.
- CSV `pruebas_bulk_202610301057.csv` y ejecuciones fallidas aportadas por el usuario.

## AI output summary
- `eb616a7` hotfix: el resultado de la carga cuenta las filas aplicadas (recuento del destino), no las enviadas
  (G37), y avisa si todas se apartaron.
- `6f539cf` hotfix: insert con la PK autoincremental en «(no cargar)».
- `f125300` feat: `override_identity` (PostgreSQL) y ajuste del contador de la PK (`sync_pk_sequences`) en la carga.
- `8fb16dd` feat: «Que la BD asigne los ids» (`exclude_autoincrement_pk`) con detección de la PK autoincremental.
- `fa68d5d` hotfix: Excel con hojas vacías (el selector depende del tipo del fichero; `NoColumnsError`).
- `728b5d4` feat (Fase 1): `upload_max_mb`, `upload_max_uncompressed_mb` y `bulk_max_rows` administrables
  (ADR-012); el job recibe los ajustes efectivos.
- `db2ddc5` feat (Fase 2): CSV por bloques (`iter_frames`), vista previa con SQL de muestra y `memory_warning`,
  carga con `bulk_*_from_chunks`, subida con progreso y cancelación (XHR), `TMPDIR` en el volumen workspace.
- AUDIT_CODE de la Fase 2: APROBADO CON CONDICIONES (ver Pendientes).
- Release 1.10.0: versión en CHANGELOG, pyproject, `__init__`, package*.json, uv.lock, openapi.json, `.env.example`
  y `.ai/product.md`; esta sesión.

## Evidencias
- R4 verificado en util_bbdd 5.2.0: `bulk_insert_from_chunks` y `__stream_operation` abren
  `self._rejects.operation(...)`: `on_error="isolate"` funciona por bloques (test `test_bulk_chunks.py` con SQLite).
- Rendimiento (local, CSV de 2 000 000 filas, 147 MB): `iter_frames` pico 45 MB frente a 381 MB de `read_frame`;
  vista previa 5,6 s y carga en SQLite 14 s, RSS +~125 MB, `verified` True.
- Fase 1 aislada (`git stash --keep-index`): backend 77 tests de storage/bulk, frontend 28; ruff, mypy y contrato.
- Integración con banco (ejecutada sin querer en una pasada): fallos y errores solo en `[sqlserver]` (motor del
  banco caído); los ERROR de `tests/api` de esa pasada los causó `-p no:logging` (sin `caplog`).
- Release 1.10.0: backend `uv sync --frozen`, ruff format/check, mypy, `export_openapi.py --check` y pytest
  `-m "not integration" -W error::FutureWarning -W error::DeprecationWarning` → 732 passed, 2 skipped, 99 deselected;
  frontend `npm ci`, format, lint, typecheck, 152 tests (21 ficheros) y build; `gen:api` sin cambios;
  `zensical build --strict`; copia `ubw-backup-20261030T200235Z` (revisión 0011, verificada); `docker compose up -d
  --build` + `/api/health` ok (1.10.0, util_bbdd 5.2.0, worker ok); E2E `bulk.spec.ts` (`UBW_E2E_SQLITE=1`) 1 passed
  contra la app 1.10.0 (subida por XHR). Logs en `build/logs/v1.10.0_*`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Lectura por bloques | `backend/app/domain/uploads/files.py` (`iter_frames`, `CHUNK_ROWS`) | completado |
| Carga por bloques | `backend/app/integrations/util_bbdd/bulk.py` (`Frames`, `_scan`, `_stream`, `SQL_SAMPLE_ROWS`) | completado |
| Límites administrables | `backend/app/domain/storage/settings.py`, *Administración → Almacenamiento* | completado |
| Subida con progreso | `frontend/src/features/bulk/useBulk.ts` (`sendUpload`, `isAbort`) | completado |
| ADR | ADR-010 y ADR-012 enmendados | completado |
| Despliegue | `docs/guides/deployment.md#ficheros-grandes-en-la-carga` | completado |

## Directrices para Futuras IAs
- **[carga]**: `build_bulk_preview` y `run_bulk` aceptan un `DataFrame` o `Frames` (función que reabre el fichero y
  da bloques). Sin plan paralelo la carga va por `bulk_*_from_chunks` (una transacción, rechazos incluidos); con plan
  paralelo se junta en memoria porque `*_from_chunks` no reparte en hilos.
- **[carga]**: `SQL_SAMPLE_ROWS` (1 000) sale del **primer bloque**: debe ser ≤ `CHUNK_ROWS` (50 000). Las
  coincidencias por PK se deduplican por bloque, no entre bloques.
- **[carga]**: `bulk_*_from_chunks` emite el progreso con `total=None`: `RunProgress(total=...)` usa las filas de la
  vista previa.
- **[storage]**: un ajuste administrable nuevo exige `StorageValues`, `_ADAPTERS`, `StorageSettingsOut`/`StorageUpdate`,
  `ENV` y el formulario de `StoragePage.tsx`, y el fixture de `storage.test.tsx`. El job solo los ve porque `run_job`
  aplica `effective_settings`.
- **[frontend]**: la subida usa `XMLHttpRequest` (progreso); los tests la simulan con `FakeXhr` (`bulk.test.tsx`),
  no con el `fetch` de `stubApi`.
- **[tooling]**: en el Bash de Claude Code, un heredoc con `'EOF'` convierte `\\n` en salto de línea y `\\0` en NUL:
  para scripts de Python con barras invertidas, escribirlos con Write en el scratchpad y ejecutarlos.
- **[git]**: para separar un cambio en dos commits sin `git add -p`: hunks con un script + `git apply --cached`, y
  verificar el índice con `git stash push --keep-index` antes del commit.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, avance de `main` y tag `v1.10.0`: a decisión del usuario.
- Banco real: carga de 1 GB contra MariaDB/PostgreSQL (transacción y log), `exclude_autoincrement_pk` y `pk_sync`;
  relanzar la integración de SQL Server cuando el banco esté arriba.
- Seguridad (AUDIT_CODE, previo): el multipart se recibe entero antes de comprobar sesión y `Content-Length`; lo
  acota el proxy. Mejora propuesta: rechazo temprano en el middleware.
- Opcional: subida reanudable por partes si la subida de 1 GB falla en la red del usuario.
