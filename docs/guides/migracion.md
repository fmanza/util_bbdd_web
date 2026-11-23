# Migración DDL

Guía de uso de la migración DDL (desde la 0.8.0, Fase 7). Traduce las tablas, vistas y rutinas de un schema a **otro
motor** con `MigrationPlanner` de util_bbdd y, si se quiere, las **crea en una base de datos destino**. Diseño de
seguridad: [ADR-008](../adr/ADR-008-aplicar-migraciones.md).

Motores: origen y destino Oracle, MariaDB, MySQL, SQL Server y PostgreSQL, siempre distintos. Solo migra la
estructura (DDL), no los datos.

## 1. Planificar

En la pestaña *Ejecuciones* del proyecto (rol editor), **Lanzar ejecución → Plan de migración DDL** (grupo *Mover a
otra base de datos* de la lista de operaciones):

| Campo | Efecto |
|---|---|
| Origen: conexión y schema | Lo que se migra; schema vacío = el de la conexión (Oracle: el usuario) |
| Destino: motor | Motor para el que se genera el DDL (empieza en «Elige…»); en la misma tarjeta, las opciones de ese motor (charset, collation, schema destino, autoincrementales…), solo las del motor elegido. «Ancho de INT» (destino MariaDB/MySQL) solo aparece con origen Oracle |
| Conversión | Vistas (reescribirlas al dialecto destino o copiarlas) y, solo con origen Oracle, tipo para `NUMBER` sin precisión |
| Filtro de tablas | Desde la 1.19.0: **Incluir** y **Excluir** (patrones) y **Probar patrones**, como en la [documentación](documentacion.md#filtro-de-tablas); se aplica a tablas y vistas, no a rutinas |

El plan **no escribe en ninguna base de datos**. Su detalle muestra:

- contadores de tablas, sentencias y avisos por severidad;
- **Avisos** (filtrables): `ERROR` impide aplicar; `WARNING` e `INFO` informan (tipos aproximados, nombres
  acortados, autoincrementales…);
- **Tablas** con el tipo de cada columna en origen y destino;
- **Sentencias** con resaltado; el script completo (`migracion_<motor>.sql`) está en *Artefactos*, con vista previa
  resaltada y **Copiar SQL** (desde la 1.17.0), y se descarga.

**Filtro de tablas** (1.19.0, util_bbdd 5.9.0): el plan lleva solo las tablas y vistas que casan con los patrones.
Una FK de una tabla del plan hacia una tabla que queda fuera se añade al final del script (aviso `FK_OUTSIDE_FILTER`):
esa tabla **debe existir ya en el destino**. El detalle del plan muestra los patrones y la **frontera**, las tablas de
fuera unidas por FK a las del plan. Una vista del plan que lea una tabla de fuera falla en el modo seco si esa tabla no
existe en el destino. Si no casa ninguna tabla ni vista, el plan termina con `invalid_params`.

**Claves foráneas**: cada columna FK recibe el tipo destino de la columna que referencia (aviso `INFO`
`FK_TYPE_ALIGNED`; p. ej. Oracle `INT` en PK y FK pasa a `INT(11)` en las dos). Si no se puede (columna referenciada
inexistente u omitida), el aviso `FK_TYPE_UNRESOLVED` es `ERROR` e impide aplicar. Los planes generados antes de la
versión 1.3.0 pueden tener FK entre tipos distintos: el plan lo avisa y, con destino MariaDB o MySQL, que siempre
rechazan esas FK, **no se puede aplicar** hasta volver a planificar.

## 2. Modo seco

Requisitos (si no se cumplen, el panel *Aplicar en una base de datos destino* explica por qué):

- el permiso **«Puede aplicar DDL»**, que concede un administrador en *Usuarios*;
- ser **propietario** del proyecto;
- una conexión del proyecto del motor destino que **no** sea de solo lectura.

Elige la conexión destino y pulsa **Modo seco**. Sin dejar cambios, comprueba que:

- el plan que se aplicará es **exactamente el revisado**: desde la versión 1.3.0 se guarda completo y se aplica sin
  volver a leer el origen (los planes anteriores se vuelven a planificar y, si el origen cambió, hay que planificar
  de nuevo);
- el destino **no tiene ya** tablas o vistas con los nombres de las tablas o vistas del plan;
- las **vistas** se pueden crear (en PostgreSQL y SQL Server, creándolas en una transacción que se deshace; en el
  resto, comprobando la sintaxis);
- no hay FK entre tipos distintos que el destino rechace.

## 3. Aplicar

Con un modo seco **correcto de la última hora** sobre esa conexión, **Aplicar…** abre la confirmación: marca que
entiendes que **no es atómico** y escribe el alias de la conexión destino.

> Las sentencias se aplican una a una. Si una falla, **las anteriores quedan aplicadas** y hay que deshacerlas a mano.
> El informe dice qué sentencia falló, cuántas se aplicaron y el mensaje del motor.

El detalle de la aplicación tiene el informe y el rastro de auditoría (`outputs/audit/migracion.jsonl`: una línea por
sentencia con su duración y resultado). Las aplicaciones no se relanzan: para repetir, lanza un modo seco nuevo
desde el plan. No se puede aplicar dos veces a la vez sobre el mismo destino.

Mientras se aplica, el detalle muestra el avance por sentencia («Sentencias: 3 de 12 (CREATE TABLE …)»). Una
aplicación **en curso se puede cancelar, pero solo entre sentencias**: tras confirmarlo, termina la sentencia en
curso y se detiene antes de la siguiente. Las ya aplicadas **quedan en el destino** (el DDL no se deshace) y el
informe dice cuántas. La web nunca corta una sentencia a medias; solo el tiempo máximo de las ejecuciones
(`UBW_JOB_TIMEOUT_SECONDS`) detiene el proceso igualmente: lo aplicado hasta entonces está en `migracion.jsonl`.

Con destino PostgreSQL y **Schema destino**, los conflictos se buscan en ese schema, que es donde el script crea las
tablas.

## Errores frecuentes

| Código | Causa | Qué hacer |
|---|---|---|
| 403 al lanzar | Sin el permiso «Puede aplicar DDL» o sin ser propietario | Pídelo a un administrador o al propietario |
| `plan_changed` | El plan guardado no es el revisado, se generó con otra versión de util_bbdd o (planes anteriores a la 1.3.0) el origen cambió | Planifica de nuevo y revisa |
| `target_conflict` | El destino ya tiene tablas o vistas con esos nombres | Bórralas o usa otro schema/BD destino |
| `fk_type_mismatch` | FK entre tipos distintos con destino MariaDB/MySQL (planes anteriores a la 1.3.0) | Planifica de nuevo |
| `view_invalid` | Una vista no se puede crear en el destino | Revisa su SQL (o usa *Copiar sin cambios*) |
| `apply_partial` | Falló una sentencia al aplicar | Lee el informe; deshaz lo aplicado o corrige y aplica lo que falta a mano |
| `invalid_params` «Ninguna tabla ni vista … casa con el filtro» | Los patrones no dejan nada del schema | Usa **Probar patrones** antes de lanzar |
