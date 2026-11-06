# AUDIT_CODE — Documentación Markdown (util_bbdd 5.3.0)

Auditoría de solo lectura de los cambios sin commit de la sesión (32 ficheros modificados y 6 nuevos sobre
`f521610`). Agentes: Code Auditor y Frontend Reviewer. Foco: todo.

## PLAN

- **Backend**: `integrations/util_bbdd/documentation.py`, `jobs/operations/documentation.py`,
  `domain/runs/{documentations (nuevo), diff, operations, service}.py`, `domain/templates/{files, service}.py`,
  `api/v1/{runs, templates, schemas_projects, schemas_templates}.py`, `pyproject.toml`, `uv.lock`.
- **Contrato**: `openapi/openapi.json`, `frontend/src/api/schema.d.ts`.
- **Frontend**: `features/runs/{LaunchRunModal, RunDetailPage, RunOutputs, ArtifactBrowser, useRuns, markdown (nuevo)}`,
  `compare/DiffViewer.tsx`, `templates/TemplatesPanel.tsx`, `i18n/es/features.json`.
- **Tests**: `tests/api/test_documentation_markdown.py`, `tests/unit/test_documentation_markdown_units.py`,
  `markdown.test.tsx`; ajustes en `test_health`, `test_runs`, `test_documentation_units` y `fixtures_runs`.
- Contrastado con util_bbdd `v5.3.0` (repo origen): `_trace.py`, `_changes.py`, `_site.py`, `_text.py`.

## AUDIT_PLAN

- Funcional: regresión de Word/Excel/HTML; opciones ocultas en el formulario; selección de la documentación anterior.
- Técnico: recolocación de la carpeta, `imprimir` con y sin Markdown, cadena de excepciones, volumen de artefactos.
- Seguridad: rutas del servidor en mensajes (regla 5), IDOR de `markdown_previous_run`, subida del mapa, XSS desde el
  mapa o los comentarios de la BD, inyección en `mkdocs.yml`.

## AUDIT_CODE

### Hallazgos

| # | Sev. | Estado | Dónde | Hallazgo |
|---|---|---|---|---|
| H1 | Media | **Confirmado** | `backend/app/integrations/util_bbdd/documentation.py:57,170` | `_ABSOLUTE_PATH` casa con cualquier `/x/` aunque no empiece la ruta: `public_message("… ruta src/a/b.py …")` → `src<fichero>` y `https://jira.example.com/browse/VEN-7` → `https:/<fichero>` (comprobado ejecutándolo). Hoy util_bbdd no repite valores en los errores del mapa, pero sí las claves (`tables.<clave>`, `routines."PROCEDURE:a/b"`), así que el mensaje puede salir deformado. No filtra nada: el fallo es de más saneado, no de menos. **Corrección**: que la ruta empiece al principio o tras un espacio, comilla o paréntesis (`(?<![^\s'"(])`) y que no siga a `:` de un esquema de URL; test con una clave con `/` y con una URL |
| H2 | Baja | Confirmado (lectura) | `frontend/src/features/runs/LaunchRunModal.tsx:190` y `paramSchema` | Zod valida también los campos ocultos: si se escribe una profundidad fuera de rango (p. ej. `9`), se desmarca *Markdown* y se lanza, el formulario no se envía y el error está en un campo que no se ve. Mejor no validar (o vaciar) los campos con `requires` ocultos |
| H3 | Baja | Confirmado (lectura) | `LaunchRunModal.tsx:110,260` | Una documentación anterior elegida sigue en el valor del formulario si después se cambia la conexión o el schema y deja de estar entre las opciones. El backend lo rechaza con 422 («otra conexión») y el error se ve en el campo: no es incorrecto, pero se puede limpiar el valor si ya no es comparable |
| H4 | Baja | Confirmado (lectura) | `frontend/src/features/runs/useRuns.ts:58` | El selector solo ve las 50 últimas documentaciones correctas del proyecto, y el filtro por conexión, schema y Markdown se hace en el cliente: con muchas documentaciones de otras conexiones o sin Markdown, una comparable más antigua no aparece. Aceptable en esta versión; documentarlo o filtrar en el servidor más adelante |
| H5 | Baja | Hipótesis | `backend/app/domain/runs/documentations.py:52` | La conexión se compara por **alias**. Si el alias del proyecto se reasigna a otra BD del mismo motor, se aceptan cambios entre dos bases distintas (un motor distinto sí lo rechaza util_bbdd → `invalid_previous`). Los runs no guardan el `connection_id`; riesgo residual |
| H6 | Info | — | `frontend/src/features/templates/TemplatesPanel.tsx:184` | Ternario anidado (`trace ? … : editable ? … : …`): correcto, pero menos legible que extraer la celda a un componente |

Sin hallazgos en:

- **Regresión**: sin `markdown`, `build_imprimir` no añade el bloque (test); `_SITE_FORMATS` mantiene la ruta y la
  portada del HTML; Graphviz sigue siendo obligatorio con Word/HTML y diagramas (test).
- **Cadena de excepciones**: `markdown_input_error` solo convierte `DocumentationConfigError` con `markdown.trace_map`
  o `markdown.previous`; los fallos de plantilla Word/Excel no lo contienen y siguen su reintento; la cancelación pasa
  intacta.
- **`mkdocs.yml`**: util_bbdd escribe `site_name` con `json.dumps` (`_site.py:30`), sin inyección YAML; además, el
  patrón impide caracteres de control.
- **XSS**: notas, etiquetas y nombres pasan por `md_text` (entidades HTML y puntuación de Markdown escapada); solo
  `http(s)` se enlaza (`_trace.py:47,230`). La vista previa sigue en `iframe sandbox=""` con CSP sin red.

### Contrato HTTP

- `export_openapi.py --check` sale con 0 y `schema.d.ts` está regenerado en el mismo cambio.
- Todos los cambios son aditivos:
  - parámetros opcionales nuevos en `DocumentationParams`;
  - `OperationParamOut` con `type="run"`, `run_operation` y `requires`;
  - `TemplateKind` con `trace`;
  - `RunDetailOut.has_diff`, con valor por defecto;
  - `/diff` también para `documentation`, con los mismos errores (404/413 *problem details*).
- La ampliación de los enums rompería a un cliente externo que los recorra de forma exhaustiva; solo existe la SPA.
- Los códigos de error nuevos del run (`invalid_trace_map`, `invalid_previous`) están documentados en la guía y el
  CHANGELOG.

### Autorización, secretos y rutas

- **IDOR**: `previous_catalog` exige el mismo proyecto y responde igual si el id no existe o es de otro proyecto (test
  `…of_another_project_is_not_revealed`). Se comprueba al encolar (rol editor) y otra vez en el worker.
- **Mapa**: `resolve_for_run` limita a los del proyecto o globales y del tipo `trace`; usar un mapa como plantilla Word
  da 422 (test). Mientras lo use una ejecución en cola o en curso no se puede borrar (`RUN_PARAMS`).
- **Secretos y rutas**: el error del run y `run.log` no llevan ni `workspace_dir` ni `inputs/` (test). El log solo
  guarda el tipo de la excepción.
- **Path traversal**: el `catalog.json` anterior sale de `get_artifact_by_path` (artefacto registrado y `safe_path`);
  las copias van a nombres fijos de `inputs/`; el mapa se guarda con su ULID, nunca con el nombre del usuario.
- **Subida**: el límite de 1 MB se aplica al copiar en bloques (`_store`). `RecursionError` y el límite de dígitos de
  `int` de `json` se capturan como contenido no válido (422).

### Concurrencia y recursos

- Sin escrituras nuevas en SQLite fuera de las de plantillas, que ya existían.
- El worker abre sesiones cortas para resolver el mapa y la documentación anterior.
- El staging de util_bbdd evita una carpeta Markdown a medias si se cancela.
- `work/` se borra en `finally`, como antes.
- Volumen medido: 500 tablas → 511 artefactos, 2,9 s de registro y 2,8 MB.
- `mermaid.min.js` (~3 MB) por ejecución cuenta para la cuota: documentado.

### Tipado y accesibilidad

- `mypy --strict` y `tsc` sin errores.
- Los `Any` nuevos se limitan a los `json_schema_extra` (`dict[str, Any]`) y a `params` de los runs, como el código que
  ya había.
- Accesibilidad:
  - los selectores nuevos tienen etiqueta y descripción;
  - la tarjeta Markdown y el visor usan encabezados `h3`;
  - el grupo *Markdown* es un `fieldset` con `legend`;
  - el estado de error del selector de ejecuciones va en `error`.

### Tests

Cubiertos:

- generación completa con Mermaid local;
- aviso sin Mermaid;
- opciones descartadas sin Markdown;
- subida (sintaxis, raíz, UTF-8, tamaño, extensión conservada) y ejemplo base;
- mapa aplicado y mapa inválido (todos los errores, sin rutas);
- tipo incorrecto;
- documentación anterior: diff, `has_diff`, validaciones e IDOR;
- Markdown sin Graphviz;
- `public_message` y la cadena de causas;
- formulario (`requires`, selector y omisión) y visor sin evolución en Vitest;
- `stripFrontMatter`.

Faltan (no bloquean):

1. `public_message` con una clave con `/` y con una URL (H1).
2. `invalid_previous` en el worker: la anterior se purga entre el encolado y el inicio.
3. La anterior de otro schema (el mensaje «otro schema»; en SQLite, `schema` vacío frente a `main`).
4. Mapa global usado desde un proyecto.
5. Vitest de `TemplatesPanel` con un mapa: insignia *Trazabilidad*, «—» en el estilo y enlace al ejemplo.

### Validación existente (IMPLEMENT)

- Backend: ruff, mypy y `export_openapi.py --check` sin errores.
- `pytest -m "not integration"`: 769 passed, 2 skipped. Los fallos de integración son solo de SQL Server (el banco
  rechaza la conexión, también en tests que no se tocan).
- Frontend: format, lint, typecheck, 159 tests y build sin errores.
- `zensical build --strict` sin errores.

### Veredicto

**`APROBADO CON CONDICIONES`**

Condición antes de cerrar la versión:

- Corregir **H1** (anclar `_ABSOLUTE_PATH`) con su test.

Recomendado en el mismo cambio, porque es barato:

- H2: no validar los campos ocultos con `requires`.
- H3: limpiar la anterior si deja de ser comparable.
- Tests 2 y 5.

H4 y H5 quedan como riesgos residuales.

## VERSION

Cambios derivados propuestos (no aplicados: auditoría de solo lectura):

```text
fix(backend,frontend): saneado de rutas sin deformar claves ni URL y opciones ocultas del Markdown sin validar
```

Pruebas sugeridas:

- `pytest tests/unit/test_documentation_markdown_units.py tests/api/test_documentation_markdown.py`;
- `npx vitest run src/features/runs/markdown.test.tsx src/features/templates`;
- E2E manual: documentación solo Markdown de la BD de ejemplo, segunda con «Comparar con la documentación» y
  apertura del visor; subida de un mapa con una errata y lectura del error.

## Correcciones aplicadas (2026-11-06)

| # | Resultado |
|---|---|
| H1 | Corregido: `_ABSOLUTE_PATH` exige principio, espacio, comilla o paréntesis antes de la ruta; tests con ruta relativa, URL, clave con `/` y rutas absolutas POSIX/Windows entre espacios, comillas y paréntesis |
| H2 | Corregido: al desactivar el interruptor, sus opciones vuelven al valor por defecto (`resetField`); Vitest con una profundidad `9` oculta |
| H3 | Corregido: la anterior elegida se quita si deja de ser comparable; Vitest cambiando el schema |
| Test 2 | Añadido: anterior purgada con la nueva en cola → `invalid_previous`. Se mejora el mensaje: «ya no está disponible: se purgó» (antes, «debe ser una documentación terminada correctamente») |
| Test 5 | Añadido: `TemplatesPanel` con un mapa (insignia, sin selector de estilo, enlace al ejemplo, `accept` con `.toml`) |
| H4, H5 | Sin cambios: riesgos residuales |

Validación: ruff, mypy y `export_openapi --check` OK; `pytest -m "not integration"` 777 passed, 2 skipped; frontend
format, lint, typecheck, 162 tests y build OK.
