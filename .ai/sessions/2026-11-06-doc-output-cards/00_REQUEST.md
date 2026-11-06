# Petición — 2026-11-06 · Tarjetas de salida de la documentación

Fase pedida: **PLAN y AUDIT_PLAN únicamente** (no se implementa nada).

Identificar lo que falta, el roadmap y el gap con util_bbdd. En el detalle de una ejecución `documentation`:

- Reestructurar la pantalla: tarjetas independientes por tipo de exportación (Word, Excel, HTML y Markdown), cada
  una con su información y descripción.
- **Word**: los documentos y descarga en ZIP, sin vista previa.
- **Excel**: el documento y descarga en ZIP, sin vista previa.
- **HTML**: como ahora en la tarjeta «Documentación» (visualizar y navegar) y descarga en ZIP.
- **Markdown**: solo artefactos Markdown. Son muchos ficheros y un scroll grande: proponer alternativas. Permitir
  visualizarlos y navegar (ahora, pinchar en un enlace da error): analizar el impacto. En la vista previa dan error
  `mermaid.min.js`, `catalog.json` y `llms-full.txt`: proponer una mejora.

Analizar también util_bbdd_web (no solo util_bbdd).
