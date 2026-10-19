# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `util_bbdd/.github/prompts/web_project_bootstrap.prompt.md` (contrato de la sesión)
- `util_bbdd/.github/prompts/bootstrap_ai_config.prompt.md` (capas A/B/C/D)
- `util_bbdd/src/util_bbdd/{__init__,core/capabilities,data/database_types.json}`
- Firmas verificadas: `DatabaseDocumentation`, `SchemaComparator`, `SchemaDiffReporter`, `MigrationPlanner`,
  `MigrationPlan`, `DumpOrchestrator`, `DumpConfig`, `DumpResult`, `BulkCrud`, `GraphvizRelationshipGraphExt`,
  `AuditSink`, `EngineReadinessReport`, `get_schema_metadata`, `build_conn_params`
- `util_bbdd/docs/guides/drivers.md` (SQL Server: pymssql por defecto)

## Estado actual observado
- Destino inexistente al empezar.
- util_bbdd 4.0.0: tag local, wheel en `dist/`; GitHub responde 404 sin credenciales.
- Equipo: Node 24.13, Docker 29.6, Python 3.14 local; **sin uv ni pnpm**.

## Estado Git relevante
- Rama activa: develop (creada desde `main` vacío con `git init`)
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: ninguno

## Clasificación metodológica
- Tipo principal: phase (Fase 0)
- Estado real de alcance: acotado
- Consecuencia: proceder; uv vía Docker, npm en lugar de pnpm

## Gate G0 · Context Ready
Veredicto: GO_CONDICIONAL
Condiciones pendientes (si aplica):
- Wheel de util_bbdd vendorizado (ADR-006) por no estar publicado el tag.
