---
applyTo: "docker/**,docker-compose*.yml,.dockerignore"
---
# Docker — reglas

- Una imagen, varios procesos: `web` (uvicorn) y `worker` (`python -m app.jobs.worker`) usan el target `runtime`.
- Etapas: `frontend-build` (Node, `npm ci`) → `backend-build` (uv, `uv sync --frozen --no-dev`) → `runtime`.
  `backend-dev` añade el grupo `dev` para CI y equipos sin uv.
- Versiones exactas de `python`, `node` y `uv` en los `ARG` del Dockerfile; al subirlas, versión con ≥ 2 semanas.
- Librerías nativas: `libmariadb3` (MariaDB) y `graphviz`; SQL Server con `pymssql` sin ODBC. Variantes por
  `build-arg`: `WITH_HSQLDB=true` (JRE + `jaydebeapi`), `WITH_ODBC=true` (`msodbcsql18` + `pyodbc`).
- Runtime: usuario `app` (uid 10001), `read_only`, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`,
  `HEALTHCHECK` contra `/api/health`, `CMD` en forma exec.
- Volúmenes con nombre: `data` (`config.db`) y `workspace` (salidas). Nunca sobre NFS/CIFS (bloqueo de SQLite).
- Secretos solo como Docker secrets (`ubw_app_secret_key`, `ubw_fernet_keys`), generados con
  `scripts/generate_secrets.py`; `secrets/` está git-ignored.
- `entrypoint.sh` aplica `alembic upgrade head` antes del proceso.
