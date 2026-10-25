# TRACEABILITY

## Session metadata
- id: 2026-10-25-plan-gaps
- fecha: 2026-10-25
- rama: claude/practical-ride-44fot0
- skill: new_feature
- fase: PLAN + AUDIT_PLAN

## Prompt issued
En util_bbdd_web se creado docs\plan\UTIL_BBDD_GAPS.md, queremos un PLAN agrupadas por cada una de los tipos de
ejecuciones incluyendo Carga, cada una tendrá sus Fases, el PLAN debe incluir el orden de ejecución simultaneo de los
dos repositorios util_bbdd_web y util_bbdd y cada una de ellas tendrá su propio commit.
Finalmente se realizará un AUDIT_PLAN de todo y dar las instrucciones necesarias para su ejecución.

## Context supplied
- `docs/plan/UTIL_BBDD_GAPS.md` (G1-G41), `docs/plan/ROADMAP.md`, ADR-006 (wheel de GitHub Releases).
- `backend/pyproject.toml`: util_bbdd fijado en 4.0.0.
- Repositorio util_bbdd (solo lectura): versión 4.0.1; rutas de cada hueco verificadas con `grep` en `src/util_bbdd/`.
- Referencias a huecos en la capa anticorrupción (`backend/app/integrations/util_bbdd/`).

## AI output summary
- Ubicación de cada hueco en util_bbdd verificada (p. ej. `doc/infrastructure/runtime/output_runtime.py` G2,
  `migrate/planner.py` G4, `dump/_models.py:172` G30, `bulk/crud.py:378` G35, `query/resolver.py:196` G18).
- Plan en 8 grupos (0 transversal base, D documentación, G grafo, C comparación, M migración, V volcado, B carga,
  T catálogo/conexiones/explorador): 42 fases `U-` (más 6 commits `release`) y 27 fases `W-` (más 6 commits de subida de versión), un commit cada una.
- Tubería de 6 olas (releases 4.1.0-4.6.0) más una ola 5.0.0 opcional; la web adapta la ola n mientras util_bbdd
  implementa la n+1.
- AUDIT_PLAN: riesgos F1-F5, T1-T7, S1-S4; decisiones D1-D5; veredicto GO_CONDICIONAL.
- Enlaces añadidos en GAPS, ROADMAP, `docs/README.md` y `zensical.toml`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` | emitido |
| Espejo en util_bbdd | `util_bbdd/.ai/sessions/2026-10-25-web-gaps-plan/PLAN.md` | emitido |

## Directrices para Futuras IAs
- **[plan]**: `docs/plan/UTIL_BBDD_GAPS_PLAN.md` es la fuente canónica del orden de las fases `U-`/`W-`; el espejo de
  util_bbdd solo resume las fases `U-`.
- **[versionado]**: la web fija util_bbdd por wheel de GitHub Releases (ADR-006); ninguna fase `W-` empieza sin el
  wheel y su `.sha256` publicados.
- **[semver]**: G30 y G35 son cambios de valor por defecto: en 4.x solo `FutureWarning`; el cambio, en 5.0.0.
- **[defensa]**: G18, G19, G20, G23, G28, G34 y G37 mantienen su control en la web aunque util_bbdd los resuelva.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Aprobación de D1-D5 antes de IMPLEMENT de la ola 1.
