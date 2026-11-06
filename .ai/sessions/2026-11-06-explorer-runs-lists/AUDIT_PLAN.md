# AUDIT_PLAN — Explorador, eliminación de ejecuciones y listas

Revisión del [PLAN](PLAN.md). D1-D4 tomadas por el usuario ([00_REQUEST.md](00_REQUEST.md)); D5-D8 aprobadas después («Si a todo»).

## Funcional

- **F1** (A) «Hasta el máximo de la izquierda»: se interpreta como ficha y árbol con el **mismo alto**, el de la
  ventana disponible. Con un árbol de pocas tablas, la ficha sigue ocupando la altura completa (no se encoge al
  contenido de la izquierda). Confirmar con la prueba manual.
- **F2** (A) El scroll queda **dentro** de cada apartado: la página no se desplaza al recorrer un DDL largo en
  escritorio. En móvil, ficha con `70dvh` como máximo (si no, el scroll se atasca).
- **F3** (B) Borrar es irreversible y quita la fila del historial de sus usuarios. El modal lo dice; la auditoría
  conserva el resumen. *Condición*: textos del modal con el número de ejecuciones y el espacio que se libera.
- **F4** (B) Referencias que quedan colgando: «Relanzada desde» (enlace a 404), la evolución de un diff con una
  `baseline` borrada (404 ya gestionado), y una documentación en cola cuyo `markdown_previous_run` se borra (falla con
  `invalid_previous`, ya gestionado). Aceptado; **D7** decide si «Relanzada desde» se muestra sin enlace cuando no
  existe.
- **F5** (B) «Eliminar todas» también borra las `purged` (su fila queda en el historial): es lo que pide «ejecuciones y
  su contenido». El resultado distingue borradas y omitidas.
- **F6** (C) Cambiar de 50 a 25 por página: más páginas en listas largas; es lo pedido («máximo 25»).
- **F7** (C) La búsqueda en el servidor reinicia la página a 1; el orden se mantiene al cambiar de página.

## Técnico

- **T1** (A) `ScrollArea` con `mah` es la causa del recorte: usar `h="100%"` dentro de un contenedor con alto o
  `ScrollArea.Autosize`. jsdom no mide alturas: test de estructura + comprobación en navegador.
- **T2** (B) Orden de borrado: fila (cascada de artefactos) y commit → carpeta. Si `remove_tree` falla, queda una
  carpeta huérfana: log con el id y sin error al usuario (como `delete_project`). *Condición*: test con la carpeta
  borrada y con un fallo de borrado simulado.
- **T3** (B) Carrera con el worker: solo se borran terminadas; una terminada no vuelve a activa. Carrera con la
  retención (que purga): las dos son idempotentes con la carpeta ausente. El borrado por proyecto selecciona y borra
  en la misma transacción.
- **T4** (B) Volumen: un proyecto con miles de ejecuciones → `DELETE` en bloque por ids y borrado de carpetas después,
  fuera de la transacción; respuesta tras terminar (sin job). Si tarda demasiado (>10 s en el bench) se pasa a job.
- **T5** (C) `sort` siempre por **lista blanca** (`Literal`) → nunca texto del usuario en `ORDER BY`; desempate por la
  clave primaria para que `offset` no repita ni salte filas.
- **T6** (C) Orden por columnas calculadas (`duration`, `username`, `artifacts_count`): expresiones SQL o `JOIN`
  explícito; si alguna es cara, se quita de la lista blanca.
- **T7** (C) Listas en cliente: datos ya completos (decenas de filas); ordenar y paginar en memoria es suficiente.
- **T8** (C) Se toca el código de muchas páginas: el `DataTable` común evita repetir la lógica; cada página solo
  declara columnas. No es refactor encubierto: es el requisito aplicado a cada lista (el prompt prohíbe refactorizar lo
  no relacionado; no se cambia nada más de esas páginas).

## Seguridad

- **S1** (B) Todas las rutas con `AdminUser` + CSRF; un no admin recibe 403 (las rutas `/admin` ya lo hacen así).
- **S2** (B) D1: el admin ve metadatos, nunca `params`, mensajes ni artefactos de proyectos ajenos. *Condición*:
  test que compruebe que `AdminRunOut` no los lleva.
- **S3** (B) Confirmación del borrado por proyecto validada en el **servidor** (`confirm` = nombre exacto): una
  llamada accidental o un CSRF fallido no borra un proyecto entero.
- **S4** (B) Rutas de carpeta solo desde `workspace_path` con `safe_path` (como la purga); nunca desde la petición.
- **S5** (B) Auditoría de cada borrado; las filas de auditoría no se borran con la ejecución.
- **S6** (C) `q` acotado (`max_length`) y con `LIKE` escapado (`%`, `_`), como las búsquedas actuales.

## Decisiones (aprobadas por el usuario el 2026-11-06)

| # | Decisión | Aprobado |
|---|---|---|
| D5 | Botón «Copiar» en el DDL | **Sí** (`CopyButton` de Mantine; útil con DDL largos) |
| D6 | Versión | **1.14.0** para estos tres bloques (enmendada el 2026-11-06: antes 1.13.0; la ola 11, con util_bbdd 5.4.0 ya publicada, sale como 1.13.0) |
| D7 | «Relanzada desde» que apunta a una ejecución borrada | Mostrar el id **sin enlace** cuando no existe (`RunDetailOut.relaunched_from_exists`) |
| D8 | Confirmación del borrado de una ejecución | Escribir `ELIMINAR` (el id de 26 caracteres es poco práctico); el de proyecto, su nombre |

## Veredicto

**GO_CONDICIONAL** — condiciones: ~~aprobar D5-D8~~ (hecho, 2026-11-06); F3 (textos con número y espacio), T2 (test de fallo de borrado de
carpeta), S2 (test sin `params`) y S3 (confirmación en el servidor); prueba manual del explorador con un DDL largo y
con un árbol corto (F1, F2).
