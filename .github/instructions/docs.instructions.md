---
applyTo: "docs/**/*.md,README.md,CHANGELOG.md"
---
# Documentación — reglas

- Español. Nombres de fichero en minúsculas con guiones bajos, salvo ADRs (`ADR-NNN-nombre.md`).
- Guías en `docs/guides/`, plan en `docs/plan/`, decisiones en `docs/adr/`, documentación de usuario en `docs/user/`.
- Solo se documenta lo implementado; lo previsto se marca como «Fase N (pendiente)».
- No inventar endpoints, pantallas ni opciones: verificar contra el código y `openapi/openapi.json`.
- Diagramas en Mermaid cuando aporten claridad.
- Markdown: línea en blanco antes de listas, tablas y bloques de código; enlaces relativos que existan.
- Sin credenciales reales en ejemplos; usar `<usuario>`, `<contraseña>`.
- Una decisión de arquitectura nueva o revertida → ADR nuevo (no se reescriben ADRs aceptados; se marcan como
  «Sustituido por ADR-NNN»).
