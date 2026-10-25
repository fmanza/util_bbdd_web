# TRACEABILITY

## Session metadata
- id: 2026-10-25-feat-document-templates
- fecha: 2026-10-25
- rama: develop (sin commit; cambios en el árbol de trabajo)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
«En Word y Excel falta la opción de seleccionar una plantilla, se necesita una gestión de plantillas que permita
seleccionar una en las opciones de documentación, si no se selecciona se deja el funcionamiento actual. Recomienda
opciones.» Tras la recomendación: «Meter Excel desde el principio, PLAN y AUDIT_PLAN». Decisiones del AUDIT_PLAN:
límites de Excel aceptados, estilo de tabla por plantilla (S1), **formato por defecto con aviso** si la plantilla no
se aplica (en lugar de fallar), ADR-011 + G40 + G41. Después: «IMPLEMENT» y «si» (AUDIT_CODE y VERSION).

## Context supplied
- util_bbdd 4.0.0 (wheel instalado): `imprimir["plantilla_word"]` y `table_style` en `PrintConfigManager`,
  `WordGenerator._initialize_document`/`_configure_document_orientation`/`_resolve_table_style`,
  `ExcelGenerator` (`SafeWorkbook()`, colores RGB fijos, `_normalize_table_style`), `DocumentationOrchestrator`
  (un fallo de renderer aborta los formatos que faltan).
- Patrones de la web: `domain/uploads` (subidas multipart, ADR-010), `admin_queries`, `jobs/operations/bulk.py`
  (sesión propia en el job), `runner._manifest`, `LaunchRunModal` genérico.

## AI output summary
- Recomendación previa: Word nativo en util_bbdd; Excel no soportado (E1 gap / E2 retoque). Verificado con
  python-docx que una plantilla sin `Heading 1` da `KeyError` y que un `.dotx` no se abre.
- PLAN/AUDIT_PLAN: hallazgo de que cambiar solo el tema del Excel no basta (rellenos RGB fijos); `GO_CONDICIONAL` →
  `GO` con las decisiones del usuario.
- Backend: modelo `DocumentTemplate` + migración `0009`; `domain/templates/` (`files.py`: comprobación de contenido,
  conversión `.dotx`/`.xltx`, plantillas base; `service.py`: CRUD, en uso, `check_run_templates`);
  `integrations/util_bbdd/excel_template.py` (retoque) y `documentation.py` (`DocumentTemplates`,
  `word_template_failed`, reintento sin plantilla, `WORD_REQUIRED_STYLES`); `DocumentationParams.word_template`/
  `excel_template` (tipo `template`); job: copia a `inputs/` con SHA-256 y `inputs/templates.json`; `runner`:
  `templates`/`warnings` en `run.json`; `RunDetailOut.warnings`; rate limit de subidas ampliado; auditoría
  `template.*`; `UBW_TEMPLATE_MAX_MB`, `UBW_TEMPLATES_PER_SCOPE`; `python-docx` y `openpyxl` declaradas.
- Contrato: `openapi.json` exportado (8 rutas nuevas, `OperationParamOut`, `RunDetailOut`) y `schema.d.ts` regenerado.
- Frontend: `features/templates/` (`useTemplates`, `TemplatesPanel`), `admin/TemplatesPage` + ruta y menú, pestaña
  *Plantillas* (montada solo al abrirla: montada siempre rompía el test de *Carga*), selectores en `LaunchRunModal`
  (solo con su formato marcado), aviso en `RunDetailPage`, i18n.
- Tests: `tests/unit/test_templates_units.py` (22), `tests/api/test_templates.py` (17, con util_bbdd real sobre
  SQLite: Word con plantilla, Excel sin colores fijos, fallback con aviso), ajustes en `test_backup` (revisión 0009),
  `test_documentation_units` y `test_hardening` (rate limit); Vitest `templates.test.tsx` (8).
- AUDIT_CODE: `APROBADO CON CONDICIONES`; A1 (selector de estilo sin opción cuando `table_style` es nulo) corregido
  con su test; A2–A6 bajos/informativos, aceptados.
- Documentación: ADR-011, G40 y G41, guía de documentación (sección «Plantillas Word y Excel»), guía de usuario,
  proyectos y ejecuciones, arquitectura, índice y `zensical.toml`; CHANGELOG (`Added`, `Security`).
- Validación ejecutada: ruff format/check, mypy, `export_openapi.py --check`, pytest (604 passed, 87 skipped),
  format:check, lint, typecheck, Vitest (113 passed), build, `zensical build --strict`.
- Tras el cierre («Hazlo»): E2E `frontend/e2e/templates.spec.ts` (plantilla Excel global desde *Administración*,
  Word del proyecto, documentación con las dos, descarga del Word y `run.json` con `applied: true`, limpieza).
  `docker compose -p ubw_e2e up -d --build` (imagen `util_bbdd_web:templates-e2e`, puerto 8091, admin y BD de
  fixtures propios): build correcto y `/api/health` 200; suite E2E completa con `--repeat-each=2 --workers=2`:
  37 passed, 7 skipped (bench sin contraseña y repeticiones de specs que escriben en destinos compartidos). Stack,
  volúmenes e imagen eliminados; el despliegue local `util_bbdd_web` no se tocó.

- Tras el cierre («Adelante»), corrección de A2–A5 de AUDIT_CODE:
  - A2: `files.py` reconstruye cada campo (`_FieldCodes`: `fldChar` begin/separate/end, `instrText` en trozos,
    anidamiento) y solo mira su tipo; rechaza también el tipo calculado por un campo anidado y añade `INCLUDE`.
  - A3: índice único `uq_document_templates_scope_kind_name` (`coalesce(project_id, 0)`, `kind`, `lower(name)`) en
    la migración 0009 (sin publicar) y en el modelo; `IntegrityError` de ese índice → 409 al crear y al renombrar;
    el máximo se recuenta tras el `flush` (`_check_limit(pending=0)`).
  - A4: si falla el guardado de la fila, `rollback` y se borra el fichero.
  - A5: `isinstance(..., PackageNotFoundError)`.
  - Tests: 10 unitarios (campos y `PackageNotFoundError`) y 3 de API (duplicados frenados por la BD también en las
    globales y al renombrar, recuento tras el INSERT, fichero borrado si falla la fila). Validación: ruff, mypy,
    `export_openapi.py --check`, pytest 617 passed (87 skipped). ADR-011 actualizado.

- Probando en local: tras elegir un estilo de tabla («Normal Table») no se podía volver a «Por defecto». La opción solo
  salía con `table_style` nulo y el PATCH trataba `null` como «no cambiar». Ahora `table_style: null` explícito
  (`TemplateUpdate.default_table_style`, por `model_fields_set`) quita el estilo y la opción «Por defecto» sale
  siempre. Tests: API (Word de proyecto y Excel global, omitir no cambia, `""` da 422) y Vitest. Validación: ruff,
  mypy, contrato exportado y cliente regenerado, pytest 618 passed (87 skipped), Vitest 114, build.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT backend | `backend/app/domain/templates/`, `backend/app/api/v1/templates.py`, `backend/app/integrations/util_bbdd/excel_template.py`, `backend/alembic/versions/0009_document_templates.py` y modificados | completado |
| Contrato | `openapi/openapi.json`, `frontend/src/api/schema.d.ts` | regenerado |
| IMPLEMENT frontend | `frontend/src/features/templates/`, `frontend/src/features/admin/TemplatesPage.tsx` y modificados | completado |
| Tests | `backend/tests/unit/test_templates_units.py`, `backend/tests/api/test_templates.py`, `frontend/src/features/templates/templates.test.tsx`, `frontend/e2e/templates.spec.ts` | en verde |
| Docs | `docs/adr/ADR-011-plantillas-de-documento.md`, `docs/plan/UTIL_BBDD_GAPS.md`, `docs/guides/documentacion.md`, `CHANGELOG.md` | completado |
| Logs | `build/logs/pytest_templates_*.txt`, `build/logs/frontend_*.txt`, `build/logs/docs_build.txt`, `build/logs/docker_e2e_build.txt`, `build/logs/e2e_*.txt` | generados |

## Directrices para Futuras IAs
- **[plantillas]**: util_bbdd 4.0.0 solo admite plantilla Word (`imprimir["plantilla_word"]`); el Excel se retoca en
  `integrations/util_bbdd/excel_template.py` cambiando los RGB de `FIXED_COLORS` por colores del tema. Al actualizar
  util_bbdd, `test_documentation_applies_word_and_excel_templates` falla si `ExcelGenerator` usa colores nuevos:
  añádelos a `FIXED_COLORS` (o retira el retoque si util_bbdd resuelve G40).
- **[plantillas]**: `table_style` de util_bbdd es un único valor para Word y Excel; la web pasa a util_bbdd solo el de
  Word y aplica el de Excel en el retoque. Un estilo de Word que llega al Excel cae en `TableStyleMedium2` con aviso
  en el log de util_bbdd (inofensivo).
- **[plantillas]**: un fallo de renderer en util_bbdd aborta los formatos que faltaban, así que el fallback de Word
  regenera **todo** sin plantilla (una vez y solo si `word_template_failed`); nunca reintentar por Graphviz ni por la
  conexión.
- **[plantillas]**: python-docx no abre `.dotx` y openpyxl exige la extensión del fichero (`.xlsx`): el temporal de
  subida se llama `.tmp-<id>.<docx|xlsx>`; los `.dotx`/`.xltx` se convierten cambiando el tipo en
  `[Content_Types].xml` (`untemplate`).
- **[plantillas]**: Word solo guarda los estilos usados; los cinco de `WORD_REQUIRED_STYLES` se exigen al subir
  (error con `missing_styles`) y la plantilla base (`base_template`) los trae todos.
- **[runs]**: `run.json` de toda operación lleva `templates` y `warnings` (vacíos salvo documentación con plantilla);
  `RunDetailOut.warnings` se lee de `run.manifest`, que solo existe al cerrar el run. `inputs/` no son artefactos.
- **[frontend]**: Mantine `Tabs` monta todos los paneles: un panel con `input[type=file]` siempre montado rompe los
  tests que usan `document.querySelector('input[type="file"]')`; la pestaña *Plantillas* se monta solo activa.
- **[tests]**: en jsdom, `request.formData()`/`request.text()` de un multipart con `File` no termina; comprobar solo
  `Content-Type` en Vitest y el contenido en los tests de API.
- **[e2e]**: `page.request` no envía la cookie `__Host-` (`Secure`) a `http://127.0.0.1`: en los specs, bajar ficheros
  con el enlace de la UI (`waitForEvent('download')`) y leer la API con `fetch` dentro de `page.evaluate`.
- **[plantillas]**: la comprobación de campos de Word mira el **tipo** (primera palabra del código reconstruido por
  `_FieldCodes`), no palabras sueltas: no volver a buscar `LINK`/`IMPORT` en todo el código (rechazaba
  `MERGEFIELD Link`).
- **[plantillas]**: el nombre único lo garantiza el índice `uq_document_templates_scope_kind_name`, no solo
  `_check_name`; SQLite trata los `NULL` como distintos, de ahí `coalesce(project_id, 0)`.
- **[e2e]**: en Git Bash, `docker compose exec … ls /data/files` necesita `MSYS_NO_PATHCONV=1` (si no, la ruta se
  convierte a `C:/Program Files/Git/...`).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Rendimiento del retoque Excel en schemas muy grandes sin medir.
- G40 y G41 abiertos en util_bbdd.
