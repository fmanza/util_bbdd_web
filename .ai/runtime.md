# Runtime (contexto para IAs)

## Procesos

| Proceso | Comando | Puerto |
|---|---|---|
| API (`web`) | `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8080 --proxy-headers` | 8080 (publicado en 127.0.0.1) |
| Worker | `python -m app.jobs.worker` (perfil compose `worker`) | — |
| Frontend dev | `npm run dev` (Vite, proxy `/api` → 127.0.0.1:8000) | 5173 |

`entrypoint.sh` ejecuta `alembic upgrade head` antes de cualquier proceso.

## Volúmenes y secretos

- `data` → `/data/config.db` (SQLite WAL; no copiar solo el `.db`, usar `.backup`).
- `workspace` → `/workspace/users/{user_id}/projects/{project_id}/runs/...`.
- Docker secrets: `/run/secrets/ubw_app_secret_key`, `/run/secrets/ubw_fernet_keys` (leídos por pydantic-settings
  con prefijo `UBW_`).

## Drivers en la imagen

| Motor | Driver | Nativo |
|---|---|---|
| MariaDB | `mariadb` (sync), `aiomysql` | `libmariadb3` |
| MySQL | `pymysql[rsa]`, `aiomysql` | — |
| Oracle | `oracledb` (thin; thick con `WITH_ORACLE_THICK=true`) | `libaio1` en la variante; Instant Client en `UBW_FILES_DIR` |
| PostgreSQL | `psycopg[binary]`, `psycopg-pool`, `asyncpg` | — |
| SQL Server | `pymssql` (por defecto); `pyodbc`/`aioodbc` con `WITH_ODBC=true` | `msodbcsql18` solo en la variante |
| SQLite | `sqlite3`, `aiosqlite` | — |
| HSQLDB | `jaydebeapi` con `WITH_HSQLDB=true` | JRE |

Graphviz (`dot`) está en la imagen para los grafos y diagramas de documentación.

## Validación sin uv local

```bash
docker build -f docker/Dockerfile --target backend-dev -t util_bbdd_web:backend-dev .
docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" util_bbdd_web:backend-dev uv run --frozen pytest
```
