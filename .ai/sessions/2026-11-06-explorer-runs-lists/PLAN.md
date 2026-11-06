# PLAN — Explorador a toda altura, eliminación de ejecuciones (admin) y listas con orden, paginación y búsqueda

Sesión `2026-11-06-explorer-runs-lists` · web 1.12.0 + plan de la ola 11 (`c6cb768`) · Fase: PLAN (sin implementar).
Decisiones D1-D4 en [00_REQUEST.md](00_REQUEST.md). Tres bloques independientes, un commit cada uno.

## 1. Estado actual (verificado en el código)

### A — Explorador

| Pieza | Dónde | Hoy |
|---|---|---|
| Columna izquierda | `frontend/src/features/explorer/ExplorerPage.tsx:65-129` | Selector de schema, casilla, filtro, botón y árbol en `ScrollArea h={520}` |
| Ficha | `ExplorerPage.tsx:130-142` | `Card mih={300}`: crece con el contenido |
| DDL | `ObjectDetail.tsx:28-30` | `ScrollArea type="auto" mah={480}` → **el `ScrollArea` de Mantine no se desplaza solo con `mah`** (hace falta `h` o `ScrollArea.Autosize`): el DDL largo queda **cortado** a 480 px sin barra. Es el fallo que se ve |
| Columnas, Claves, Índices, Relaciones | `ObjectDetail.tsx:36-…` | `Table.ScrollContainer minWidth={640}` (solo horizontal); la ficha crece sin límite |
| Marco | `app/Layout.tsx:30` | `AppShell` con cabecera de 56 px y `padding="md"`; el explorador va en las pestañas *Metadatos* / *Queries nombradas* de la conexión |

### B — Ejecuciones

- `domain/runs/service.py:354-383`: `purge` (editor; solo terminadas; no si un volcado dejó constraints sin restaurar,
  G31) borra carpeta y artefactos y deja la fila `purged`. La retención hace lo mismo.
- `domain/projects/service.py:140-158`: `delete_project` rechaza con ejecuciones activas, borra la fila (cascada) y
  después la carpeta.
- Acceso: `get_access` → un admin **no miembro recibe 404** (`domain/projects/service.py:11`); `AdminUser`
  (`api/deps.py:72-83`) para las rutas de administración.
- FK hacia `runs`: solo `artifacts.run_id` (`ON DELETE CASCADE`). `runs.relaunched_from` es texto sin FK; otras
  referencias son parámetros (`markdown_previous_run`, `baseline` de la evolución), que se resuelven al usarse.
- Cuota: suma de `runs.size_bytes` (`domain/storage/purge.py`); borrar la fila libera la cuota.

### C — Listas

| Tipo | Listas | Hoy |
|---|---|---|
| Paginadas en el servidor (`limit`/`offset`, `MAX_PAGE_SIZE` 200) | Usuarios, sesiones, auditoría, almacenamiento (uso), conexiones, proyectos, ejecuciones (mías y del proyecto) | 50 por página; `q` en todas salvo **sesiones** y **auditoría** (esta filtra por acción); **ninguna ordena** (orden fijo en el servicio) |
| Completas en el cliente | Destinos permitidos, queries nombradas, motores, plantillas (globales y del proyecto), miembros y conexiones del proyecto | Sin paginación, búsqueda ni orden |
| Fuera de alcance (D4) | Visores de una ejecución (diff, plan, volcado, carga, migración), explorador, resultados SQL, parámetros del detalle, salud | — |

## 2. Bloque A — Explorador a toda altura (`fix(frontend)`)

- En escritorio (`md` o más), el explorador ocupa el alto disponible de la ventana:
  `height: calc(100dvh - var(--app-shell-header-height) - <cabecera de la página y pestañas>)`, con mínimo de
  480 px. Las dos columnas se estiran a ese alto (flex en columna).
- Columna izquierda: los controles arriba y el árbol con `flex: 1` y su propio scroll (sustituye `h={520}`).
- Ficha: título fijo; `Tabs` con `flex: 1; min-height: 0`; **cada panel** (Columnas, Claves, Índices, Relaciones,
  DDL) en un `ScrollArea` con `h="100%"`, scroll vertical y horizontal. Las tablas con cabecera fija
  (`Table stickyHeader`). Vistas y rutinas (solo DDL) igual.
- DDL: `Code block` dentro del `ScrollArea` de altura completa; sin `mah`. Botón «Copiar» (Mantine `CopyButton`)
  opcional (D5).
- Móvil (`base`): columnas apiladas; la ficha con un máximo de `70dvh` y scroll interno (sin altura de ventana
  completa para no atrapar el scroll de la página).
- Ficheros: `ExplorerPage.tsx`, `ObjectDetail.tsx`, quizá un `explorer.module.css` (sin dependencias).
- Tests: DDL largo dentro de un contenedor con scroll (no recortado: sin `mah`, con `overflow`); los cinco paneles
  dentro de su `ScrollArea`. La altura real se comprueba en la E2E o a mano (jsdom no calcula alturas).

## 3. Bloque B — Eliminar ejecuciones (administrador) (`feat(backend,frontend)`)

### Contrato HTTP

```text
GET    /api/v1/admin/runs?q=&project_id=&status=&sort=&order=&limit=&offset=   → AdminRunPage
DELETE /api/v1/admin/runs/{run_id}                                              → 204
POST   /api/v1/admin/projects/{project_id}/runs/delete  {confirm: "<nombre>"}  → AdminRunsDeleteOut
```

- `AdminRunOut`: `id`, `project_id`, `project_name`, `operation`, `status`, `username`, `created_at`,
  `finished_at`, `size_bytes`, `artifacts_count`. **Sin** `params`, `error_message` ni artefactos (D1: el admin no
  ve el contenido de proyectos ajenos).
- `DELETE /admin/runs/{id}`: 409 si está en cola o en curso, o si es un volcado con constraints sin restaurar (G31);
  404 si no existe. Borra la fila (los artefactos por cascada) y **después del commit** la carpeta.
- `POST …/runs/delete`: `confirm` debe ser el nombre exacto del proyecto (422 si no). Borra todas las terminadas
  (también las `purged`), **omite** activas y volcados pendientes (D3) y devuelve
  `{deleted, skipped_active, skipped_pending_dump, freed_bytes}`.
- Todas con `AdminUser` y CSRF (como el resto de mutaciones). Auditoría: `run.delete` (id, proyecto, operación,
  usuario, tamaño) y `project.runs_delete` (proyecto y contadores).

### Backend

- `domain/runs/admin.py` (nuevo): `list_all_runs`, `delete_run`, `delete_project_runs` (reutiliza
  `TERMINAL_STATUSES`, `dump_journal`, `run_dir`, `remove_tree`).
- `api/v1/admin_runs.py` (nuevo) + `schemas_admin_runs.py`; registro en el router de `/admin`.
- `domain/identity/audit.py`: `RUN_DELETE`, `PROJECT_RUNS_DELETE`.

### Frontend

- `features/admin/RunsAdminPage.tsx` (nuevo, ruta `/admin/runs`, menú de Administración): tabla del bloque C
  (orden, 25 por página, búsqueda por id, proyecto, operación o usuario; filtros de estado y proyecto).
- Acción por fila **Eliminar** → modal con resumen y escribir `ELIMINAR` para habilitar el botón.
- Acción por fila **Eliminar todas las de «proyecto»** → modal con el número de ejecuciones y el espacio, y escribir
  el **nombre del proyecto** (el mismo valor va en `confirm`). Resultado: notificación con borradas y omitidas.
- Detalle de una ejecución borrada (alguien la tenía abierta): el 404 existente; el SSE ya termina con `gone`.
- «Relanzada desde» que apunta a una borrada: el enlace da 404 (aceptado, ver AUDIT_PLAN F4).

### Tests

API: 403 sin admin, 404 de inexistente, 409 activa y volcado pendiente, 204 con carpeta borrada y cuota liberada,
auditoría sin `params`; borrado por proyecto con `confirm` erróneo (422), con activas omitidas y recuentos; listado
de todos los proyectos sin `params`. Frontend: modal deshabilitado hasta escribir la confirmación; resultado con
omitidas; página oculta en el menú a no administradores.

## 4. Bloque C — Listas con orden, paginación de 25 y búsqueda (`feat(backend,frontend)`)

### Componente común

`components/DataTable.tsx` (nuevo, sin dependencias): columnas declaradas (`key`, título, celda, `sortable`,
`searchable`), cabeceras con botón de orden (`aria-sort`, flecha), caja de búsqueda, `Pagination` de Mantine y
recuento («26-50 de 312»). Dos modos:

- **Servidor**: `page`, `sort`, `order`, `q` controlados; el padre los pasa a su hook de TanStack Query
  (`keepPreviousData`). La búsqueda espera 300 ms (debounce) y vuelve a la página 1.
- **Cliente**: filtra, ordena (`localeCompare` con `numeric`, fechas por valor) y pagina en memoria.

Tamaño de página **25** en todas (`PAGE_SIZE` 50 → 25 en `useAdmin`, `useConnections`, `useProjects`, `useRuns`).

### Backend (listas paginadas)

- Parámetros nuevos `sort` (un `Literal` de columnas permitidas por endpoint) y `order` (`asc`|`desc`); por defecto
  el orden de hoy. Lista blanca → `ORDER BY` con desempate por `id` (paginación estable).
- `q` nuevo en **sesiones** (usuario, IP o agente) y **auditoría** (acción, actor u objetivo), sin quitar el filtro de
  acción.
- Endpoints: `users`, `sessions`, `audit`, `admin_storage/usage`, `connections`, `projects`, `runs` (mías y del
  proyecto) y el nuevo `admin/runs`. Columnas exactas **a fijar en IMPLEMENT** con los modelos (p. ej. ejecuciones:
  `created_at`, `operation`, `status`, `username`, `duration`, `size_bytes`).
- OpenAPI exportado y cliente regenerado (regla 7).

### Frontend (listas)

| Lista | Modo |
|---|---|
| Usuarios, sesiones, auditoría, almacenamiento (uso), conexiones, proyectos, ejecuciones (mías, del proyecto, admin) | Servidor |
| Destinos permitidos, queries nombradas, motores, plantillas globales y del proyecto, miembros, conexiones del proyecto | Cliente |

Las listas conservan sus filtros actuales (estado de ejecución, acción de auditoría…) junto a la búsqueda.

### Tests

Unitarios de `DataTable` (orden asc/desc y `aria-sort`, búsqueda, páginas, vacío); por cada endpoint: orden
permitido, valor no permitido → 422, desempate estable, `q` nuevo en sesiones y auditoría; frontend: una lista de cada
modo con las peticiones (`sort`, `order`, `q`, `limit=25`).

## 5. Datos, migraciones y dependencias

Sin migración (no cambia el esquema; índices existentes en `created_at`/`project_id`; si un orden nuevo lo necesita
se valora en IMPLEMENT). Sin dependencias nuevas.

## 6. Versión y commits

| Commit | Contenido |
|---|---|
| `fix(frontend): explorador a toda altura con scroll en cada apartado` | Bloque A |
| `feat(backend,frontend): eliminar ejecuciones desde administración` | Bloque B (+ OpenAPI) |
| `feat(backend,frontend): listas con orden, paginación de 25 y búsqueda` | Bloque C (+ OpenAPI) |
| `release: v1.13.0` | D6 (aprobada): la ola 11 pasa a 1.14.0 |

## 7. Fuera de alcance

Visores de resultados, explorador y resultados SQL con paginación (D4); estado de la lista en la URL; borrado de
proyectos por el admin (ya existe para su propietario); papelera o deshacer.
