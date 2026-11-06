# Documentación y grafos de relaciones

Guía de uso de las operaciones de documentación y grafos (desde la 0.6.0, Fase 5; Markdown desde la 1.11.0). Se lanzan desde la pestaña *Ejecuciones* de un proyecto
(rol editor) sobre una conexión asociada al proyecto, y se ejecutan en el worker como cualquier ejecución.

## Documentación de la base de datos

Documenta un schema con `DatabaseDocumentation` de util_bbdd.

| Sección del formulario | Opciones |
|---|---|
| (general) | **Conexión** (alias del proyecto) y **Schema**: vacío = el de la conexión |
| Formatos | **Word** (.docx), **Excel** (.xlsx), **Sitio HTML** y **Markdown** (desde la 1.11.0; desmarcado por defecto); al menos uno |
| Tablas | Tablas, columnas, claves (PK, FK, únicas), índices y DDL |
| Vistas | Vistas (columnas) y su DDL |
| Rutinas | Procedimientos y funciones |
| Información adicional | Datos de la BD (versión), almacenamiento, condiciones del motor, charset y collation |
| Diagramas | Diagramas de relaciones: en Word y HTML con Graphviz y en Markdown con Mermaid; profundidad (1–3), dirección y columnas de cada tabla (ver abajo) |
| Presentación | Tablas por documento Word (si hay más, se generan varios) y elementos por página del índice HTML |
| Plantillas | **Plantilla Word** y **Plantilla Excel** del proyecto o globales; vacío = formato por defecto (ver abajo) |
| Markdown | Solo con **Markdown** marcado: título del sitio, profundidad máxima de los diagramas, mapa de trazabilidad y documentación anterior con la que comparar ([Documentación Markdown](#documentación-markdown)) |

**Columnas en el diagrama** (independiente de la opción *Columnas* de *Tablas*, que controla la tabla de columnas del
documento):

| Opción | Qué muestra cada tabla del diagrama |
|---|---|
| Primero las de relación, luego el resto (por defecto) | Las columnas de PK/FK que dibuja el diagrama y, hasta el máximo, las demás |
| Solo columnas de relación | Solo las de PK/FK que dibuja el diagrama; una tabla sin FK sale «Sin columnas visibles» |
| Todas las columnas | Las primeras columnas de la tabla, hasta el máximo |
| Sin columnas | Solo el nombre de la tabla |

Con **Columnas máximas por tabla** (1–50, 8 por defecto) se limita cada tabla; las que no caben se resumen en
«… N columna(s) más». **Mostrar tipos de columna** añade el tipo de cada una.

Una tabla **sin relaciones** se dibuja sola, en el Word y en el sitio HTML (grupo «Sin relaciones»).

**Schema por motor**: en PostgreSQL, SQL Server y HSQLDB es el schema; en MySQL y MariaDB, la base de datos; en
SQLite no aplica. En **Oracle**, el owner: vacío usa el usuario de la conexión, y se puede poner otro owner si el
usuario tiene permiso de lectura sobre sus objetos (desde util_bbdd 4.1.0).

### Plantillas Word y Excel

Sin plantilla, Word y Excel salen con el formato de util_bbdd. Con una **plantilla** se aplica la imagen corporativa
([ADR-011](../adr/ADR-011-plantillas-de-documento.md)):

| | Word (`.docx`, `.dotx`) | Excel (`.xlsx`, `.xltx`) |
|---|---|---|
| Qué se toma | Su contenido (portada), encabezado, pie, estilos y orientación | Tema (colores y fuentes), encabezado y pie y configuración de página de la primera hoja |
| Estilo de tabla | Uno de los estilos de tabla de la plantilla | Uno predefinido de Excel (`TableStyleLight1`…`TableStyleDark11`) |
| Requisitos | Los estilos *Título*, *Título 1* a *Título 3* y *Sin espaciado* (`Title`, `Heading 1`-`3`, `No Spacing`) | Un tema sin imágenes |
| No se admite | Macros, objetos incrustados, plantilla adjunta o imágenes enlazadas, campos DDE/INCLUDE/LINK | Macros, vínculos a otros libros; portada e imágenes en el encabezado no se copian |

- **Dónde se gestionan**: la pestaña **Plantillas** del proyecto (los editores suben, renombran, eligen el estilo de
  tabla y borran; todos los miembros ven y descargan) y *Administración → Plantillas* para las **globales**, que salen
  en todos los proyectos. Máximo 10 MB por plantilla (`UBW_TEMPLATE_MAX_MB`) y 20 por proyecto o en el catálogo
  global (`UBW_TEMPLATES_PER_SCOPE`).
- **Plantillas base**: desde la pestaña se descargan un Word con todos los estilos necesarios (en horizontal) y un
  Excel de ejemplo. Word solo guarda los estilos que se han usado: si al subir una plantilla faltan estilos, el
  mensaje dice cuáles; úsalos una vez en el documento o parte de la plantilla base.
- **Al lanzar**: «Plantilla Word» y «Plantilla Excel» aparecen si ese formato está marcado.
- **Con plantilla Word se respeta su orientación** (sin plantilla se usa horizontal): para tablas anchas, usa una
  plantilla en horizontal. Su contenido se repite al principio de cada documento si hay más tablas que «Tablas por
  documento Word».
- **Si la plantilla no se puede aplicar** (se borró del disco, le falta un estilo, el Excel no es un libro válido), la
  documentación sale con el **formato por defecto** y la ejecución termina con un **aviso** en su detalle. La
  ejecución guarda una copia de cada plantilla, y `run.json` registra cuál se usó y si se aplicó; borrar una plantilla
  no afecta a las documentaciones ya generadas (no se puede borrar mientras la use una en cola o en curso).
- El Excel no tiene portada ni imágenes en el encabezado, y solo admite estilos de tabla predefinidos (GAPS G40).

Al terminar, el detalle de la ejecución muestra la tarjeta **Documentación**:

- Botones de descarga del Word y del Excel.
- El **sitio HTML** navegable dentro de la página, y **Abrir en pestaña nueva**. El sitio se ve con sus scripts, pero
  aislado: no puede leer tu sesión ni llamar a la API ([ADR-007](../adr/ADR-007-sitio-html-aislado.md)). Su enlace es
  temporal (caduca con la inactividad de la sesión, 60 minutos por defecto): si caduca, recarga el detalle.
- **Descargar ZIP** baja todo, incluido el sitio completo para abrirlo sin servidor.

### Documentación Markdown

Desde la 1.11.0 (util_bbdd 5.3.0). Genera una carpeta pensada para versionar con git, publicar como sitio y dar
contexto a una IA:

- una página `.md` por tabla, vista y rutina (`docs/tables/…`, `docs/views/…`, `docs/routines/…`), con índices por
  letra y una portada (`docs/index.md`);
- diagramas ER de **Mermaid** en cada tabla: **no necesitan Graphviz** (una documentación solo Markdown funciona en
  un servidor sin `dot`). *Mostrar tipos de columna* y *Relaciones en ángulo recto* no aplican: Mermaid siempre
  muestra los tipos;
- `docs/catalog.json` (catálogo de los objetos), `docs/llms.txt` y `docs/llms-full.txt` (para IA), `mkdocs.yml`
  (listo para `zensical build` o `mkdocs build`) y `manifest.json`.

| Opción | Efecto |
|---|---|
| Título del sitio | `site_name` del `mkdocs.yml`; vacío = «Documentación de <base de datos>» |
| Profundidad máxima de los diagramas | 1–3 (2 por defecto). Se usa el menor entre este valor y la *Profundidad* de *Diagramas*; si recorta, la página lo avisa |
| Mapa de trazabilidad | Un mapa del proyecto o global (ver abajo); vacío = sin trazabilidad |
| Comparar con la documentación | Una documentación anterior **del mismo proyecto, conexión y schema, con Markdown**: añade `docs/changes.md` y `docs/changes.json` con los cambios de esquema |

**Mermaid sin Internet**: el `mkdocs.yml` carga `docs/assets/javascripts/mermaid.min.js`, y el **ZIP** lleva el
`mermaid.min.js` de la web (`UBW_MERMAID_JS`, incluido en la imagen) en esa ruta, así el sitio publicado dibuja los
diagramas sin salir a Internet. Desde la 1.13.0 (util_bbdd 5.4.0, G50) ese fichero **no se guarda en cada
ejecución**: se añade al ZIP al descargarlo (antes eran unos 5,5 MB por ejecución en la cuota; las ejecuciones
anteriores conservan su copia). Sin `UBW_MERMAID_JS` en el servidor: al generar, el `mkdocs.yml` carga Mermaid de
unpkg y la ejecución termina con un aviso; al descargar, el ZIP sale sin el fichero, la respuesta lo avisa
(`X-UBW-Warning`) y el sitio publicado cargará Mermaid de Internet.

**Dónde verla**: en su tarjeta del detalle, con el visor Markdown (ver
[Resultados](#resultados-una-tarjeta-por-formato)), o completa en su ZIP. Para el sitio con buscador de texto
completo, publica el ZIP con Zensical o MkDocs fuera de la web.

**Mapa de trazabilidad**: un `.toml` (recomendado: admite comentarios) o `.json` de hasta 1 MB que enlaza tablas,
vistas, rutinas y columnas con código, documentos funcionales y técnicos y requisitos. Se gestiona como una plantilla
más (pestaña **Plantillas** del proyecto o *Administración → Plantillas*), con su **ejemplo** descargable. Al subirlo
se comprueba la sintaxis; los campos los comprueba util_bbdd al generar: **si el mapa no es válido, la ejecución
falla** (`invalid_trace_map`) con **todos** los errores en el mensaje, para corregirlos de una vez. Con mapa, la
documentación añade `docs/traceability.md` (cobertura, matriz y entradas del mapa que no casan con ningún objeto).

```toml
[tables."PEDIDOS"]
code = ["src/ventas/pedidos.py#Pedido"]
requirements = ["REQ-012"]

[tables."PEDIDOS".columns."CLIENTE_ID"]
code = ["src/ventas/pedidos.py#Pedido.cliente_id"]
```

**Cambios respecto de la anterior**: la documentación nueva lleva un apartado **Cambios respecto de la documentación
anterior** en su detalle con el mismo visor que la comparación de esquemas (sin *Comparar con otra ejecución*). La
ejecución copia el `catalog.json` de la anterior: purgar después la anterior no la afecta.

### Resultados: una tarjeta por formato

Desde la 1.12.0, el detalle de una documentación muestra **una tarjeta por formato pedido** (Word, Excel, HTML y
Markdown), cada una con su descripción, número de ficheros y tamaño, la marca **Con plantilla** si se aplicó la
elegida, **sus avisos** (plantilla no disponible, Mermaid ausente…) y **Descargar ZIP** solo con ese formato
(`GET /api/v1/runs/{id}/archive?format=word|excel|html|markdown`; sin `format`, el ZIP completo de siempre). Los avisos
que no son de un formato siguen en la cabecera. Si un formato pedido no llegó a generarse, su tarjeta lo dice.

| Tarjeta | Contenido | Vista previa |
|---|---|---|
| Word | Un botón por documento (varios si se pidió un número de tablas por documento) | No: descárgalo |
| Excel | El libro | No: descárgalo |
| HTML | El sitio navegable en la página y **Abrir en pestaña nueva** | Sí (ADR-007) |
| Markdown | Visor con árbol, buscador y navegación entre páginas; **Ficheros auxiliares** (`catalog.json`, `llms.txt`, `llms-full.txt`, `mkdocs.yml`, `manifest.json`) para descargar | Solo las páginas `.md` |

**ZIP HTML sin conexión**: descomprímelo y abre `outputs/html/documentacion/index.html`; el índice, el buscador, el
resaltado SQL y la navegación funcionan desde el disco (comprobado en Chromium).

**ZIP Markdown**: la carpeta `outputs/markdown/documentacion/` es publicable tal cual (`zensical build` o
`mkdocs build`) e incluye `mermaid.min.js` (el del servidor, añadido al descargar) para dibujar los diagramas sin
Internet.

**Visor Markdown**:

- **Árbol** a la izquierda: *Sección* (Portada, Tablas, Vistas, Rutinas, Base de datos, Trazabilidad, Cambios), el
  índice de la sección y, en las secciones de más de 40 objetos, **letra inicial**. **Buscar página** filtra por
  nombre y por ruta en todas las secciones (muestra hasta 100 resultados).
- **Nombres reales**: desde la 1.13.0 (util_bbdd 5.4.0, G51) el árbol sale del índice de páginas de `manifest.json`
  y muestra el nombre del objeto tal como está en la base de datos (`ACM_AGENDA`) y los títulos de los índices. En
  las documentaciones anteriores se deduce de las carpetas y muestra el nombre del fichero (`acm-agenda`).
- **Enlaces**: los enlaces entre páginas y a columnas (`#col-…`) navegan dentro del visor; **Página anterior** y
  **Página siguiente** recorren el historial del visor. La página abierta queda en la dirección
  (`?md=tables/pedidos.md`): se puede compartir con otro miembro del proyecto.
- Un enlace a un fichero que no es una página (`catalog.json`…) ofrece su descarga; uno a una página que no existe,
  un aviso. Un enlace **externo** (`http`/`https`, p. ej. del mapa de trazabilidad) pide confirmación mostrando la
  dirección completa y se abre en otra pestaña; cualquier otro esquema (`javascript:`, `data:`, `file:`…) se ignora.
- Seguridad: cada página se muestra en un iframe con origen opaco, sin red y con el HTML limpiado (ADR-007, enmienda
  de la 1.12.0).

**Artefactos** ya no lista los ficheros de la carpeta Markdown (son miles en un schema grande): los cuenta y remite a
su tarjeta. `mermaid.min.js`, `catalog.json`, `llms-full.txt` y el resto de ficheros que no son páginas no tienen vista
previa (antes daban un error genérico al abrirlos): se descargan.

## Grafo de relaciones

Dibuja con Graphviz las claves foráneas alrededor de una tabla (`GraphvizRelationshipGraphExt`).

| Parámetro | Efecto |
|---|---|
| Tabla central | La tabla del grafo; **vacío = un grafo por cada tabla con relaciones** |
| Profundidad | Niveles de relación (1–5) |
| Dirección | Ambas, salientes (tablas a las que referencia) o entrantes (tablas que la referencian) |
| Columnas | Solo las de relación (por defecto), primero las de relación y luego el resto, ninguna o todas; con un máximo por tabla |
| Mostrar tipos | Tipo de cada columna |
| Tablas por imagen | Si hay más tablas relacionadas, el grafo se reparte en varias imágenes |
| Formato | SVG o PNG |

El detalle muestra una **galería** con las primeras 12 imágenes; el resto están en *Artefactos*.

## Errores frecuentes

| Código | Causa | Qué hacer |
|---|---|---|
| `invalid_params` | Schema de Oracle distinto del usuario, o tabla que no existe en el schema | Corrige el schema o la tabla |
| `no_relations` | El grafo no tiene relaciones que dibujar (p. ej. ninguna tabla con FK) | Elige otra tabla o schema |
| `graphviz_missing` | El servidor no tiene Graphviz | La imagen oficial lo incluye; en otra instalación, instala `graphviz` |
| `graphviz_failed` | Graphviz no pudo dibujar los diagramas. Desde util_bbdd 4.1.0 un diagrama que falla deja un aviso en su lugar y el documento sigue, así que es raro (GAPS G39) | Desmarca «Relaciones en ángulo recto», reduce la profundidad o desactiva los diagramas |
| `connection_failed` | La BD no responde o rechaza las credenciales | Prueba la conexión desde su ficha |
| `invalid_trace_map` | El mapa de trazabilidad tiene campos o tipos que util_bbdd no admite (el mensaje los lista todos), o ya no está | Corrige el mapa y súbelo de nuevo, o lanza sin mapa |
| `invalid_previous` | La documentación anterior se purgó antes de empezar la ejecución, o es de otro motor | Elige otra o lanza sin comparar |

Documentar un schema grande lleva tiempo (cada diagrama de Word o HTML es un proceso `dot`); el límite es el de cualquier
ejecución (`UBW_JOB_TIMEOUT_SECONDS`, 1 hora por defecto).
