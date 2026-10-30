#!/bin/sh
# Aplica las migraciones de config.db y ejecuta el comando del contenedor (API o worker).
set -eu
cd /app
# Carpeta de ficheros a los que pueden apuntar las conexiones (SQLite, JAR, certificados): UBW_FILES_DIR.
mkdir -p "${UBW_FILES_DIR:-/data/files}"
# Oracle thick: el Instant Client 19 no lleva RUNPATH $ORIGIN, así que libclntsh no encuentra libnnz19.so por lib_dir
# (oracle_client_path); la carpeta tiene que estar en LD_LIBRARY_PATH al arrancar. Los jobs (spawn) lo heredan.
if [ -n "${UBW_ORACLE_CLIENT_DIR:-}" ]; then
    export LD_LIBRARY_PATH="${UBW_FILES_DIR:-/data/files}/${UBW_ORACLE_CLIENT_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
alembic upgrade head
exec "$@"
