# TRACEABILITY

## Session metadata
- id: 2026-11-26-refactor-check-apply
- fecha: 2026-11-26
- rama: refactor/check-apply (sobre `1690d36`, release 2.1.1)
- versión: sin versión (`[Unreleased]`; sale con la próxima)
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
`/refactor D7 check_apply triplicado` (inventario de `2026-11-26-errores-idioma`) → PLAN/AUDIT_PLAN `GO` → «sí,
adelante con IMPLEMENT».

## Context supplied
- `app/domain/runs/{migrations,dumps,bulks,targets,service}.py`; `tests/api/test_{migrate,dump,bulk}.py`,
  `tests/unit/test_{dump,migrate}_units.py`.
- Cobertura previa: `migrations.check_apply` completa; en `dumps`/`bulks` sin cubrir vista previa inexistente,
  ilegible y motor del destino cambiado.

## AI output summary
- Duplicación real en cuatro funciones (también `dumps.check_restore`): permiso + owner, vista previa reciente,
  destino escribible y del mismo motor, `confirm` = alias, una escritura por destino, y `_params_error` en tres módulos.
- Tests de caracterización antes de tocar el código: `test_apply_rule_codes` en `test_dump.py` y `test_bulk.py`
  (fijan el `code` de cada regla, incluidas las tres ramas sin cubrir); pasan con el código anterior.
- `targets.py`: `params_error`, `check_writer`, `load_fresh_preview`, `check_target`, `check_confirm`,
  `check_no_write`; nombres de permiso con claves literales (`_PERMISSION_NAMES`) para que `test_i18n` las vigile.
- Las cuatro funciones son secuencias de esas llamadas en el mismo orden; las reglas propias (errores del plan,
  `fk_blocking`, modo seco, conexiones o fichero cambiados, `confirm_truncate`, `confirm_rows`, `accept_non_atomic`,
  `pending_restore`) siguen en su módulo; las clases 403 y `PREVIEW_MAX_AGE` también.
- CHANGELOG `[Unreleased]` › Changed (interno).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Comprobaciones comunes | backend/app/domain/runs/targets.py | completado |
| Funciones simplificadas | backend/app/domain/runs/{migrations,dumps,bulks}.py | completado |
| Tests de caracterización | backend/tests/api/test_dump.py · backend/tests/api/test_bulk.py | completado |

## Directrices para Futuras IAs
- **[runs]**: una regla nueva común a las escrituras en destino va en `app/domain/runs/targets.py`; las de una sola
  operación, en su módulo. El orden de las llamadas en cada `check_apply` decide qué error ve el usuario: los tests
  `test_apply_rule_codes` lo fijan por `code`.
- **[runs]**: una escritura nueva que exija otro permiso necesita su entrada en `targets._PERMISSION_NAMES` (clave
  literal `runs.permission.*`).

## Veredicto final
Veredicto: CLOSED (sale en la 2.2.0) — AUDIT_PLAN `GO`.
- Commits `8bfc13a` (tests de caracterización) y `a3cabf6` (refactor); PR #30 con CI en verde (run 45878001117,
  suite completa de pytest y E2E incluidas), fusionado en `develop` (`37dd5ed`) y rama borrada.
