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
| **Rol** | Nombre y permisos del catálogo (ADR-014); cada usuario tiene uno. Base: *Administrador* (todos) y *Usuario* (ninguno) |
| **Permiso** | Entrada del catálogo fijo de `app/domain/identity/permissions.py` (`users.manage`, `sql.run`…) |

## Términos en inglés de la interfaz (2.0.0)

Inglés británico, coherente con doc_organize_web. ejecución → *run*; lanzar ejecución → *Launch run*; conexión →
*connection*; motor → *engine*; volcado / volcar → *data dump* / *dump*; carga (bulk) → *bulk load*; modo seco →
*dry run*; plan de migración → *migration plan*; destinos permitidos → *allowed targets*; queries nombradas → *named
queries*; plantilla → *template*; artefactos → *artefacts*; purgar → *purge*; cuota → *quota*; retención →
*retention*; frontera → *boundary*; patrones → *patterns*; destino / origen → *target* / *source*; vista previa →
*preview*; apartar filas / rechazos → *set aside* / *rejects*; deshacer / confirmar (transacción) → *roll back* /
*commit*; lote → *batch*; sentencia → *statement*; vaciar el destino → *empty the target*; ajustar contador de PK →
*sync*; asociar conexión → *attach*; SQL libre → *free SQL*; relanzar → *relaunch*; Correcta / Fallida / Omitida →
*Succeeded* / *Failed* / *Skipped*; Mi espacio → *My storage*; catálogo → *catalogue*; Nulos → *Nullable*; rol base
→ *built-in role*; Administrador / Usuario → *Administrator* / *User*. Se quedan en español los nombres de ficheros
que genera util_bbdd (`rechazos.csv`, `volcado.jsonl`…) y los idiomas se muestran en su propio nombre (*Español*,
*English*).
