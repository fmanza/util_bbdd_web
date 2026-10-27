# Publicar una versión

Pasos para publicar una versión de util_bbdd_web y desplegarla, desde que el desarrollo está terminado en `develop`:
subir util_bbdd si toca, comprobar, subir la versión, avanzar `main`, crear el tag y actualizar el servidor. Todos los
comandos son para **Git Bash** (Windows) en el equipo de desarrollo y para `bash` en el servidor Linux.

La distribución es el **tag**: el servidor hace `git checkout vX.Y.Z` y construye la imagen con
`docker compose up -d --build`. No se publican imágenes ni paquetes; util_bbdd llega como el wheel de su release de
GitHub, con el hash fijado en `backend/uv.lock` ([ADR-006](../adr/ADR-006-integracion-util-bbdd.md)).

## 1. Qué se publica

| Pieza | Dónde | Cómo |
|---|---|---|
| Commit `release: vX.Y.Z - <resumen>` | `develop` y `main` | Paso 5 (`main` avanza por fast-forward) |
| Tag anotado `vX.Y.Z` | GitHub | Paso 6 |
| Release de GitHub con las notas del CHANGELOG (opcional, sin ficheros) | GitHub Releases | Paso 6 |
| Imagen `util_bbdd_web:X.Y.Z` | Cada servidor | Paso 8 (`UBW_TAG` en `.env`) |

Ramas: solo `main` (lo publicado) y `develop` (integración); ver [Ramas y Dependabot](#10-ramas-y-dependabot).

## 2. Orden cuando cambian los dos repositorios

Si la versión necesita una util_bbdd nueva, va primero la librería:

| # | Repositorio | Paso | Guía |
|---|---|---|---|
| 1 | util_bbdd | Release `vA.B.C` con el wheel y su `.sha256` | [Publicar una versión (util_bbdd)](https://github.com/fmanza/util_bbdd/blob/develop/docs/guides/release_guide.md) |
| 2 | util_bbdd_web | Subir util_bbdd a `A.B.C` (W-x.0) | [Paso 3](#3-subir-util_bbdd-si-toca) |
| 3 | util_bbdd_web | Desarrollo que usa la versión nueva, en `develop` | — |
| 4 | util_bbdd_web | Comprobar, versión, `main` y tag | Pasos 4 a 7 |
| 5 | Servidor | Copia, `checkout` del tag y reconstruir | [Paso 8](#8-desplegar-en-el-servidor) |

Si solo cambia la web, empieza en el paso 4.

Variables que usan los pasos (cámbialas en cada versión):

```bash
cd /c/Desarrollo/<ruta>/util_bbdd_web
OLD=1.5.0      # versión publicada anterior
NEW=1.6.0      # versión que se publica (SemVer: MAJOR si exige intervención al actualizar o rompe la API)
UBB=4.6.0      # versión de util_bbdd que se fija (solo para el paso 3)
git switch develop
git pull --ff-only origin develop
git status                                   # «nothing to commit, working tree clean»
```

## 3. Subir util_bbdd (si toca)

Antes, la release `vA.B.C` de util_bbdd debe tener el wheel y su `.sha256`. Usa la **misma versión de uv que la
imagen** (`UV_IMAGE` en `docker/Dockerfile`, hoy 0.12.22): otra versión cambia el formato de `uv.lock`.

```bash
grep -n "UV_IMAGE=" docker/Dockerfile
uv --version

# En backend/pyproject.toml: la dependencia util_bbdd[...]==A.B.C y la URL del wheel en [tool.uv.sources]
CUR=$(grep -o 'util_bbdd-[0-9.]*-py3' backend/pyproject.toml | head -1 | sed 's/util_bbdd-//; s/-py3//')
sed -i "s/==${CUR}\"/==${UBB}\"/; s|v${CUR}/util_bbdd-${CUR}-py3|v${UBB}/util_bbdd-${UBB}-py3|; s|release v${CUR}|release v${UBB}|" backend/pyproject.toml
git diff backend/pyproject.toml                  # tres líneas: comentario, dependencia y URL

cd backend
uv lock --upgrade-package util-bbdd
uv sync --frozen
uv run --frozen python -c "import importlib.metadata as m; print(m.version('util_bbdd'))"   # A.B.C
cd ..
```

Si `uv lock` falla con **401**: GitHub responde 401 a la petición `HEAD` de los ficheros de una release. Ejecuta
antes `cd backend && uv sync` (descarga el wheel con `GET` y lo deja en caché) y repite `uv lock`. Comprueba el
resultado sin red con `uv lock --check --offline`.

Comprueba que el hash del lock es el de la release:

```bash
curl -sL "https://github.com/fmanza/util_bbdd/releases/download/v${UBB}/util_bbdd-${UBB}-py3-none-any.whl.sha256"
grep -o "util_bbdd-${UBB}-py3-none-any.whl\", hash = \"sha256:[0-9a-f]*" backend/uv.lock    # mismo hash
```

Busca los tests y textos que nombran la versión anterior de util_bbdd (por ejemplo, el de `/api/health`) y
actualízalos. Después, las comprobaciones del paso 4 y:

```bash
git add backend/pyproject.toml backend/uv.lock <tests y docs cambiados>
git commit -m "chore(backend): util_bbdd ${UBB}"
```

## 4. Comprobaciones

Backend (desde `backend/`):

```bash
cd backend
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen pytest
uv run --frozen python scripts/export_openapi.py --check
cd ..
```

Frontend (desde `frontend/`):

```bash
cd frontend
npm ci
npm run format:check && npm run lint && npm run typecheck && npm test && npm run build
cd ..
```

Documentación y aplicación completa, con Docker:

```bash
uv run --frozen --project backend --only-group docs zensical build --strict && rm -rf site
docker compose up -d --build
curl -s http://127.0.0.1:8080/api/health          # "status": "ok" y "worker": "ok"
cd frontend && npm run e2e && cd ..               # requisitos: Guía de desarrolladores › E2E completa
```

## 5. Commit de versión

Con Claude Code, `/version-closure` lo prepara. A mano, la versión vive en estos sitios
(`.github/instructions/sync.instructions.md`):

| Fichero | Cambio |
|---|---|
| `CHANGELOG.md` | `## [Unreleased]` → `## [X.Y.Z] - AAAA-MM-DD` |
| `backend/pyproject.toml` | `[project] version = "X.Y.Z"` |
| `backend/app/__init__.py` | `__version__ = "X.Y.Z"` |
| `frontend/package.json` y `package-lock.json` | `"version": "X.Y.Z"` |
| `backend/uv.lock` | Versión del paquete `util-bbdd-web` |
| `openapi/openapi.json` | `info.version` |
| `.env.example` | `UBW_TAG=X.Y.Z` |

```bash
sed -i "0,/^version = \"${OLD}\"/s//version = \"${NEW}\"/" backend/pyproject.toml
sed -i "s/__version__ = \"${OLD}\"/__version__ = \"${NEW}\"/" backend/app/__init__.py
sed -i "s/^UBW_TAG=.*/UBW_TAG=${NEW}/" .env.example
(cd frontend && npm version "${NEW}" --no-git-tag-version)       # package.json y package-lock.json
(cd backend && uv lock && uv lock --check --offline)              # versión de util-bbdd-web en el lock
(cd backend && uv run --frozen python scripts/export_openapi.py)  # info.version
(cd frontend && npm run gen:api && git diff --stat src/api/schema.d.ts)   # normalmente sin cambios
# CHANGELOG.md: renombra «## [Unreleased]» a «## [X.Y.Z] - AAAA-MM-DD» con tu editor

git diff --stat          # CHANGELOG, pyproject, __init__, package*.json, uv.lock, openapi.json y .env.example
git add CHANGELOG.md backend/pyproject.toml backend/app/__init__.py backend/uv.lock \
  frontend/package.json frontend/package-lock.json openapi/openapi.json .env.example
git commit -m "release: v${NEW} - <resumen>"
```

Repite las comprobaciones de backend del paso 4 (los tests de versión leen `__version__`).

## 6. Publicar

```bash
# develop y main (fast-forward; si falla, para: main tiene algo que develop no tiene)
git push origin develop
```

Espera el CI de `develop` en verde (pestaña *Actions*: `backend`, `frontend`, `docs` e `image`). Después:

```bash
git switch main
git pull --ff-only origin main
git merge --ff-only develop
git push origin main
git tag -a "v${NEW}" -m "util_bbdd_web ${NEW}"
git push origin "v${NEW}"
git switch develop
```

Release de GitHub con las notas del CHANGELOG (opcional; no lleva ficheros, la distribución es el tag):

```bash
awk -v v="${NEW}" 'index($0, "## [" v "]")==1 {f=1; next} /^## \[/ {f=0} f' CHANGELOG.md > "/tmp/notas_${NEW}.md"
gh release create "v${NEW}" --verify-tag --title "v${NEW}" --notes-file "/tmp/notas_${NEW}.md" --latest
```

Si Git Bash no encuentra `gh`: `export PATH="$PATH:/c/Program Files/GitHub CLI"`.

## 7. Comprobar

```bash
git ls-remote origin main develop "refs/tags/v${NEW}"     # main, develop y el tag en el mismo commit
```

En *Actions*, el CI de `main` también en verde.

## 8. Desplegar en el servidor

En el servidor (`/opt/util_bbdd_web` en [Puesta en marcha › En producción](puesta_en_marcha.md#4-en-producción)).
Lee antes el CHANGELOG de la versión: puede pedir pasos extra (variables nuevas, volver a iniciar sesión).

```bash
cd /opt/util_bbdd_web
NEW=1.6.0
PREV=$(git describe --tags --exact-match 2>/dev/null)     # versión desplegada ahora (para volver atrás)
echo "Desplegada: ${PREV}"

# 1. Copia de seguridad, fuera del servidor después
docker compose exec web python -m app.cli backup

# 2. Código de la versión (un tag, nunca una rama)
git fetch --tags origin
git checkout "v${NEW}"

# 3. Nombre de la imagen
sed -i "s/^UBW_TAG=.*/UBW_TAG=${NEW}/" .env
grep UBW_TAG .env

# 4. Reconstruir y arrancar (las migraciones de Alembic se aplican al arrancar)
docker compose up -d --build
curl -s http://127.0.0.1:8080/api/health    # "version": "X.Y.Z", "util_bbdd_version", "status" y "worker": "ok"
```

Después, en la aplicación, lanza una ejecución `noop` y comprueba que termina «Correcta»; los usuarios deben
recargar sin caché (Ctrl+F5).

## 9. Volver atrás

| Situación | Qué hacer |
|---|---|
| La versión nueva falla y **no** tenía migraciones de Alembic | `git checkout "${PREV}"`, `UBW_TAG` a la versión anterior en `.env` y `docker compose up -d --build` |
| Tenía migraciones | Antes de arrancar la imagen anterior: `docker compose run --rm web alembic downgrade <rev>` con la revisión de la versión anterior; o restaura la copia ([Despliegue › Copias de seguridad](deployment.md#copias-de-seguridad)) |
| El tag apunta a un commit equivocado y **no se ha desplegado** | `git push origin :refs/tags/vX.Y.Z`, `git tag -d vX.Y.Z` (y `gh release delete vX.Y.Z` si se creó) y vuelve al paso 6 |
| Ya se desplegó | No se reutiliza una versión: corrige en `develop` y publica `X.Y.Z+1` |

No uses `docker compose down -v` (borra los volúmenes) ni borres `secrets/`.

## 10. Ramas y Dependabot

Solo se mantienen `main` y `develop`. Las ramas `dependabot/*` existen solo mientras su PR está abierto.
`.github/dependabot.yml` las limita a **una por ecosistema y mes** (`uv`, `npm`, `docker`, `github-actions`):

- `schedule.interval: monthly` (también existen `quarterly`, `semiannually` y `yearly`).
- `groups` con `patterns: ["*"]`: todas las actualizaciones del ecosistema en un solo PR.
- `open-pull-requests-limit: 1`, `target-branch: develop` y `cooldown` de 14 días (solo versiones con al menos dos
  semanas, como pide la política de dependencias).

Para que la rama desaparezca al cerrar su PR, activa una vez **Settings → General → Pull Requests → Automatically
delete head branches**. Los PR de seguridad (*Dependabot security updates*, en Settings → Code security) no siguen
este calendario.

| Objetivo | Cambio en `.github/dependabot.yml` |
|---|---|
| Menos a menudo | `interval: quarterly` en cada entrada |
| Solo PR de seguridad | `open-pull-requests-limit: 0` en cada entrada |
| Ninguno | Borrar el fichero y desactivar *Dependabot security updates* |

Limpiar las ramas `dependabot/*` que queden (cierra sus PR):

```bash
git fetch --prune origin
for b in $(git branch -r --format='%(refname:lstrip=3)' | grep '^dependabot/'); do git push origin --delete "$b"; done
```
