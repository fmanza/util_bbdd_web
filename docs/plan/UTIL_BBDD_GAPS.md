# Huecos de la API de util_bbdd

Peticiones para util_bbdd detectadas desde la web. **No se parchea util_bbdd desde aquí**: cada hueco tiene un rodeo
en la capa anticorrupción (`backend/app/integrations/util_bbdd/`) hasta que la librería lo resuelva.

Versión analizada: **util_bbdd 4.0.0** (2026-10-19).

| # | Hueco | Impacto en la web | Rodeo actual | Petición a util_bbdd | Estado |
|---|---|---|---|---|---|
| G1 | Sin callback de progreso ni de cancelación en `DatabaseDocumentation.generate()`, `SchemaComparator.compare()`, `DumpOrchestrator.run()` ni bulk | Progreso aproximado por fases; cancelar no es cooperativo | Un subproceso por job: cancelar = terminar el proceso (ADR-002) | `on_progress` / `cancel_event` opcionales | Abierto |
| G2 | `DatabaseDocumentation._LAST_AUTO_OUTPUT_BY_KEY` (atributo de clase) reutiliza el nombre de carpeta 90 s | Salidas de usuarios distintos en la misma carpeta | `fichero_salida` explícito + `batch_window_seconds=0`; subproceso por job | Ventana desactivada por defecto o estado por instancia | Abierto |
| G3 | Sin extras `sqlserver` (pymssql), `hsqldb` (jaydebeapi) ni `sqlite-async` (aiosqlite) | La web declara esos drivers por su cuenta | Dependencias propias en `backend/pyproject.toml` | Extras en una MINOR | Abierto |
| G4 | Motores válidos de migración en constantes privadas (`migrate/planner.py`: `_SUPPORTED_SOURCE`, `_SUPPORTED_TARGET`) | La UI duplicaría la lista | Lista en la capa anticorrupción con test que la compara con un `MigrationPlanner` real | Consulta pública | Abierto |
| G5 | Sin matriz pública de capacidades por motor y operación (async, migración, readiness, grafos…) | La ficha de motor combina varias fuentes | Matriz construida en la capa anticorrupción | `get_engine_capabilities(db_type)` | Abierto |
| G6 | El `audit_sink` del volcado escribe los eventos al terminar | Sin avance por tabla durante la ejecución | Progreso por fases | Emitir eventos durante la ejecución | Abierto |
| G7 | `SchemaComparator` recibe `Inspector` y no usa `SchemaSnapshot` (ADR-003 de util_bbdd) | El adaptador crea engine e inspector | `inspect(manager.get_sqlalchemy_engine())` | Ninguna para la web; posible deuda en util_bbdd | Informativo |
| G8 | `database_types.json` lista `cx_Oracle` como driver de Oracle | Aparecería en la ficha de capacidades | Filtrar drivers no instalables en la capa anticorrupción | Revisar el dato | Abierto |
| G9 | util_bbdd 4.0.0 exige `asyncpg>=0.32`, publicado después del corte de dependencias | Excepción en `exclude-newer` | `exclude-newer-package` para asyncpg | Ninguna (informativo) | Informativo |
