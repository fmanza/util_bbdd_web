# Petición — 2026-11-06 · Explorador, eliminación de ejecuciones y listas

Fase pedida: **PLAN y AUDIT_PLAN**.

> En conexiones en opción Explorador la información en la DDL se corta si esta es muy grande.
> - Queremos para todos los apartados (Columnas, Claves, Índices, Relaciones y DDL) que la ficha se amplie hasta el
>   máximo de la información que se muestra de las tablas a la izquierda y que el contenido si se sobrepasa se realice
>   scroll
>
> Permitir eliminar ejecuciones y su contenido, solo administrador y validación para confirmarlo. Por ejecución y por
> proyecto.
>
> En todas las listas permitir ordenar las columnas, disponer de paginación (máximo 25 filas) y permitir búsqueda

## Decisiones del usuario (2026-11-06, antes del PLAN)

| # | Pregunta | Respuesta |
|---|---|---|
| D1 | Desde dónde elimina el administrador (hoy un admin no miembro recibe 404 en el proyecto) | **Página de administración** «Ejecuciones» con las de todos los proyectos, sin abrir su contenido; borra una o todas las de un proyecto |
| D2 | Qué hace «Eliminar» | **Fila y ficheros**: desaparece del historial; la auditoría guarda el resumen. «Purgar» sigue igual para los editores |
| D3 | Ejecuciones activas o volcados con constraints pendientes al borrar un proyecto | **Omitirlas y avisar** (cuántas y por qué) |
| D4 | Qué tablas entran en «todas las listas» | **Listas de recursos** (no visores de resultados, explorador ni resultados SQL) |

D5-D8 (AUDIT_PLAN): aprobadas el 2026-11-06 («Si a todo»), junto con el commit `docs(plan)`. D6 enmienda D11-7 de
la ola 11 (sesión `2026-11-06-gaps-g50-g51`): la web de esa ola pasa a 1.14.0.
