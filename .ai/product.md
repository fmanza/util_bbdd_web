# Producto — util_bbdd_web

- **Qué es**: aplicación web multiusuario que expone la funcionalidad de la librería util_bbdd 4.3.0.
- **Versión actual**: 1.3.0 (util_bbdd 4.3.0: ola 3 del plan de huecos, migración DDL). Planes: `docs/plan/ROADMAP.md` y `docs/plan/UTIL_BBDD_GAPS_PLAN.md`.
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
