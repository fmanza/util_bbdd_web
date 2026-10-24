# Documentación y grafos de relaciones

Guía de uso de las operaciones de documentación y grafos (desde la 0.6.0, Fase 5; vigente en 1.0.0). Se lanzan desde la pestaña *Ejecuciones* de un proyecto
(rol editor) sobre una conexión asociada al proyecto, y se ejecutan en el worker como cualquier ejecución.

## Documentación de la base de datos

Documenta un schema con `DatabaseDocumentation` de util_bbdd.

| Sección del formulario | Opciones |
|---|---|
| (general) | **Conexión** (alias del proyecto) y **Schema**: vacío = el de la conexión |
| Formatos | **Word** (.docx), **Excel** (.xlsx) y **Sitio HTML**; al menos uno |
| Tablas | Tablas, columnas, claves (PK, FK, únicas), índices y DDL |
| Vistas | Vistas (columnas) y su DDL |
| Rutinas | Procedimientos y funciones |
| Información adicional | Datos de la BD (versión), almacenamiento, condiciones del motor, charset y collation |
| Diagramas | Diagramas de relaciones en Word y HTML, con profundidad (1–3), dirección y columnas de cada tabla (ver abajo) |
| Presentación | Tablas por documento Word (si hay más, se generan varios) y elementos por página del índice HTML |

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

Una tabla **sin relaciones** se dibuja sola en el Word, pero el sitio HTML no muestra su diagrama (GAPS G38).

**Schema por motor**: en PostgreSQL, SQL Server y HSQLDB es el schema; en MySQL y MariaDB, la base de datos; en
SQLite no aplica. En **Oracle**, util_bbdd solo documenta el schema del **usuario de la conexión**: deja el campo
vacío o pon ese usuario; para otro schema, crea una conexión con su usuario (el formulario lo avisa; GAPS G21).

Al terminar, el detalle de la ejecución muestra la tarjeta **Documentación**:

- Botones de descarga del Word y del Excel.
- El **sitio HTML** navegable dentro de la página, y **Abrir en pestaña nueva**. El sitio se ve con sus scripts, pero
  aislado: no puede leer tu sesión ni llamar a la API ([ADR-007](../adr/ADR-007-sitio-html-aislado.md)). Su enlace es
  temporal (caduca con la inactividad de la sesión, 60 minutos por defecto): si caduca, recarga el detalle.
- **Descargar ZIP** baja todo, incluido el sitio completo para abrirlo sin servidor.

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
| `connection_failed` | La BD no responde o rechaza las credenciales | Prueba la conexión desde su ficha |

Documentar un schema grande lleva tiempo (cada diagrama es un proceso `dot`); el límite es el de cualquier
ejecución (`UBW_JOB_TIMEOUT_SECONDS`, 1 hora por defecto).
