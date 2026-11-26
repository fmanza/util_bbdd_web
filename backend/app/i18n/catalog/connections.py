"""Mensajes de motores, conexiones, allowlist, explorador de metadatos, queries nombradas y SQL libre (ADR-015).

``connections.probe.<código>`` son los motivos estables de una prueba de conexión fallida (``ERROR_MESSAGES``).
"""

from __future__ import annotations

from typing import Final

ES: Final[dict[str, str]] = {
    # Títulos
    "title.engine_not_found": "Motor no encontrado",
    "title.connection_not_found": "Conexión no encontrada",
    "title.connection_forbidden": "No puedes modificar esta conexión",
    "title.connection_name_taken": "Ya tienes una conexión con ese nombre",
    "title.connection_params": "Parámetros de conexión no válidos",
    "title.too_many_tests": "Demasiadas pruebas de conexión en curso",
    "title.invalid_allowlist_pattern": "Patrón de destino no válido",
    "title.allowlist_entry_not_found": "Destino no encontrado",
    "title.allowlist_duplicate": "El destino ya está en la lista",
    "title.database_access": "No se pudo consultar la base de datos",
    "title.database_timeout": "La base de datos no respondió a tiempo",
    "title.object_not_found": "Objeto no encontrado en el schema",
    "title.sql_not_allowed": "No tienes permiso para ejecutar SQL libre",
    "title.connection_not_read_only": "El SQL libre solo se permite sobre conexiones de solo lectura",
    "title.sql_rejected": "Consulta no admitida",
    "title.named_query_not_found": "Query no encontrada",
    "title.named_query_name_taken": "Ya existe una query con ese nombre para el motor",
    "title.named_query_invalid": "Query no válida",
    # Motivos de una prueba de conexión fallida
    "connections.probe.driver_missing": "El driver del motor no está instalado en el servidor.",
    "connections.probe.invalid_config": "Los parámetros de conexión no son válidos para el motor.",
    "connections.probe.connection_failed": (
        "No se pudo conectar: servidor inaccesible, credenciales incorrectas o BD inexistente."
    ),
    "connections.probe.timeout": "La conexión no respondió a tiempo.",
    "connections.probe.not_allowed": (
        "El destino no está en la lista de destinos permitidos. Pide a un administrador que lo añada."
    ),
    "connections.probe.secret_unreadable": "No se puede descifrar la contraseña guardada: vuelve a introducirla.",
    "connections.probe.unknown": "Error inesperado al conectar.",
    # Conexiones
    "connections.too_many_tests": "Espera unos segundos y vuelve a intentarlo.",
    "connections.shared_admin_only": "Es una conexión compartida: solo un administrador puede modificarla.",
    "connections.share_permission": "Tu rol no tiene el permiso «Compartir conexiones».",
    "connections.name_empty": "El nombre no puede estar vacío.",
    "connections.invalid_params": "{reason}",
    "connections.param_type": "«{name}» debe ser de tipo {type}.",
    "connections.param_options": "«{name}» debe ser uno de: {options}.",
    "connections.param_options_or_empty": "«{name}» debe ser uno de: {options}, (vacío).",
    "connections.param_too_long": "«{name}» es demasiado largo.",
    "connections.param_empty": "«{name}» no puede estar vacío.",
    "connections.path_outside_files": (
        "«{name}» debe ser una ruta dentro de la carpeta de ficheros del servidor (UBW_FILES_DIR)."
    ),
    "connections.jdbc_url": "«jdbc_url» debe ser jdbc:hsqldb:hsql://, hsqls://, http(s)://, file: o mem:.",
    "connections.not_a_param": "«{name}» no es un parámetro de {engine}.",
    "connections.password_in_params": "La contraseña se envía en el campo «password», no en «params».",
    "connections.param_blocked": "«{name}» no se admite por seguridad.",
    "connections.sqlite_memory": "Las BD en memoria no tienen sentido en el servidor.",
    "connections.allowlist_pattern": (
        "Usa una red CIDR (10.0.0.0/8), una IP, un nombre de host (db.empresa.local) o un comodín (*.empresa.local)."
    ),
    # Motores
    "engines.not_supported": "util_bbdd no soporta el motor «{db_type}».",
    # Explorador, queries nombradas y SQL libre
    "explorer.query_error": "El motor rechazó la consulta.",
    "explorer.not_read_only": "Solo se admiten consultas de lectura.",
    "explorer.rejected": "{reason}",
    "explorer.table_not_found": "La tabla «{table}» no está en el schema (prueba a refrescar).",
    "explorer.sql_not_allowed": "Tu rol no tiene el permiso «Ejecutar SQL libre»; pídeselo a un administrador.",
    "explorer.connection_not_read_only": "Marca la conexión como «Solo lectura» para usar SQL libre sobre ella.",
    "explorer.sql_too_long": "La consulta supera {max_chars} caracteres.",
    "explorer.query_other_engine": "La query no es de este motor.",
    "explorer.param_required": "Obligatorio",
    "explorer.param_unknown": "No es un parámetro de la query",
    "explorer.param_value": "Solo identificadores (letras, números, _ $ #) o números",
    "explorer.check_params": "Revisa los parámetros de la query.",
}

EN: Final[dict[str, str]] = {
    "title.engine_not_found": "Engine not found",
    "title.connection_not_found": "Connection not found",
    "title.connection_forbidden": "You cannot modify this connection",
    "title.connection_name_taken": "You already have a connection with that name",
    "title.connection_params": "Invalid connection parameters",
    "title.too_many_tests": "Too many connection tests in progress",
    "title.invalid_allowlist_pattern": "Invalid destination pattern",
    "title.allowlist_entry_not_found": "Destination not found",
    "title.allowlist_duplicate": "The destination is already on the list",
    "title.database_access": "The database could not be queried",
    "title.database_timeout": "The database did not respond in time",
    "title.object_not_found": "Object not found in the schema",
    "title.sql_not_allowed": "You are not allowed to run free SQL",
    "title.connection_not_read_only": "Free SQL is only allowed on read-only connections",
    "title.sql_rejected": "Query not allowed",
    "title.named_query_not_found": "Query not found",
    "title.named_query_name_taken": "A query with that name already exists for the engine",
    "title.named_query_invalid": "Invalid query",
    "connections.probe.driver_missing": "The engine driver is not installed on the server.",
    "connections.probe.invalid_config": "The connection parameters are not valid for the engine.",
    "connections.probe.connection_failed": (
        "Could not connect: server unreachable, wrong credentials or database does not exist."
    ),
    "connections.probe.timeout": "The connection did not respond in time.",
    "connections.probe.not_allowed": (
        "The destination is not on the list of allowed destinations. Ask an administrator to add it."
    ),
    "connections.probe.secret_unreadable": "The saved password cannot be decrypted: enter it again.",
    "connections.probe.unknown": "Unexpected error while connecting.",
    "connections.too_many_tests": "Wait a few seconds and try again.",
    "connections.shared_admin_only": "It is a shared connection: only an administrator can modify it.",
    "connections.share_permission": "Your role does not have the “Share connections” permission.",
    "connections.name_empty": "The name cannot be empty.",
    "connections.invalid_params": "{reason}",
    "connections.param_type": "“{name}” must be of type {type}.",
    "connections.param_options": "“{name}” must be one of: {options}.",
    "connections.param_options_or_empty": "“{name}” must be one of: {options}, (empty).",
    "connections.param_too_long": "“{name}” is too long.",
    "connections.param_empty": "“{name}” cannot be empty.",
    "connections.path_outside_files": "“{name}” must be a path inside the server's files folder (UBW_FILES_DIR).",
    "connections.jdbc_url": "“jdbc_url” must be jdbc:hsqldb:hsql://, hsqls://, http(s)://, file: or mem:.",
    "connections.not_a_param": "“{name}” is not a parameter of {engine}.",
    "connections.password_in_params": "The password is sent in the “password” field, not in “params”.",
    "connections.param_blocked": "“{name}” is not allowed for security reasons.",
    "connections.sqlite_memory": "In-memory databases make no sense on the server.",
    "connections.allowlist_pattern": (
        "Use a CIDR network (10.0.0.0/8), an IP, a host name (db.company.local) or a wildcard (*.company.local)."
    ),
    "engines.not_supported": "util_bbdd does not support the engine “{db_type}”.",
    "explorer.query_error": "The engine rejected the query.",
    "explorer.not_read_only": "Only read queries are allowed.",
    "explorer.rejected": "{reason}",
    "explorer.table_not_found": "The table “{table}” is not in the schema (try refreshing).",
    "explorer.sql_not_allowed": "Your role does not have the “Run free SQL” permission; ask an administrator.",
    "explorer.connection_not_read_only": "Mark the connection as “Read only” to use free SQL on it.",
    "explorer.sql_too_long": "The query exceeds {max_chars} characters.",
    "explorer.query_other_engine": "The query does not belong to this engine.",
    "explorer.param_required": "Required",
    "explorer.param_unknown": "Not a parameter of the query",
    "explorer.param_value": "Only identifiers (letters, digits, _ $ #) or numbers",
    "explorer.check_params": "Review the query parameters.",
}
