# Petición — 2026-11-06 · Huecos G50 y G51 de util_bbdd

Fase pedida: **PLAN y AUDIT_PLAN** («Huecos de util_bbdd: G50 y G51 siguen abiertos. PLAN Y AUDIT_PLAN, pregunta lo
que necesites»).

Contexto: web 1.12.0 (`39cf285`, tarjetas por formato y visor Markdown M2) con util_bbdd 5.3.0 (`2841111d`).
G50 y G51 se registraron en la sesión `2026-11-06-doc-output-cards`.

## Decisiones del usuario (2026-11-06, antes del PLAN)

| # | Pregunta | Respuesta |
|---|---|---|
| D11-1 | Cómo resolver G50 | **Referenciar + ZIP**: util_bbdd escribe la ruta de Mermaid en `mkdocs.yml` sin copiar el fichero; la web deja de guardarlo por ejecución y lo añade al ZIP al vuelo desde `UBW_MERMAID_JS` |
| D11-2 | Dónde escribe util_bbdd el índice de páginas (G51) | **`manifest.json` → `pages`** (fuera de `docs/`, `format_version` 2, aditivo) |
| D11-3 | Cómo lo usa la web | **Endpoint + títulos**: `GET /runs/{id}/markdown-pages`; el árbol muestra nombres reales; las ejecuciones antiguas siguen con el árbol deducido de las rutas |
| D11-4 | Copias de `mermaid.min.js` ya guardadas | **Dejarlas**: sin limpieza ni migración; las purga la retención |

D11-5 a D11-8 (AUDIT_PLAN): aprobadas el 2026-11-06 («Todo»), junto con el commit `docs(plan)` del plan.
