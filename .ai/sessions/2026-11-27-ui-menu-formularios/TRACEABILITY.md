# TRACEABILITY

## Session metadata
- id: 2026-11-27-ui-menu-formularios
- fecha: 2026-11-27
- rama: develop (sin commit)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL; el usuario aprueba las alternativas A/A/A con «Adelante») + IMPLEMENT +
  AUDIT_CODE

## Prompt issued
Menú contraíble a la izquierda; grupos del menú plegables; alta de rol agrupada por funcionalidad o menú; *Destinos
permitidos*: alinear *Descripción* con *Destino* y buscador «Buscar por destino o descripción»; *Auditoría*: *Fecha* y
*Resultado* completos, *Quién* al ancho del usuario, *Detalles* más estrecho pero con toda la información; decidir una
regla del proyecto para alinear etiquetas y campos con ayuda en varias columnas. «PUEDES PROPONER ALTERNATIVAS. PLAN y
AUDIT_PLAN».

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/new_feature.prompt.md`,
  `.github/instructions/frontend.instructions.md`
- `frontend/src/app/{Layout,navigation,Providers}.tsx`, `features/admin/{Roles,Allowlist,Audit}Page.tsx`,
  `components/DataTable.tsx`, `backend/app/domain/identity/permissions.py`

## AI output summary
- Decisiones (alternativas A): menú contraído a barra de iconos (64 px) con tooltip; grupos plegables con la sección
  de la página actual siempre abierta; permisos de rol agrupados según `ADMIN_NAV` + reserva por el `group` de la API;
  regla de formularios «ayuda debajo del campo» fijada en el tema.
- Verificado en Mantine 9.8: `useInputProps` lee los `defaultProps` de `InputWrapper` del tema, así que
  `inputWrapperOrder` se fija una vez (`app/theme.ts`).
- `Layout.tsx`: botón de contraer (`ubw.nav.collapsed`), secciones plegables (`ubw.nav.folded`, migra
  `ubw.nav.adminOpened`); `navigation.ts`: `isActive`, `initialFoldedSections`.
- `RolesPage.tsx` + `permissionGroups.ts` (nuevo): `Fieldset` por grupo, icono del menú y casilla *Todos* que respeta
  ADR-014.
- `DataTable`/`tableState`: `Column.nowrap`. `AuditPage`: fecha, resultado, quién e IP sin partir; *Detalles* como
  líneas `clave: valor`.
- `InlineAction.tsx` (nuevo); aplicado en Destinos, conexiones y miembros del proyecto, plantillas y carga bulk (eran
  `align="flex-end"` o `mt={50}` con ayuda encima).
- Textos es/en; regla en `frontend.instructions.md`; guía de usuario; CHANGELOG `[Unreleased]`.
- Validación: format:check, lint, typecheck y build OK; tests: 41 timeouts con la suite completa en paralelo, los 18
  ficheros pasan con `--maxWorkers=3` (173/173) y bulk aislado 12/12. Revisión visual en la imagen local
  `util_bbdd_web:ui-menu` (8081): corregido `InlineAction` (el botón quedaba en la línea de la etiqueta).
- Sin cambios de backend ni de contrato OpenAPI.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación | emitido |
| IMPLEMENT | `frontend/src/…`, `docs/guides/…`, `.github/instructions/frontend.instructions.md`, `CHANGELOG.md` | completado |
| Pruebas | `app/layout.test.tsx`, `components/formRule.test.tsx`, `features/admin/{roles,allowlist,lists,admin,permissionGroups}.test.*` | completado |

## Directrices para Futuras IAs
- **[frontend/formularios]**: la ayuda de los campos va debajo (`app/theme.ts`, `INPUT_WRAPPER_ORDER`); no se pasa
  `inputWrapperOrder` ni se alinean botones con `mt={n}`: se usa `components/InlineAction.tsx`
  (`components/formRule.test.tsx` lo comprueba).
- **[frontend/InlineAction]**: la etiqueta de Mantine es `inline-block`; el botón debe ir en un bloque o se coloca en
  su misma línea y queda 22 px alto.
- **[frontend/menú]**: estado en `localStorage`: `ubw.nav.collapsed` (barra de iconos) y `ubw.nav.folded` (clave i18n
  del título → plegada); `ubw.nav.adminOpened` solo se lee para migrar.
- **[frontend/roles]**: los grupos del formulario de rol salen de `ADMIN_NAV`; un permiso sin entrada de menú cae en
  `admin.roles.groups.<group de la API>`. Un permiso nuevo con página de administración se agrupa solo al añadir su
  entrada al menú.

## Veredicto final
Veredicto: GO (AUDIT_CODE)
Pendientes al cierre:
- VERSION: commit y, si se publica, versión 2.3.0 (a petición del usuario).
- E2E no ejecutado en esta sesión.
