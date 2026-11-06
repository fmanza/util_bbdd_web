# AUDIT_CODE — Explorador, eliminación de ejecuciones y listas

Revisión de los commits `026d8c8`..`bd549b6` hecha por el implementador, con comprobación en navegador.

## Condiciones del AUDIT_PLAN

| Condición | Resultado |
|---|---|
| F1/F2 explorador con DDL largo y árbol corto (manual) | Chromium contra una instancia local desechable (SQLite con una tabla de 181 columnas): árbol y ficha de 686 px en una ventana de 900 (termina a 16 px del borde), sin scroll de página; DDL con scroll propio hasta la última línea; Columnas con cabecera `sticky`; con la tabla corta la ficha mantiene el alto; en 390×844, ficha de 591 px sin desbordamiento horizontal. Encontrado y corregido el alto medido antes de existir el contenedor (`a8d94f6`) |
| F3 modal con número y espacio | Una: proyecto, operación, id y espacio. Proyecto: número de ejecuciones y tamaño (`/runs/summary`) |
| T2 fallo al borrar la carpeta | `test_delete_keeps_going_if_the_folder_cannot_be_removed`: la fila se borra, aviso en el log |
| S2 sin `params` en la lista de admin | `test_list_shows_every_project_without_content`: claves exactas de `AdminRunOut` y 404 en la API normal |
| S3 confirmación en el servidor | 422 con un nombre distinto (test) |

## Seguridad

- `/admin/*` con `AdminUser` y CSRF (403 a un usuario; tests). El admin sigue sin ver el contenido de proyectos ajenos.
- `ORDER BY` solo desde mapas de columnas por endpoint (`Literal` en la API; 422 con otro valor); desempate por clave
  primaria (`test_paging_is_stable_with_ties`).
- `LIKE` con `%`, `_` y `\` escapados (`like_pattern`; test con `a_`).
- Rutas de carpeta solo desde `workspace_path` (`run_dir`).

## Riesgos residuales

- **R1** El borrado por proyecto va en la petición (sin job); no medido con miles de ejecuciones (T4).
- **R2** La búsqueda y el orden de las listas en cliente son en memoria (decenas de filas).
- **R3** Las tablas de detalle (parámetros de un motor, readiness, salud) y los visores quedan fuera (D4).
- **R4** Sin estado de la lista en la URL (fuera de alcance).

## Veredicto

**APROBADO**.
