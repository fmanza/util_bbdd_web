# ADR-015 — Idioma de los mensajes de la API

- **Estado**: Aceptado
- **Fecha**: 2026-11-26
- **Completa**: [ADR-014](ADR-014-roles-y-permisos.md) (idioma de la interfaz por usuario, 2.0.0)

## Contexto

La 2.0.0 trae la interfaz en español o inglés, pero el backend solo hablaba español: con la interfaz en inglés, el
título de un error se traducía en el frontend por su estado HTTP y debajo salía el detalle en español. Lo mismo pasaba
con los errores por campo de los formularios y con el motivo del fallo de una ejecución. Los mensajes de validación de
Pydantic, al revés, salían en inglés también con la interfaz en español.

Había unos 200 `raise` con texto en 51 ficheros, 78 títulos de clase, 46 errores por campo y unos 90 fallos de jobs.

Se valoraron tres opciones: catálogo en el backend (el servidor responde ya traducido), código y parámetros (el
frontend compone el texto) y dejarlo como estaba. La segunda cambia el contrato en cada error y obliga a cada cliente a
conocer todos los códigos; la tercera deja la mezcla de idiomas.

## Decisión

1. **Catálogo en el backend** (`backend/app/i18n/`): los errores no llevan texto, sino un `Msg` (clave y parámetros).
   El texto se compone al responder, con un catálogo por área en `app/i18n/catalog/` (`ES` y `EN`).
2. **Idioma de la petición**: `Accept-Language` (el frontend envía siempre el idioma activo, también antes de iniciar
   sesión), negociado por `q` entre `es` y `en`; sin cabecera o sin idioma soportado, `es`. Las respuestas de error
   llevan `Content-Language` y `Vary: Accept-Language`. No se lee `Me.language`: evita una consulta por error y
   coincide con lo que ve el usuario.
3. **`code` estable** en todo *problem details* (extensión de RFC 9457) y en cada entrada de `errors`: la clave del
   detalle (`runs.preview_expired`) o, sin detalle, el código de la clase, derivado de su nombre
   (`ConnectionNotFoundError` → `connection_not_found`). Su título es la clave `title.<code>`. Un cliente puede
   sustituir un texto concreto por el suyo sin migrar el resto. Las claves no se renombran a la ligera.
4. **Validación de Pydantic** traducida por `type` (`validation.missing`, `validation.string_too_long`…, con los
   valores de `ctx`); un `type` sin entrada conserva el texto de Pydantic. Los validadores propios lanzan
   `PydanticCustomError` con una clave del catálogo como `type`.
5. **Fallos de las ejecuciones** (`JobError(code, Msg)`): se guardan como clave y parámetros en `runs.error_detail`
   (JSON, migración 0016) y la API compone `error_message` **en el idioma de quien consulta**: cada miembro del
   proyecto lo lee en el suyo. `runs.error_message` y `run.json` guardan además el texto en español; las ejecuciones
   anteriores solo tienen ese texto.
6. **Excepciones internas** (capa de integración): las que llevan un mensaje para el usuario heredan de
   `LocalizedError` y exponen `.msg`; `str(exc)` es la clave, así los logs no dependen del idioma.
7. **Vigilancia** (`tests/unit/test_i18n.py`): mismas claves y marcadores en los dos idiomas, ninguna clave repetida
   entre módulos, todo `Msg("…")` literal existe, toda clase de `AppError` tiene título y ningún error que llega al
   usuario se construye con un texto. `mypy --strict` exige `Msg` en `AppError`, `JobError` y `finalize_run`.

## Consecuencias

- Con la interfaz en inglés, títulos, detalles, errores por campo y fallos de ejecución llegan en inglés.
- **Siguen en español**: el progreso de las ejecuciones y su log de eventos, los avisos de la documentación, la
  auditoría, los logs del servidor y los textos que vienen de excepciones de util_bbdd (se interpolan tal cual; util_bbdd
  traduce sus informes con `locale`, no sus excepciones: [G58](../plan/UTIL_BBDD_GAPS.md)).
- El flujo SSE de una ejecución (`EventSource` no deja fijar cabeceras) usa el idioma del navegador; al terminar, la
  SPA recarga el detalle con su idioma.
- Un mensaje nuevo exige su entrada en `ES` y `EN`; la prueba de paridad falla si falta.
- El contrato solo se amplía (`code`, `errors[].code`, cabeceras): un cliente anterior sigue funcionando.
