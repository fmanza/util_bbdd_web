# Producto — util_bbdd_web

- **Qué es**: aplicación web multiusuario que expone la funcionalidad de la librería util_bbdd 4.3.0.
- **Versión actual**: 1.21.1 (util_bbdd 5.9.0; migraciones 0005-0007 y 0010 sin recrear `users`; tema claro, oscuro o del sistema guardado en la cuenta; ventana «Lanzar ejecución» ancha con tarjetas y menú lateral agrupado con iconos desde la 1.20.0; filtro de tablas por patrones en migración y volcado desde la 1.19.0). Planes: `docs/plan/ROADMAP.md` y `docs/plan/UTIL_BBDD_GAPS_PLAN.md`.
- **Usuarios**: equipos técnicos (DBA, desarrollo, migraciones) en una red interna; rol `admin` y rol `user`.

## Capacidades objetivo

1. Catálogo de motores (MariaDB, MySQL, Oracle, PostgreSQL, SQLite, SQL Server, HSQLDB) con todas sus capacidades.
2. Conexiones por usuario o compartidas, con secretos cifrados, prueba y readiness.
3. Proyectos por usuario con miembros (`owner`/`editor`/`viewer`) y conexiones asociadas por alias.
4. Ejecuciones de util_bbdd desde un proyecto: explorador de metadatos, documentación (Word/Excel/HTML), grafos,
   comparación de esquemas, migración DDL, volcado y carga bulk.
5. Salidas en carpetas por ejecución y resultados agrupados por ejecución, con vista previa y descarga.

## Fuera de alcance (por ahora)

- Exposición directa a Internet sin proxy TLS.
- Modificar util_bbdd desde este repositorio.
- Generación de documentación mediante APIs de IA externas.
