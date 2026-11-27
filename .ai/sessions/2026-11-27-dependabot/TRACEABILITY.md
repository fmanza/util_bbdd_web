# TRACEABILITY

## Session metadata
- id: 2026-11-27-dependabot
- fecha: 2026-11-27
- rama: PR de Dependabot #26 (npm) y #32 (GitHub Actions; sustituye al #18), fusionados en `develop` (`e230846`)
- versión: 2.2.1
- skill: version_closure (D9 del inventario de deuda)

## Prompt issued
«D9 Dependabot, que falta» → revisar los PR abiertos → «si» (empezar) → «si» (fusionar).
Confirmado por el usuario: revisión humana del inglés hecha y correcta; `noop` y *Administración → Usuarios* probados
tras la 0017.

## AI output summary
- #18 (5 actions, CI anterior a `audit`/`e2e`): `@dependabot rebase` → Dependabot lo cierra y abre #32 (6 actions,
  con `upload-artifact` 7); todas con ≥ 2 semanas; CI completo en verde.
- #26 (23 paquetes npm): `frontend` fallaba. Causas: `Select.onChange` con `option` posiblemente `null` (Mantine 9.8)
  y jsdom 31, que evalúa los `@media` de `<style data-mantine-styles="classes">` con una ventana fija de 1024 px (ni
  `innerWidth` ni `defineProperty` lo cambian): la hamburguesa `hiddenFrom="sm"` quedaba `display: none`. Arreglo en
  la rama del PR (`ef4871a`): guarda en `TransferUserModal`; `Providers` con `withGlobalClasses` (por defecto `true`),
  `false` en `renderRoute`/`renderWithProviders`. CI completo en verde.
- Versión 2.2.1 sincronizada; CHANGELOG `[2.2.1]`.

## Directrices para Futuras IAs
- **[frontend/tests]**: con jsdom 31 los `@media` se evalúan con 1024 px: un control con `hiddenFrom`/`visibleFrom` se
  oculta en las pruebas salvo con `withGlobalClasses={false}` (ya lo ponen los helpers de `src/test/render.tsx`; un
  test que monte `Providers` a mano debe pasarlo).
- **[dependabot]**: un PR de Dependabot con CI de un workflow anterior se actualiza con `@dependabot rebase`; si lo
  cierra («updatable in another way»), abre otro con el grupo al día. Si hace falta adaptar código, el commit va a su
  rama y Dependabot deja de rebasarla.

## Veredicto final
Veredicto: CLOSED (2.2.1). Sin PR de Dependabot abiertos; D9 queda en el ciclo mensual.
Pendientes al cierre: publicación de la 2.2.1 y despliegue local; `.trivyignore` el 2026-12-26; `PYSEC-2026-217` el
2027-02-26.
