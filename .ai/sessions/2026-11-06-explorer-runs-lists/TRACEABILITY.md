# TRACEABILITY

## Session metadata
- id: 2026-11-06-explorer-runs-lists
- fecha: 2026-11-06 / 2026-11-07
- rama: develop
- skill: new_feature + audit_code + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (bloques A, B y C) + AUDIT_CODE + VERSION → 1.14.0

## Prompt issued
1. Explorador (DDL cortado; ficha hasta el alto de la izquierda con scroll), eliminar ejecuciones y su contenido (solo
   administrador, con confirmación, por ejecución y por proyecto), y en todas las listas orden, 25 filas y búsqueda.
   «PLAN y AUDIT_PLAN» (D1-D4 respondidas antes del PLAN).
2. «Si a todo» (D5-D8 y commit `docs(plan)`); D6 enmendada después: la ola 11 salió como 1.13.0.
3. «Hazlo» (push, reconstrucción y esta sesión).

## Context supplied
- Código de la web 1.12.0-1.13.0; `.github/prompts/new_feature.prompt.md`, `version_closure.prompt.md`.

## AI output summary
- PLAN/AUDIT_PLAN (`b079cb9`), enmienda de versiones (`d47d905`).
- IMPLEMENT: ver [IMPLEMENT.md](IMPLEMENT.md); AUDIT_CODE: [AUDIT_CODE.md](AUDIT_CODE.md) (APROBADO).
- Comprobación en Chromium con una instancia local desechable (datos temporales, admin propio): encontró el alto
  mal medido del explorador, corregido.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN / AUDIT_PLAN | `.ai/sessions/2026-11-06-explorer-runs-lists/` | aprobados |
| IMPLEMENT | commits `026d8c8`..`bd549b6` | completado |
| AUDIT_CODE | [AUDIT_CODE.md](AUDIT_CODE.md) | APROBADO |

## Directrices para Futuras IAs
- **[frontend/Mantine]**: `ScrollArea` con solo `mah` no se desplaza (recorta el contenido); para scroll vertical hace falta `h` (o `ScrollArea.Autosize`). El explorador usa contenedores flex con `minHeight: 0` y `ScrollArea h="100%"`.
- **[frontend/explorador]**: el alto de escritorio se mide con una ref de callback (`useFillHeight`): el contenedor aparece después del cargador de schemas; medir al montar el panel da 0 como borde superior.
- **[frontend/listas]**: toda lista de recursos usa `components/DataTable` (`mode="server"` con `useListState` + `listQuery`, o `mode="client"` con `value`/`searchable`); `PAGE_SIZE` = 25 está en `components/tableState.ts` (no en `DataTable.tsx`, por `react-refresh/only-export-components` y para no chocar en mayúsculas con Windows).
- **[backend/listas]**: el orden se declara con un `Literal` por endpoint y un mapa columna → expresión en el servicio, aplicado con `domain/sorting.order_by` (desempate por clave primaria); las búsquedas usan `like_pattern` con `escape="\\"`.
- **[backend/admin]**: un admin no miembro sigue recibiendo 404 en la API de proyectos; las ejecuciones de todos los proyectos solo se ven por `/admin/runs` (metadatos). Borrar = fila + carpeta (la purga deja la fila `purged`).
- **[frontend/tests]**: `userEvent.setup()` sustituye `navigator.clipboard`: leer lo copiado con `navigator.clipboard.readText()`.

## Veredicto final
Veredicto: CLOSED (1.14.0)
Pendientes al cierre:
- R1 (borrado por proyecto sin job, no medido con miles de ejecuciones) y R4 (estado de las listas en la URL).
