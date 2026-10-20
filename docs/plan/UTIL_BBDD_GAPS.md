# Huecos de la API de util_bbdd

Peticiones para util_bbdd detectadas desde la web. **No se parchea util_bbdd desde aquí**: cada hueco tiene un rodeo
en la capa anticorrupción (`backend/app/integrations/util_bbdd/`) hasta que la librería lo resuelva.

Versión analizada: **util_bbdd 4.0.0** (2026-10-19).

| # | Hueco | Impacto en la web | Rodeo actual | Petición a util_bbdd | Estado |
|---|---|---|---|---|---|
| G1 | Sin callback de progreso ni de cancelación en `DatabaseDocumentation.generate()`, `SchemaComparator.compare()`, `DumpOrchestrator.run()` ni bulk | Progreso aproximado por fases; cancelar no es cooperativo | Un subproceso por job: cancelar = terminar el proceso (ADR-002) | `on_progress` / `cancel_event` opcionales | Abierto |
| G2 | `DatabaseDocumentation._LAST_AUTO_OUTPUT_BY_KEY` (atributo de clase) reutiliza el nombre de carpeta 90 s | Salidas de usuarios distintos en la misma carpeta | `fichero_salida` explícito + `batch_window_seconds=0`; subproceso por job | Ventana desactivada por defecto o estado por instancia | Abierto |
| G3 | Sin extras `sqlserver` (pymssql), `hsqldb` (jaydebeapi) ni `sqlite-async` (aiosqlite) | La web declara esos drivers por su cuenta | Dependencias propias en `backend/pyproject.toml` | Extras en una MINOR | Abierto |
| G4 | Motores válidos de migración en constantes privadas (`migrate/planner.py`: `_SUPPORTED_SOURCE`, `_SUPPORTED_TARGET`) | La UI duplicaría la lista | `MIGRATE_SOURCE/TARGET` en `catalog.py` con test que las compara con las constantes privadas (Fase 2) | Consulta pública | Abierto |
| G5 | Sin matriz pública de capacidades por motor y operación (async, migración, readiness, grafos…) | La ficha de motor combina varias fuentes | `EngineCapabilities` en `catalog.py`: async, migración y readiness estático (`EngineReadinessAdvisor().assess(db_type, {})`); el resto de operaciones se añade al verificarlas en su fase | `get_engine_capabilities(db_type)` | Abierto |
| G6 | El `audit_sink` del volcado escribe los eventos al terminar | Sin avance por tabla durante la ejecución | Progreso por fases | Emitir eventos durante la ejecución | Abierto |
| G7 | `SchemaComparator` recibe `Inspector` y no usa `SchemaSnapshot` (ADR-003 de util_bbdd) | El adaptador crea engine e inspector | `inspect(manager.get_sqlalchemy_engine())` | Ninguna para la web; posible deuda en util_bbdd | Informativo |
| G8 | `database_types.json` lista `cx_Oracle` como driver de Oracle | Aparecería en la ficha de capacidades | `OBSOLETE_DRIVERS` en `catalog.py` lo filtra (Fase 2) | Revisar el dato | Abierto |
| G9 | util_bbdd 4.0.0 exige `asyncpg>=0.32`, publicado después del corte de dependencias | Excepción en `exclude-newer` | `exclude-newer-package` para asyncpg | Ninguna (informativo) | Informativo |
| G10 | Sin API para saber qué drivers de un motor están instalados | La ficha no podría avisar de un driver ausente | `importlib.util.find_spec` sobre cada nombre de `drivers` (`catalog.py`) | `get_driver_status(db_type)` | Abierto |
| G11 | `SyncDatabaseManager.get_database_info()` devuelve `connection_params` **con la contraseña** | Riesgo de fuga si se serializa | No se usa; la ficha sale de `get_db_type_info_static` | Excluir o enmascarar los secretos | Abierto |
| G12 | El catálogo (`connection_params`) no marca qué parámetros son secretos, rutas del sistema de ficheros o destinos de red | La web debe clasificarlos para cifrar, confinar en `UBW_FILES_DIR` y aplicar la allowlist | `param_kind` y `KNOWN_PARAMS` en `catalog.py`, con test que avisa de parámetros nuevos | Atributo `kind` o `sensitive` por parámetro | Abierto |
| G13 | Sin API de *ping* ni de versión del servidor | La prueba de conexión no mostraría la versión | `get_sqlalchemy_engine().dialect.server_version_info` (`probe.py`) | `ping()` / `get_server_version()` | Abierto |
| G14 | `driver_info` es un `dict` en todos los motores salvo SQL Server, donde es una lista de opciones | Código defensivo en la capa | Se toma la primera opción (la predeterminada) | Forma homogénea | Abierto |
| G15 | `build_conn_params` descarta los opcionales que su *builder* no conoce (p. ej. `sslmode` en PostgreSQL) | Se perderían parámetros del usuario | `build_params` = `{**build_conn_params(...), **params_del_usuario}` | Conservar los opcionales declarados en `connection_params` | Abierto |
| G16 | `init_command` (MariaDB) ejecuta SQL arbitrario al conectar | Saltaría la protección `read_only` de la web | Parámetro bloqueado (`kind=blocked`) | Ninguna (informativo) | Informativo |
