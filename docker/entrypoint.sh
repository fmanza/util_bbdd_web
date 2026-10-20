#!/bin/sh
# Aplica las migraciones de config.db y ejecuta el comando del contenedor (API o worker).
set -eu
cd /app
# Carpeta de ficheros a los que pueden apuntar las conexiones (SQLite, JAR, certificados): UBW_FILES_DIR.
mkdir -p "${UBW_FILES_DIR:-/data/files}"
alembic upgrade head
exec "$@"
