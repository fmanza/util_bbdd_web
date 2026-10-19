# syntax=docker/dockerfile:1
# util_bbdd_web — imagen única para API (target "runtime") y worker (mismo target, otro comando).
# Build:  docker compose build            (o docker build -f docker/Dockerfile .)
# Variantes: --build-arg WITH_HSQLDB=true  (JRE + jaydebeapi)  |  --build-arg WITH_ODBC=true (msodbcsql18 + pyodbc)

ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm
ARG NODE_IMAGE=node:24.21.0-alpine
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.22

FROM ${UV_IMAGE} AS uv

# ---------- 1. Frontend ----------
FROM ${NODE_IMAGE} AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Dependencias Python ----------
FROM ${PYTHON_IMAGE} AS backend-build
ARG WITH_HSQLDB=false
ARG WITH_ODBC=false
COPY --from=uv /uv /bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev libmariadb-dev pkg-config \
 && if [ "$WITH_ODBC" = "true" ]; then apt-get install -y --no-install-recommends unixodbc-dev; fi \
 && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src/backend
COPY vendor/ /src/vendor/
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    EXTRAS=""; \
    if [ "$WITH_HSQLDB" = "true" ]; then EXTRAS="$EXTRAS --extra hsqldb"; fi; \
    if [ "$WITH_ODBC" = "true" ]; then EXTRAS="$EXTRAS --extra odbc"; fi; \
    uv sync --frozen --no-dev $EXTRAS

# ---------- 2b. Herramientas de desarrollo (CI y equipos sin uv local) ----------
# docker build -f docker/Dockerfile --target backend-dev -t util_bbdd_web:backend-dev .
# docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" util_bbdd_web:backend-dev uv run --frozen pytest
FROM backend-build AS backend-dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen
ENV PATH=/opt/venv/bin:$PATH
CMD ["uv", "run", "--frozen", "pytest"]

# ---------- 3. Runtime ----------
FROM ${PYTHON_IMAGE} AS runtime
ARG WITH_HSQLDB=false
ARG WITH_ODBC=false
RUN apt-get update \
 && apt-get install -y --no-install-recommends libmariadb3 graphviz \
 && if [ "$WITH_HSQLDB" = "true" ]; then apt-get install -y --no-install-recommends default-jre-headless; fi \
 && if [ "$WITH_ODBC" = "true" ]; then \
      apt-get install -y --no-install-recommends curl gnupg unixodbc \
      && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
      && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
      && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
      && apt-get purge -y curl gnupg; \
    fi \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /data /workspace \
 && chown app:app /data /workspace

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UBW_ENVIRONMENT=production \
    UBW_DATA_DIR=/data \
    UBW_WORKSPACE_DIR=/workspace \
    UBW_STATIC_DIR=/app/static

WORKDIR /app
COPY --from=backend-build /opt/venv /opt/venv
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app backend/alembic.ini ./alembic.ini
COPY --chown=app:app --from=frontend-build /fe/dist ./static
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

USER app
EXPOSE 8080
VOLUME ["/data", "/workspace"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import json,urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4); sys.exit(0 if json.load(r)['status']=='ok' else 1)"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header"]
