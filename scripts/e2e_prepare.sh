#!/usr/bin/env bash
# Prepara un `docker compose` ya levantado para la E2E de Playwright (frontend/e2e/): crea el admin E2E y copia a
# /data/files las BD SQLite de los fixtures. Lo usan el CI (job `e2e`) y el desarrollo en local.
#
#   UBW_E2E_ADMIN_USER=e2e-admin UBW_E2E_ADMIN_PASSWORD='…' scripts/e2e_prepare.sh
#
# Desde la raíz del repositorio. Se puede repetir: si el admin ya existe, lo avisa y sigue; las BD se sustituyen.
set -euo pipefail

: "${UBW_E2E_ADMIN_USER:=e2e-admin}"
if [ -z "${UBW_E2E_ADMIN_PASSWORD:-}" ]; then
  echo "Define UBW_E2E_ADMIN_PASSWORD." >&2
  exit 2
fi
PYTHON=$(command -v python3 || command -v python)
FIXTURES=frontend/e2e/fixtures
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. Admin E2E (rol base «Administrador», con todos los permisos).
if ! printf '%s\n' "$UBW_E2E_ADMIN_PASSWORD" |
  docker compose exec -T web python -m app.cli create-admin --username "$UBW_E2E_ADMIN_USER" --password-stdin; then
  echo "Aviso: no se creó «$UBW_E2E_ADMIN_USER» (¿ya existe?); se usa el existente." >&2
fi

# 2. BD SQLite: nombre en el contenedor → script de los fixtures.
DATABASES=(
  "e2e-tienda.db:tienda.sql"
  "e2e-tienda-v2.db:tienda_v2.sql"
  "e2e-volcado-origen.db:volcado.sql"
  "e2e-volcado-destino.db:volcado_vacio.sql"
  "e2e-carga.db:volcado_vacio.sql"
)
for entry in "${DATABASES[@]}"; do
  name=${entry%%:*}
  script=${entry#*:}
  "$PYTHON" -c 'import sqlite3, sys; sqlite3.connect(sys.argv[1]).executescript(open(sys.argv[2], encoding="utf-8").read())' \
    "$WORK/$name" "$FIXTURES/$script"
  docker compose cp "$WORK/$name" "web:/data/files/$name"
  # `docker compose cp` deja el fichero como root y el contenedor no tiene CAP_CHOWN: copiarlo lo deja del usuario app.
  docker compose exec -T web sh -c "cd /data/files && cp '$name' .tmp-e2e && mv -f .tmp-e2e '$name'"
done

echo "E2E preparada: admin «$UBW_E2E_ADMIN_USER» y ${#DATABASES[@]} BD SQLite en /data/files."
