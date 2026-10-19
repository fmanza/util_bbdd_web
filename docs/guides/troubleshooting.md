# Solución de problemas

## Errores y diagnóstico

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker compose up` falla con `secret … not found` | No existen `secrets/*.txt` | `python scripts/generate_secrets.py` |
| `/api/health` → `"status": "degraded"`, `"database": "error"` | Volumen `data` no escribible o NFS/CIFS | Usar volumen con nombre local; comprobar permisos del uid 10001 |
| `database is locked` en logs | Escritura larga en SQLite | Transacciones cortas; `busy_timeout` ya es 5 s; revisar jobs que escriben progreso fila a fila |
| `npm install` falla con `ERESOLVE` y TypeScript | TypeScript 6/7 no soportado por openapi-typescript / typescript-eslint | Mantener `typescript` 5.9 (ADR-001) |
| `uv lock` falla por `exclude-newer` | Una dependencia exige una versión más nueva que el corte | Excepción justificada en `exclude-newer-package` (ver asyncpg) |
| Build de la imagen falla compilando `mariadb` | Falta `libmariadb-dev` en la etapa de build | Ya incluido en `backend-build`; en CI o local, instalar `libmariadb-dev` |
| SQL Server con `pyodbc` falla al conectar | Imagen sin ODBC | `WITH_ODBC=true docker compose build` o usar `pymssql` (por defecto) |
| HSQLDB no disponible | Imagen sin JRE | `WITH_HSQLDB=true docker compose build` |
| `/api/docs` da 404 | Desactivado en producción | `UBW_ENVIRONMENT=development` (compose dev) |
| Aviso `StarletteDeprecationWarning … httpx2` en pytest | Starlette 1.x depreca `httpx` en `TestClient` | Informativo; seguimiento en la deuda técnica |

## Logs

- API y worker escriben una línea JSON por evento: `docker compose logs -f web worker`.
- Cada ejecución (Fase 3) tiene su `logs/run.log` dentro de su carpeta del workspace.
