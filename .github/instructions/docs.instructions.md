---
applyTo: "docs/**/*.md,README.md,CHANGELOG.md"
---
# Documentación — reglas

- Español. Nombres de fichero en minúsculas con guiones bajos, salvo ADRs (`ADR-NNN-nombre.md`).
- Guías (de uso y de operación) en `docs/guides/`, plan en `docs/plan/`, decisiones en `docs/adr/`, seguridad en
  `docs/security/`; índice en `docs/README.md` (portada del sitio). Una página nueva se añade al `nav` de
  `zensical.toml`.
- Solo se documenta lo implementado; lo previsto se marca como «Fase N (pendiente)».
- No inventar endpoints, pantallas ni opciones: verificar contra el código y `openapi/openapi.json`.
- Diagramas en Mermaid cuando aporten claridad.
- Markdown compatible con GitHub **y** con Zensical (Python-Markdown, más estricto):
    - línea en blanco antes de listas, tablas y bloques de código, también dentro de un elemento de lista;
    - lo anidado en una lista (subviñetas, párrafos, bloques de código) va indentado **4 espacios**;
    - si un elemento de lista tiene varios párrafos o un bloque de código, línea en blanco entre elementos;
    - enlaces relativos solo dentro de `docs/`; a ficheros de fuera (README, CHANGELOG, `.github/`), URL absoluta
      `https://github.com/fmanza/util_bbdd_web/blob/develop/…`.
- Antes de cerrar un cambio de documentación: `zensical build --strict` (comando en SHARED) sin avisos.
- Sin credenciales reales en ejemplos; usar `<usuario>`, `<contraseña>`.
- Una decisión de arquitectura nueva o revertida → ADR nuevo (no se reescriben ADRs aceptados; se marcan como
  «Sustituido por ADR-NNN»).
