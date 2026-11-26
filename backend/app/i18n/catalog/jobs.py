"""Mensajes de las áreas ``jobs`` (fallos de las ejecuciones que guarda el worker) e ``integrations`` (motivos que la
capa de integración con util_bbdd da al usuario) (ADR-015).

Los marcadores ``{reason}`` llevan texto de util_bbdd o del motor ya saneado (sin rutas ni secretos): no se traduce.
"""

from __future__ import annotations

from typing import Final

ES: Final[dict[str, str]] = {
    # Worker y runner
    "jobs.unexpected": "Error inesperado ({exc_type}).",
    "jobs.interrupted": "El worker se detuvo durante la ejecución.",
    "jobs.worker_crash": "El proceso del job terminó de forma inesperada (código {exitcode}).",
    "jobs.cancelled_by_user": "Cancelada por un usuario.",
    "jobs.timeout": "Superó el tiempo máximo ({limit} s).",
    # Fallos de util_bbdd o del driver por código (nunca su texto)
    "jobs.connection_failed": "No se pudo conectar con la base de datos.",
    "jobs.driver_missing": "El driver del motor no está instalado en el servidor.",
    "jobs.timeout_db": "La base de datos no respondió a tiempo.",
    "jobs.invalid_config": "Parámetros no válidos para util_bbdd.",
    "jobs.library_failed": "util_bbdd falló ({exc_type}).",
    # Comprobaciones comunes en el worker
    "jobs.project_gone": "El proyecto ya no existe.",
    "jobs.run_gone": "La ejecución ya no existe.",
    "jobs.connection_alias_missing": "El proyecto no tiene la conexión «{alias}».",
    "jobs.connection_alias_gone": "El proyecto ya no tiene la conexión «{alias}».",
    "jobs.no_permission_for": "El usuario ya no tiene permiso para {action}.",
    "jobs.owner_only_for": "Solo el propietario del proyecto puede {action}.",
    "jobs.not_member": "El usuario ya no es miembro del proyecto.",
    "jobs.action.write_data": "escribir datos",
    "jobs.action.bulk": "cargar datos",
    "jobs.action.dump": "volcar datos",
    "jobs.action.restore": "restaurar constraints",
    "jobs.action.migrate": "aplicar migraciones",
    "jobs.preview_gone": "La vista previa ya no existe.",
    "jobs.preview_unavailable": "La vista previa ya no está disponible (¿purgada?).",
    "jobs.target_read_only": "La conexión destino es de solo lectura.",
    "jobs.target_engine_changed": "La conexión destino ya no es {engine}.",
    "jobs.cancelled_before_write": "Cancelada por un usuario antes de escribir en el destino.",
    "jobs.list.1": "{a}",
    "jobs.list.2": "{a}; {b}",
    "jobs.list.3": "{a}; {b}; {c}",
    "jobs.noop_failed": "Fallo simulado (fail = true).",
    # Documentación y grafos
    "jobs.doc.graphviz_failed": (
        "Graphviz no pudo dibujar un diagrama de relaciones. Reduce la profundidad o desactiva los diagramas."
    ),
    "jobs.doc.trace_map_gone": "El mapa de trazabilidad ya no está disponible.",
    "jobs.doc.previous_invalid": "La documentación anterior no es válida.",
    "jobs.doc.previous_missing": "La documentación anterior no existe en el proyecto.",
    "jobs.doc.no_relations": "No hay relaciones que dibujar con esos parámetros.",
    # Comparación
    "jobs.compare.side.source": "Origen: {reason}",
    "jobs.compare.side.target": "Destino: {reason}",
    # Volcado
    "jobs.dump.no_matching_tables": "Ninguna tabla del origen casa con el filtro de tablas.",
    "jobs.dump.unknown_tables": "Tablas que no existen en el origen: {tables}",
    "jobs.dump.structure_changed": "Las tablas o columnas cambiaron desde la vista previa: repítela.",
    "jobs.dump.cancelled": "Cancelada por un usuario: {loaded} de {total} tablas cargadas; la tabla en curso se deshizo.",
    "jobs.dump.cancelled_pending": (
        "Cancelada por un usuario: {loaded} de {total} tablas cargadas; la tabla en curso se deshizo; quedan "
        "constraints sin restaurar: restáuralas desde el resultado."
    ),
    "jobs.dump.partial": "Volcado incompleto; {details}.",
    "jobs.dump.failed_tables": "tablas con error: {tables}",
    "jobs.dump.broken_constraints": "constraints que no se pudieron reactivar: {constraints}",
    "jobs.dump.pending_constraints": "quedan constraints sin restaurar: restáuralas desde el resultado",
    "jobs.dump.confirm_mismatch": "La confirmación no es el alias de la conexión destino.",
    "jobs.dump.journal_invalid": "El diario de constraints no es válido para este destino.",
    "jobs.dump.restore_partial": (
        "No se pudieron reactivar todas las constraints; corrige los datos y vuelve a restaurar."
    ),
    "jobs.dump.restore_partial_list": (
        "No se pudieron reactivar todas las constraints: {constraints}; corrige los datos y vuelve a restaurar."
    ),
    # Migración DDL
    "jobs.migrate.engines_unsupported": "Combinación de motores no soportada por util_bbdd.",
    "jobs.migrate.no_matching_tables": "Ninguna tabla ni vista del schema casa con el filtro de tablas.",
    "jobs.migrate.plan_gone": "El plan ya no existe.",
    "jobs.migrate.plan_unavailable": "El plan ya no está disponible (¿purgado?).",
    "jobs.migrate.plan_outdated": (
        "El plan se generó con otra versión de util_bbdd o está dañado: vuelve a planificar."
    ),
    "jobs.migrate.source_changed": "El origen ha cambiado desde el plan: vuelve a planificar.",
    "jobs.migrate.plan_not_reviewed": "El plan guardado no es el revisado: vuelve a planificar.",
    "jobs.migrate.plan_blocked": "El plan tiene avisos de severidad ERROR.",
    "jobs.migrate.fk_type_mismatch": "El plan tiene claves foráneas entre tipos distintos.",
    "jobs.migrate.target_conflict": "El destino ya tiene tablas o vistas del plan: {tables}.",
    "jobs.migrate.fk_blocking": "Claves foráneas entre tipos distintos (el destino las rechazará): {pairs}.",
    "jobs.migrate.view_invalid": "Vistas que no se pueden crear en el destino: {views}.",
    "jobs.migrate.cancelled": (
        "Cancelada entre sentencias: quedaron aplicadas {applied} de {statements} en el destino."
    ),
    "jobs.migrate.apply_partial": (
        "Falló la sentencia {position}/{statements}; quedaron aplicadas {applied}. Motor: {error}"
    ),
    # Carga bulk
    "jobs.bulk.upload_gone": "El fichero ya no existe en el proyecto.",
    "jobs.bulk.target_gone": "El proyecto ya no tiene la conexión destino.",
    "jobs.bulk.structure_changed": "La tabla o el mapeo cambiaron desde la vista previa: repítela.",
    "jobs.bulk.matches_changed": (
        "Ahora coinciden {matches} filas, no las {confirmed} confirmadas: repite la vista previa."
    ),
    "jobs.bulk.cancelled_kept": (
        "Cancelada por un usuario: quedan confirmadas {committed} filas de las particiones terminadas."
    ),
    "jobs.bulk.cancelled_rolled_back": "Cancelada por un usuario: la carga se deshizo entera; no se escribió nada.",
    "jobs.bulk.failed": "La carga falló: {error}",
    "jobs.bulk.partial": "Fallaron {partitions} particiones; las demás quedaron confirmadas.",
    # Capa de integración con util_bbdd
    "integrations.schema_not_found.source": "El schema «{schema}» no existe en el origen.",
    "integrations.schema_not_found.target": "El schema «{schema}» no existe en el destino.",
    "integrations.invalid_conn_params": "{reason}",
    "integrations.graphviz_missing": "Graphviz (dot) no está instalado en el servidor.",
    "integrations.doc.table_not_found": "La tabla «{table}» no existe en el schema.",
    "integrations.doc.invalid_trace_map": "{reason}",
    "integrations.doc.invalid_previous": "{reason}",
    "integrations.bulk.table_not_found": "La tabla «{table}» no existe en el destino.",
    "integrations.bulk.file_invalid": "{reason}",
    "integrations.sql.engine_unsupported": "El SQL libre no está disponible para {db_type}.",
    "integrations.sql.parse_error": "No se ha podido analizar el SQL; revisa la sintaxis.",
    "integrations.sql.single_statement": "Escribe una única sentencia (sin «;» entre varias).",
    "integrations.sql.select_only": "Solo se admiten consultas SELECT (también con WITH o UNION).",
    "integrations.sql.forbidden_node": "La consulta contiene una operación no permitida ({node}).",
    "integrations.sql.invalid_template_param": "Parámetro no válido en la plantilla: «{{{field}}}»",
    "integrations.sql.engine_error": "{reason}",
    "integrations.sql.invalid_query_params": "Parámetros no válidos para la query ({exc_type}).",
}

EN: Final[dict[str, str]] = {
    "jobs.unexpected": "Unexpected error ({exc_type}).",
    "jobs.interrupted": "The worker stopped during the run.",
    "jobs.worker_crash": "The job process ended unexpectedly (code {exitcode}).",
    "jobs.cancelled_by_user": "Cancelled by a user.",
    "jobs.timeout": "Exceeded the maximum time ({limit} s).",
    "jobs.connection_failed": "Could not connect to the database.",
    "jobs.driver_missing": "The engine driver is not installed on the server.",
    "jobs.timeout_db": "The database did not respond in time.",
    "jobs.invalid_config": "Invalid parameters for util_bbdd.",
    "jobs.library_failed": "util_bbdd failed ({exc_type}).",
    "jobs.project_gone": "The project no longer exists.",
    "jobs.run_gone": "The run no longer exists.",
    "jobs.connection_alias_missing": "The project has no connection “{alias}”.",
    "jobs.connection_alias_gone": "The project no longer has the connection “{alias}”.",
    "jobs.no_permission_for": "The user no longer has permission to {action}.",
    "jobs.owner_only_for": "Only the project owner can {action}.",
    "jobs.not_member": "The user is no longer a member of the project.",
    "jobs.action.write_data": "write data",
    "jobs.action.bulk": "load data",
    "jobs.action.dump": "dump data",
    "jobs.action.restore": "restore constraints",
    "jobs.action.migrate": "apply migrations",
    "jobs.preview_gone": "The preview no longer exists.",
    "jobs.preview_unavailable": "The preview is no longer available (purged?).",
    "jobs.target_read_only": "The target connection is read-only.",
    "jobs.target_engine_changed": "The target connection is no longer {engine}.",
    "jobs.cancelled_before_write": "Cancelled by a user before writing to the target.",
    "jobs.list.1": "{a}",
    "jobs.list.2": "{a}; {b}",
    "jobs.list.3": "{a}; {b}; {c}",
    "jobs.noop_failed": "Simulated failure (fail = true).",
    "jobs.doc.graphviz_failed": (
        "Graphviz could not draw a relationship diagram. Reduce the depth or turn off the diagrams."
    ),
    "jobs.doc.trace_map_gone": "The traceability map is no longer available.",
    "jobs.doc.previous_invalid": "The previous documentation is not valid.",
    "jobs.doc.previous_missing": "The previous documentation does not exist in the project.",
    "jobs.doc.no_relations": "There are no relationships to draw with those parameters.",
    "jobs.compare.side.source": "Source: {reason}",
    "jobs.compare.side.target": "Target: {reason}",
    "jobs.dump.no_matching_tables": "No source table matches the table filter.",
    "jobs.dump.unknown_tables": "Tables that do not exist in the source: {tables}",
    "jobs.dump.structure_changed": "The tables or columns changed since the preview: run it again.",
    "jobs.dump.cancelled": "Cancelled by a user: {loaded} of {total} tables loaded; the table in progress was rolled back.",
    "jobs.dump.cancelled_pending": (
        "Cancelled by a user: {loaded} of {total} tables loaded; the table in progress was rolled back; some "
        "constraints were not restored: restore them from the result."
    ),
    "jobs.dump.partial": "Incomplete dump; {details}.",
    "jobs.dump.failed_tables": "tables with errors: {tables}",
    "jobs.dump.broken_constraints": "constraints that could not be re-enabled: {constraints}",
    "jobs.dump.pending_constraints": "some constraints were not restored: restore them from the result",
    "jobs.dump.confirm_mismatch": "The confirmation is not the alias of the target connection.",
    "jobs.dump.journal_invalid": "The constraint journal is not valid for this target.",
    "jobs.dump.restore_partial": "Not all constraints could be re-enabled; fix the data and restore again.",
    "jobs.dump.restore_partial_list": (
        "Not all constraints could be re-enabled: {constraints}; fix the data and restore again."
    ),
    "jobs.migrate.engines_unsupported": "Engine combination not supported by util_bbdd.",
    "jobs.migrate.no_matching_tables": "No table or view in the schema matches the table filter.",
    "jobs.migrate.plan_gone": "The plan no longer exists.",
    "jobs.migrate.plan_unavailable": "The plan is no longer available (purged?).",
    "jobs.migrate.plan_outdated": "The plan was generated with another version of util_bbdd or is damaged: plan again.",
    "jobs.migrate.source_changed": "The source has changed since the plan: plan again.",
    "jobs.migrate.plan_not_reviewed": "The stored plan is not the reviewed one: plan again.",
    "jobs.migrate.plan_blocked": "The plan has ERROR severity warnings.",
    "jobs.migrate.fk_type_mismatch": "The plan has foreign keys between different types.",
    "jobs.migrate.target_conflict": "The target already has tables or views from the plan: {tables}.",
    "jobs.migrate.fk_blocking": "Foreign keys between different types (the target will reject them): {pairs}.",
    "jobs.migrate.view_invalid": "Views that cannot be created in the target: {views}.",
    "jobs.migrate.cancelled": "Cancelled between statements: {applied} of {statements} were applied to the target.",
    "jobs.migrate.apply_partial": "Statement {position}/{statements} failed; {applied} were applied. Engine: {error}",
    "jobs.bulk.upload_gone": "The file no longer exists in the project.",
    "jobs.bulk.target_gone": "The project no longer has the target connection.",
    "jobs.bulk.structure_changed": "The table or the mapping changed since the preview: run it again.",
    "jobs.bulk.matches_changed": "{matches} rows match now, not the {confirmed} confirmed: run the preview again.",
    "jobs.bulk.cancelled_kept": "Cancelled by a user: {committed} rows from the finished partitions remain committed.",
    "jobs.bulk.cancelled_rolled_back": "Cancelled by a user: the whole load was rolled back; nothing was written.",
    "jobs.bulk.failed": "The load failed: {error}",
    "jobs.bulk.partial": "{partitions} partitions failed; the others remain committed.",
    "integrations.schema_not_found.source": "The schema “{schema}” does not exist in the source.",
    "integrations.schema_not_found.target": "The schema “{schema}” does not exist in the target.",
    "integrations.invalid_conn_params": "{reason}",
    "integrations.graphviz_missing": "Graphviz (dot) is not installed on the server.",
    "integrations.doc.table_not_found": "The table “{table}” does not exist in the schema.",
    "integrations.doc.invalid_trace_map": "{reason}",
    "integrations.doc.invalid_previous": "{reason}",
    "integrations.bulk.table_not_found": "The table “{table}” does not exist in the target.",
    "integrations.bulk.file_invalid": "{reason}",
    "integrations.sql.engine_unsupported": "Free SQL is not available for {db_type}.",
    "integrations.sql.parse_error": "The SQL could not be parsed; check the syntax.",
    "integrations.sql.single_statement": "Write a single statement (no “;” between several).",
    "integrations.sql.select_only": "Only SELECT queries are allowed (also with WITH or UNION).",
    "integrations.sql.forbidden_node": "The query contains an operation that is not allowed ({node}).",
    "integrations.sql.invalid_template_param": "Invalid parameter in the template: “{{{field}}}”",
    "integrations.sql.engine_error": "{reason}",
    "integrations.sql.invalid_query_params": "Invalid parameters for the query ({exc_type}).",
}
