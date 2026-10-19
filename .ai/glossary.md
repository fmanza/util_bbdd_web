# Glosario

| Término | Significado |
|---|---|
| **Motor** | Tipo de base de datos soportado por util_bbdd (`db_type`: mariadb, mysql, oracle, postgresql, sqlite, sqlserver, hsqldb) |
| **Capacidades** | Lo que util_bbdd permite con un motor: drivers, características, async, operaciones (migración…), parámetros de conexión |
| **Conexión** | Configuración guardada para conectar a una BD concreta (parámetros + secreto cifrado) |
| **Conexión compartida** | Creada por un admin; otros usuarios la usan sin ver el secreto |
| **Proyecto** | Espacio de trabajo de un usuario (con miembros) donde se lanzan ejecuciones sobre sus conexiones |
| **Alias** | Papel de una conexión en un proyecto (`origen`, `destino`…) |
| **Ejecución (run)** | Una invocación de una operación de util_bbdd, con estado, parámetros, logs y artefactos |
| **Artefacto** | Fichero producido por una ejecución (docx, xlsx, html, sql, md, svg, log) |
| **Workspace** | Volumen con las carpetas de las ejecuciones |
| **Manifiesto** | `run.json` de una ejecución |
| **Modo seco** | Ejecución que calcula y muestra lo que haría sin escribir en la BD destino |
| **Readiness** | Informe de util_bbdd sobre la configuración del servidor (`EngineReadinessReport`) |
| **Capa anticorrupción** | `backend/app/integrations/util_bbdd/`, único importador de util_bbdd |
| **GAP** | Hueco de la API de util_bbdd registrado en `docs/plan/UTIL_BBDD_GAPS.md` |
