# AUDIT_PLAN — Tarjetas de salida de la documentación

Revisión del [PLAN](PLAN.md) antes de implementar. Veredicto al final.

## Funcional

- **F1** Una tarjeta por formato **pedido**, no por formato con artefactos: si Word falla y se regenera sin plantilla, la
  tarjeta debe existir y mostrar el aviso. Si un formato pedido no deja artefactos (error parcial), mostrar la tarjeta con
  «sin ficheros» en lugar de ocultarla. *Condición*.
- **F2** Word con un solo documento: el ZIP es redundante pero se mantiene por coherencia entre tarjetas (lo pidió el
  usuario). Aceptado.
- **F3** HTML: el ZIP debe incluir **todo** `outputs/html/**` (también lo que `isSiteFile` oculta); el filtro por `kind`
  lo cumple. Comprobar que el sitio abre desde `file://` (el índice usa un iframe `detailFrame`): si el navegador lo
  bloquea en local, documentarlo en la guía. *Pendiente de verificar*.
- **F4** Markdown: la descripción debe decir que el ZIP es una carpeta publicable (`zensical build` / `mkdocs build`) y
  que `mermaid.min.js` va dentro para publicarla sin Internet.
- **F5** El enlace «Artefactos» de la tarjeta Markdown actual (`markdownHint`) desaparece; el navegador general queda
  para logs y manifiesto. Revisar textos de la guía que lo citen.
- **F6** Los errores de `mermaid.min.js`, `catalog.json` y `llms-full.txt` se resuelven con B (no previsualizables →
  descarga), no con un visor JSON. Ver `llms.txt` como texto es opcional; `llms-full.txt` nunca (tamaño y diagramas).

## Técnico

- **T1** `_previewable` por extensión sin cambiar `_kind`: correcto, evita migrar la tabla `artifacts` y las
  ejecuciones antiguas se arreglan solas. La regla vive en el backend; el frontend usa `previewable`, no la repite.
- **T2** Árbol deducido de rutas: acoplado al layout de util_bbdd 5.3.0 (`docs/tables|views|routines|database`). Mitigar
  con un test de contrato que genere una documentación Markdown con SQLite y compruebe las carpetas (el wheel
  vendorizado lo permite). G51 eliminaría el acoplamiento.
- **T3** Volumen: el detalle del run (`RunDetailOut.artifacts`) ya trae miles de filas; el árbol no añade peticiones.
  Medir el tamaño de la respuesta del detalle con un schema grande; si pasa de ~1 MB, plantear paginar artefactos (fuera
  de alcance, anotar).
- **T4** Paginación por letra en lugar de virtualización: sin dependencias nuevas. Aceptado.
- **T5** `postMessage` desde un iframe con origen opaco: `event.origin` es `"null"`, así que la validación debe ser
  `event.source === iframe.contentWindow` y un esquema de mensaje estricto (`{type: 'ubw-md-nav', href: string}`,
  longitud máxima). *Condición*.
- **T6** Resolución de rutas en el padre (`markdownNav.ts`): normalizar `./`, `../`, decodificar `%xx`, rechazar rutas que
  salgan de `docs/` y buscar solo entre artefactos registrados. Nunca construir una URL de la API con texto del Markdown
  sin pasar por esa búsqueda. *Condición*.
- **T7** Nonce del script por render (`crypto.getRandomValues`), en la CSP `meta` del `srcDoc`. El HTML de `marked` se
  limpia con DOMPurify **antes** de añadir el script, con `FORBID_TAGS: ['script','iframe','object','embed','form']` y sin
  `on*`; así un `<script>` incrustado en un comentario de la BD no hereda el nonce.
- **T8** Historial: atrás/adelante del visor en estado propio y la página en `?md=`; no usar el historial del iframe.
- **T9** ZIP por formato: `format` como `Literal`; mantener `GET /archive` sin parámetro idéntico (compatibilidad).
- **T10** Avisos por formato: guardar `warnings_by_format` en el manifiesto es mejor que filtrar texto; las ejecuciones
  antiguas caen en «avisos generales» de la cabecera del run.

## Seguridad

- **S1** El iframe Markdown pasa de `sandbox=""` a `sandbox="allow-scripts"`. Riesgo aceptable solo con: origen opaco (sin
  `allow-same-origin`), CSP `default-src 'none'; script-src 'nonce-…'; img-src data:; style-src 'unsafe-inline';
  connect-src 'none'; form-action 'none'; base-uri 'none'`, DOMPurify previo y validación de mensajes (T5). Enmendar
  ADR-007. *Condición bloqueante*.
- **S2** Los SVG de Mermaid siguen generándose en la SPA con `securityLevel: 'strict'`; DOMPurify debe permitir SVG
  (`USE_PROFILES: {html: true, svg: true}`) sin `foreignObject` con scripts. Test con una etiqueta maliciosa.
- **S3** Enlaces externos (`http(s)`, los del mapa de trazabilidad): abrir con `window.open(url, '_blank', 'noopener')`
  tras validar el esquema (`http:`/`https:` solamente), o mostrarlos como texto. Recomendado: abrir con confirmación
  («sale de la aplicación»). `javascript:`, `data:` y demás, ignorados.
- **S4** ZIP por formato: mismo `safe_path` y misma comprobación de acceso que el ZIP completo; sin rutas del usuario.
- **S5** Sin cambios en la URL firmada del HTML ni en `SITE_CSP`.

## Rendimiento

- **P1** Primera página del visor: una petición (`/preview` del `index.md`) + Mermaid bajo demanda. Igual que hoy.
- **P2** Cachear el texto de cada página (`useArtifactText` ya usa `staleTime: Infinity`).
- **P3** Las páginas con muchos diagramas (índices de tablas grandes) dependen de `max_diagram_depth` del formulario;
  sin cambios.

## Documentación

- Guía `docs/guides/documentacion.md`: capturas/descripciones de las cuatro tarjetas, ZIP por formato, visor Markdown y
  sus límites (sin buscador de texto completo; el sitio completo, con el ZIP).
- `CHANGELOG.md` (1.12.0), `ROADMAP.md` (nueva entrada «Después de la 1.0: salida de la documentación por formato»),
  ADR-007 enmendado, `UTIL_BBDD_GAPS.md` con G50/G51 si se aceptan.

## Decisiones del usuario (2026-11-06)

1. Visor Markdown: **M2**.
2. Pasos 1 y 2 en **una sola versión** (1.12.0).
3. **G50 y G51 registrados** en `UTIL_BBDD_GAPS.md` (abiertos).
4. Enlaces externos: **se abren con confirmación**.

Consecuencias revisadas:

- **D2** Una versión con más superficie: el paso 1 se implementa y se valida (tests verdes, `zensical build --strict`)
  antes de empezar M2, en commits separados, para poder publicar sin M2 si la condición S1 no se cumple a tiempo.
- **D4 / S3** Modal de confirmación con la URL completa visible (no solo el texto del enlace, que viene de la BD o del
  mapa y podría no coincidir); `new URL()` con `protocol` ∈ {`http:`, `https:`}; `window.open(…, 'noopener,noreferrer')`.
  Test: `javascript:`, `data:`, `file:` y rutas protocol-relative (`//host`) no abren nada.
- **G51** Mientras siga abierto, el test de contrato de T2 es obligatorio (no opcional).

## Veredicto

**GO_CONDICIONAL** — condiciones: F1, T5, T6, T7, S1 (bloqueante), S2, S3 con el test de D4 y el test de contrato
de T2. Verificar antes de implementar: mensaje real de los tres errores (§ 1.1 del PLAN) y apertura del ZIP HTML desde
`file://` (F3).

**Aprobado por el usuario (2026-11-06)**: PLAN y AUDIT_PLAN aceptados; IMPLEMENT pendiente de lanzar.
