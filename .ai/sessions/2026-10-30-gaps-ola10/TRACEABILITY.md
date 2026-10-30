# TRACEABILITY

## Session metadata
- id: 2026-10-30-gaps-ola10
- fecha: 2026-10-30
- rama: develop
- skill: new_feature + hotfix + version_closure
- fase: incidencias de uso (Oracle thick, volcado, migración y carga) con sus hotfixes y features; PLAN + AUDIT_PLAN
  de la ola 10 del plan de huecos (G45-G48); IMPLEMENT + AUDIT_CODE + VERSION de W-10 (util_bbdd 5.2.0) → 1.9.0

## Prompt issued
1. Cómo usar `oracle_client_path` dentro de `UBW_FILES_DIR`; documentarlo paso a paso; cargar el Instant Client 19.
2. Volcado: «Solo el propietario…», `preview_changed` con la estructura sin cambios (`/hotfix`) e `InterfaceError`.
3. Formulario del plan de migración: motor destino y «NUMBER sin precisión» (`/hotfix`).
4. Carga: ayuda del separador del CSV y schema/tabla destino desde el catálogo (`/new-feature`); `CompileError` con
   fechas → decidido corregirlo en util_bbdd.
5. PLAN y AUDIT_PLAN de lo pendiente en `UTIL_BBDD_GAPS.md` (D10-1 … D10-5 aprobadas); tras la release de
   util_bbdd 5.2.0 (otra sesión): W-10.0, W-10.1, W-10.2 y `/version-closure` → 1.9.0.

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, prompts `hotfix`, `new_feature` y `version_closure`; `publicar_version.md`.
- util_bbdd leída en el repo origen (solo lectura): 5.1.0 para diagnosticar y planificar, `v5.2.0` para verificar lo
  publicado. oracledb 26.0.1 del wheel instalado (`init_oracle_client`).
- `run.log`, `volcado.jsonl` y `run.json` de las ejecuciones fallidas del proyecto 17; variables de MariaDB del
  destino (`SHOW VARIABLES`, `Uptime`) aportadas por el usuario.

## AI output summary
- `d1809ec` feat(docker): variante `WITH_ORACLE_THICK` (`libaio1`) y `UBW_ORACLE_CLIENT_DIR` → `LD_LIBRARY_PATH` en
  el *entrypoint*; guía paso a paso. Instant Client 19.32 descomprimido en el volumen (dueño `app`) y verificado en
  `web` y `worker`; borrado el 11.2 copiado como root.
- `64e1721` hotfix(backend): `structure_hash` del volcado ordena los ciclos (G47; reproducido con 4 semillas).
- `01e3151` docs: `read_timeout` de MariaDB/MySQL en el volcado (causa del `InterfaceError`; resuelto subiéndolo).
- `dfae683` hotfix(frontend): «Elige…» en desplegables de opciones sin defecto; opciones de Oracle solo con origen
  Oracle.
- `3137551` feat(frontend): schema y tabla de la carga con `Autocomplete` desde el catálogo; ayuda del CSV.
- `f7bfa66` docs(plan): ola 10 (G48 nuevo; Grupo 10, §3, AUDIT_PLAN; GO_CONDICIONAL).
- `a7d6e1e` W-10.0, `f86056a` W-10.1, `ddbaecc` W-10.2; release 1.9.0 (D10-5) con el E2E de la carga corregido.

## Evidencias
- Backend (1.9.0): ruff, mypy, `export_openapi.py --check` y pytest con `-W error::FutureWarning
  -W error::DeprecationWarning` → 706 passed, 2 skipped, 99 deselected (integración sin banco).
- Frontend: `npm ci`, format, lint, typecheck, 140 tests (21 ficheros), build; `gen:api` sin cambios.
- Docs: `zensical build --strict`.
- Copia `ubw-backup-20261030T150011Z` (revisión 0011); `docker compose up -d --build` + `/api/health` 200 (1.9.0,
  util_bbdd 5.2.0, worker ok).
- E2E (`UBW_E2E_SQLITE=1`, `--repeat-each=2 --workers=2`, límites altos): 40 passed, 5 skipped, 1 failed
  (`bulk.spec.ts`: buscaba «Tabla destino» como `textbox`). Corregido el spec: `bulk.spec.ts` 1 passed, 1 skipped.
- W-10.1: el test nuevo da `CompileError` con util_bbdd 5.1.0 instalada a propósito y pasa con 5.2.0.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Plan y registro de la ola 10 | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` (Grupo 10, §4 «Ola 10», §6 «Ola 10» y «W-10») | completado |
| Huecos | `docs/plan/UTIL_BBDD_GAPS.md`: G45-G48 resueltos, ninguno abierto | completado |
| Logs de validación | `build/logs/w10-0.txt`, `v1.9.0_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[oracle]**: con el Instant Client 19 en Linux, `lib_dir` (`oracle_client_path`) no basta: `libclntsh` no lleva
  RUNPATH `$ORIGIN` y `libnnz19.so` solo se encuentra por `LD_LIBRARY_PATH`, que el *entrypoint* monta con
  `UBW_ORACLE_CLIENT_DIR`. `docker compose exec` no pasa por el *entrypoint*: para probar, toma `LD_LIBRARY_PATH` de
  `/proc/1/environ`. Un Instant Client por despliegue.
- **[docker]**: el contenedor corre con `cap_drop: ALL`: root no puede borrar en `/data/files` (es de `app`). Lo
  copiado con `docker compose cp` queda de root; descomprimir con un contenedor temporal y `chown 10001:10001`.
- **[volcado]**: `structure_hash` debe ser independiente del orden de los ciclos (aunque util_bbdd ≥ 5.2.0 ya los dé
  estables); un `preview_changed` sin cambios reales apunta a algo no determinista entre subprocesos *spawn*.
- **[volcado]**: util_bbdd usa `read_timeout = 30` y `write_timeout = 60` en MariaDB/MySQL; un `InterfaceError`
  «Lost connection to server during query» en `volcado.jsonl` se resuelve subiéndolos en la conexión destino.
- **[frontend]**: `Autocomplete` de Mantine tiene rol `combobox`; en jsdom su desplegable queda `display: none`
  (sin layout): en Vitest, opciones con `hidden: true` y elección con `{ArrowDown}{Enter}`. En Playwright sí se ve.
  Al cambiar una pantalla, revisar también su spec de `frontend/e2e/`.
- **[docs]**: un `|` en una celda de tabla Markdown rompe la tabla en GitHub y, escapado (`\|`), sale literal en
  Zensical: escribirlo con palabras.
- **[git]**: `docs/plan/UTIL_BBDD_GAPS.md` está guardado con CRLF aunque `.gitattributes` pide LF; editarlo
  conservando los saltos (`newline=''` en Python) hasta normalizarlo en un `chore` propio.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, avance de `main` y tag `v1.9.0` (pasos 6-7 de `publicar_version.md`): a decisión del usuario.
- Normalizar a LF `docs/plan/UTIL_BBDD_GAPS.md` en un `chore` aparte (opcional).
