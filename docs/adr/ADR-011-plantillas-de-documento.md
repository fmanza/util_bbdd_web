# ADR-011 — Plantillas de documento (Word y Excel)

- **Estado**: Aceptado
- **Fecha**: 2026-10-25

## Contexto

La documentación (Fase 5) genera Word y Excel con el formato fijo de util_bbdd. Los equipos quieren su portada, su
encabezado y pie y sus colores corporativos, sin cambiar lo que pasa cuando no eligen nada. Con util_bbdd 4.0.0:

- **Word** admite `imprimir["plantilla_word"]`: carga el `.docx` con python-docx, conserva su contenido y añade la
  documentación detrás; con plantilla respeta su orientación (sin ella fuerza horizontal). Usa por nombre los
  estilos `Title`, `Heading 1` a `Heading 3` y `No Spacing`: si falta uno, python-docx lanza `KeyError` en mitad del
  documento y util_bbdd aborta ese formato y los que faltaban (G41).
- **Excel** no admite plantilla: `ExcelGenerator` crea un libro nuevo con colores RGB fijos (la paleta de Office),
  fuentes sin nombre y tablas con un `table_style` que además es el mismo valor que el de Word (G40).
- Una plantilla la sube un usuario y la abren otros al descargar la documentación: puede llevar macros, objetos
  OLE/ActiveX, una plantilla adjunta remota o campos DDE.

## Decisión

1. **Dos ámbitos** en una tabla `document_templates` (`project_id` nulo = global): el **catálogo global** lo
   gestionan los admins (`/api/v1/admin/document-templates`) y lo ve cualquier usuario; cada **proyecto** tiene las
   suyas, que gestionan sus editores y ven sus miembros (`/api/v1/projects/{id}/document-templates`, que lista
   también las globales). Límites: `UBW_TEMPLATE_MAX_MB` (10) por fichero y `UBW_TEMPLATES_PER_SCOPE` (20) por
   ámbito; las subidas comparten el rate limit de las de la carga bulk. Sin purga por antigüedad. El nombre es único
   por ámbito y tipo sin distinguir mayúsculas (índice `uq_document_templates_scope_kind_name`, con
   `coalesce(project_id, 0)` para las globales) y el máximo se vuelve a contar después del INSERT, que en SQLite ya
   tiene el bloqueo de escritura: dos subidas simultáneas no se lo saltan. Si la fila no se guarda, se borra el
   fichero.
2. **Comprobación al subir** (contenido real, no la extensión): `.docx`/`.dotx` y `.xlsx`/`.xltx` (las plantillas de
   Office se convierten cambiando el tipo de la parte principal, porque python-docx no las abre); ZIP con su parte
   principal y tamaño descomprimido acotado (`UBW_UPLOAD_MAX_UNCOMPRESSED_MB`); se rechazan macros (`.docm`…,
   `vbaProject.bin`), objetos incrustados y ActiveX, vínculos a otros libros, relaciones externas que no sean
   hipervínculos, campos de tipo `DDE`, `DDEAUTO`, `INCLUDE`, `INCLUDETEXT`, `INCLUDEPICTURE`, `LINK` o `IMPORT` y
   cualquier DTD. El tipo es la primera palabra del código de cada campo, reconstruido a partir de sus piezas
   (`fldChar` de inicio, separador y fin y los trozos de `instrText`, con referencias de carácter resueltas); un
   campo cuyo tipo lo calcula otro campo anidado también se rechaza. Así un `MERGEFIELD Link` es válido. Word: deben estar los cinco estilos (el error dice cuáles faltan). Excel: el tema no
   puede referenciar imágenes (openpyxl no copia sus `.rels`). Se ofrecen **plantillas base** que pasan la
   comprobación (`/api/v1/document-templates/base/{word|excel}`).
3. **Estilo de tabla por plantilla**, no por ejecución: en Word, uno de los estilos de tabla de la plantilla (por
   defecto `Table Grid`); en Excel, uno predefinido `TableStyle*` (por defecto `TableStyleMedium2`). El formulario de
   lanzamiento solo añade «Plantilla Word» y «Plantilla Excel» (parámetros `word_template`/`excel_template`, tipo
   `template`), visibles si se genera ese formato; si no se genera, la plantilla se descarta.
4. **Al encolar** se comprueba que cada plantilla es del proyecto o global y del tipo correcto (422 con el campo).
   No se puede borrar una plantilla que use una documentación en cola o en curso (409).
5. **En el job**, la plantilla se copia a `inputs/plantilla_{word|excel}.{docx|xlsx}` tras comprobar su SHA-256, y
   `inputs/templates.json` registra id, ámbito, nombre, SHA-256 y si se aplicó; `run.json` lo recoge en
   `templates`. Así una ejecución no depende de que la plantilla siga existiendo. `inputs/` no son artefactos.
6. **Word**: la copia va en `plantilla_word` (y su estilo en `table_style`). **Excel**: después de generar, la capa
   anticorrupción (`excel_template.py`) pone el tema de la plantilla, cambia los colores fijos conocidos por los del
   tema (`accent1`/`accent5` con su tono: con el tema de Office se ven igual), hace que las fuentes sin nombre sigan
   la fuente del tema, copia el encabezado, el pie (sin imágenes `&G`) y la configuración de página de su primera
   hoja a todas, y aplica el estilo de tabla. Se guarda en un temporal y solo sustituye al libro si todo va bien.
7. **Formato por defecto con aviso**: si la plantilla no está (o cambió), si la de Word falla por la plantilla (estilo
   ausente, fichero ilegible) o si falla el retoque del Excel, la documentación sale **con el formato por defecto** y
   la ejecución termina bien con un aviso: `warnings` en `run.json` y en `RunDetailOut`, que el detalle muestra.
   En Word se reintenta **una sola vez** y solo si la cadena de causas apunta a la plantilla (nunca por Graphviz ni
   por la conexión); como util_bbdd aborta los formatos que faltaban, se regenera todo sin plantilla.

## Consecuencias

- **Positivas**: portada, encabezado, pie y estilos corporativos en Word; tema, encabezado, pie y estilo de tabla en
  Excel; ejecuciones reproducibles (copia y huella en `run.json`); una plantilla rota no hace perder la documentación.
- **Negativas**:
    - Excel sin portada, sin imágenes en el encabezado y solo con estilos de tabla predefinidos (openpyxl no copia
      hojas entre libros); los colores que no estén en la tabla de G40 no cambian.
    - El cambio de colores depende de cómo genera util_bbdd 4.0.0 el Excel: un test que documenta una base SQLite real
      comprueba que no queda ninguno de esos colores. Al actualizar util_bbdd, si cambian, el test falla.
    - Con plantilla Word se pierde la orientación horizontal automática, y su contenido (portada) se repite en cada
      documento cuando hay más tablas que «Tablas por documento Word».
    - Si la plantilla Word falla, los metadatos se leen dos veces (solo en ese caso).
    - `python-docx` y `openpyxl` pasan a ser dependencias directas de la web (ya llegaban con util_bbdd).

## Alternativas descartadas

- **Copiar las hojas generadas dentro de la plantilla Excel** con openpyxl: no sabe copiar hojas entre libros; habría
  que copiar celda a celda estilos, tablas y anchos, duplicando a util_bbdd fuera de su sitio.
- **Cambiar solo el tema del Excel**: las cabeceras de sección de util_bbdd tienen colores RGB fijos y seguirían en azul.
- **Fallar la ejecución si la plantilla no se aplica**: se perdería la documentación (que puede tardar minutos) por un
  problema de formato; se prefirió el formato por defecto con un aviso visible.
- **Completar los estilos que faltan en la plantilla Word**: modificaría el fichero del usuario; se rechaza con un
  mensaje claro y se ofrece la plantilla base.
