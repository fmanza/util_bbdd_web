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
| El contenedor `web` no arranca: `MissingSecretKeyError` | Producción sin `ubw_app_secret_key` | `python scripts/generate_secrets.py` y comprobar `secrets:` en compose |
| El login no persiste (vuelve a `/login`) | Cookie `Secure` sobre HTTP en un host que no es `localhost`/`127.0.0.1` | Acceder por el proxy TLS; solo en desarrollo `UBW_ENVIRONMENT=development` quita `Secure` |
| «Token CSRF ausente o no válido» (403) | Cookie `ubw_csrf` borrada o de otra sesión | Recargar la página; el login pide un token nuevo con `GET /api/v1/auth/csrf` |
| Un usuario no puede entrar con la contraseña correcta | Bloqueo temporal tras 5 fallos (`UBW_LOGIN_*`) | Esperar el bloqueo, o que un admin le restablezca la contraseña (quita el bloqueo) |
| Se ha perdido la contraseña del único admin | — | `docker compose exec web python -m app.cli create-admin --username otro-admin` y reactivar o restablecer desde la web |
| Prueba de conexión: «El destino no está en la lista de destinos permitidos» | Allowlist vacía o sin ese host | Un admin añade el host o la red en *Destinos permitidos* |
| Prueba de conexión: «El driver del motor no está instalado» | Imagen sin el driver (p. ej. HSQLDB o `pyodbc`) | Ver la ficha del motor; imagen `WITH_HSQLDB=true` o `WITH_ODBC=true` |
| «No se puede descifrar la contraseña guardada» | Se retiró una clave de `fernet_keys.txt` sin `rotate-secrets` | Restaurar la clave antigua, ejecutar `rotate-secrets` y retirarla después; o reintroducir la contraseña |
| La API no arranca: `UBW_FERNET_KEYS … obligatoria` | Producción sin el secret `ubw_fernet_keys` | `python scripts/generate_secrets.py` |
| Desde Docker no conecta con una BD en `127.0.0.1` del host | Dentro del contenedor, `127.0.0.1` es el propio contenedor | Usar `host.docker.internal` (Docker Desktop) o la IP del host, y añadirlo a la allowlist |
| Las ejecuciones se quedan «En cola» | No hay worker (`/api/health` → `"worker": "absent"` o `"stale"`) | `docker compose up -d worker` y `docker compose logs worker` |
| Ejecución «Fallida» con `interrupted` | El worker se reinició con el job en curso | Relanzar la ejecución |
| Ejecución «Fallida» con `job_timeout` | Superó `UBW_JOB_TIMEOUT_SECONDS` | Subir el límite o dividir el trabajo |
| Lanzar ejecución → 409 «Cuota de almacenamiento superada» | El usuario supera su cuota (la global de *Administración → Almacenamiento* o la suya) | Purgar ejecuciones antiguas, subir la cuota o activar la purga por cuota; el usuario ve su uso en *Mi espacio* |
| Lanzar ejecución → 429 | Más de `UBW_MAX_QUEUED_PER_USER` en cola o en curso | Esperar o cancelar alguna |
| El progreso no se actualiza en vivo | Un proxy almacena la respuesta SSE | `proxy_buffering off` en nginx (ver despliegue); la UI cae a sondeo cada 2 s |
| Explorador: 502 «No se pudo consultar la base de datos» | Conexión no permitida, caída o credenciales | El código (`not_allowed`, `connection_failed`…) indica la causa; prueba la conexión |
| Documentación: el sitio HTML da 404 tras un rato | Su enlace firmado caducó (inactividad de la sesión) | Recarga el detalle de la ejecución |
| Comparación: «El schema «x» no existe en el origen/destino» | Nombre mal escrito o de otro motor (en MySQL es la base de datos) | Copia el nombre del explorador |
| Volcado: `dump_partial` | Una tabla falló o una constraint no se reactivó | Revisa el resultado por tabla |
| Volcado: «attempt to write a readonly database» (SQLite) | El fichero no es del usuario de la aplicación | Dale permisos de escritura al usuario `app` |
| 429 «Demasiadas peticiones» | Se superó un límite de `UBW_RATE_LIMIT_*` (por sesión, por IP sin sesión, login o subidas) | Esperar los segundos de `Retry-After`; si afecta a muchos usuarios a la vez, revisar `UBW_FORWARDED_ALLOW_IPS` (sin él todos comparten la IP del proxy) o subir el límite |
| Login: 429 aunque la contraseña sea buena | Más de `UBW_RATE_LIMIT_LOGIN_FAILURES` fallos desde esa IP en 15 min | Esperar o reiniciar `web` (los contadores son en memoria) |
| Tras actualizar a 1.0 todos tienen que volver a entrar | Las cookies pasan a `__Host-ubw_session`/`__Host-ubw_csrf` | Esperado una vez |
| No se mantiene la sesión (vuelve al login) | Acceso por HTTP sin TLS a otro host que `localhost`: el navegador no guarda cookies `Secure` | Usar el proxy TLS (o `UBW_ENVIRONMENT=development` solo en local) |
| «Esa contraseña es demasiado común» | Está en la lista de contraseñas comunes (ASVS 2.1.7) | Elegir otra, mejor una frase |
| `/metrics` da 404 / 401 | Sin secret `ubw_metrics_token` / sin `Authorization: Bearer` correcto | Ver *Logs y métricas* en el despliegue |
| `restore`: «hay un worker en marcha» | La aplicación sigue arrancada | `docker compose stop` y `docker compose run --rm --no-deps …` |
| `restore`: «… está dañado» | La copia no coincide con su `manifest.json` | Usar otra copia; no restaurar una incompleta |
| Para dar soporte, ¿qué petición falló? | — | La «Referencia» del error es el `request_id`: búscalo en `docker compose logs web` |
| Carga: 413 al subir un fichero | Supera `UBW_UPLOAD_MAX_MB` o el límite del proxy | Divide el fichero o sube ambos límites (`client_max_body_size`) |
| Carga: 415/422 al subir | Extensión distinta de `.csv`/`.xlsx`, contenido que no corresponde o Excel con macros | Guarda el fichero como CSV o `.xlsx` sin macros |
| Carga: `invalid_file` | Codificación, separador u hoja incorrectos, o más de `UBW_BULK_MAX_ROWS` filas | Fija separador y codificación en el formulario o divide el fichero |
| Carga: `preview_changed` | Cambiaron la tabla, el mapeo o las filas afectadas desde la vista previa | Repite la vista previa |
| Carga: `bulk_partial` | Falló una partición de una carga paralela; las demás quedaron confirmadas | Revisa las particiones y corrige el destino |
| Migración: 403 al aplicar | Sin «Puede aplicar DDL» o sin ser propietario | Un admin concede el permiso; aplica el propietario |
| Migración: «El origen ha cambiado desde el plan» | Cambió el schema origen tras planificar | Planifica de nuevo |
| Migración: no aparece *Cancelar* | Las aplicaciones en curso no se cancelan (dejarían el destino a medias) | Espera a que termine; en cola sí se cancela |
| Migración: `apply_partial` | Falló una sentencia; las anteriores quedaron aplicadas | Lee el informe y corrige el destino a mano |
| Comparación: el visor da 413 | El diff supera 20 MB | Descarga los informes |
| Ejecución fallida con `graphviz_missing` | Falta Graphviz en el servidor | Usa la imagen oficial o instala `graphviz` |
| Ejecución fallida con `graphviz_failed`, o un diagrama con «No se pudo generar el diagrama» | `dot` terminó con error en un diagrama (GAPS G39). Desde util_bbdd 4.1.0 ese diagrama queda con un aviso y el documento sigue; la imagen oficial además repite sin aristas ortogonales los diagramas que abortan Graphviz | Desmarca «Relaciones en ángulo recto» en el formulario, reduce la profundidad o desactiva los diagramas; fuera de la imagen oficial, instala `docker/dot-wrapper.sh` como `dot` |
| Explorador: el schema tarda en abrirse | Primera lectura de un schema grande | Espera (hasta `UBW_METADATA_TIMEOUT_SECONDS`); después va desde la caché |
| Una tabla nueva no aparece | El árbol viene de la caché | **Refrescar** |
| SQL libre: 403 | Sin permiso «Puede ejecutar SQL libre» o sin rol editor | Un admin activa el permiso en *Usuarios* |
| SQL libre: 409 | La conexión no es «Solo lectura» | Marca la conexión como solo lectura |
| SQL libre: 422 «Solo se admiten consultas SELECT» | La consulta escribe o tiene varias sentencias | Una única consulta de lectura |
| Oracle: ORA-01466 en SQL libre | Tabla creada hace unos segundos (transacción de solo lectura) | Reintentar pasados unos segundos |
| `/api/docs` da 404 | Desactivado en producción | `UBW_ENVIRONMENT=development` (compose dev) |
| Aviso `StarletteDeprecationWarning … httpx2` en pytest | Starlette 1.x depreca `httpx` en `TestClient` | Informativo; seguimiento en la deuda técnica |

## Logs

- API y worker escriben una línea JSON por evento: `docker compose logs -f web worker`.
- Cada ejecución (Fase 3) tiene su `logs/run.log` dentro de su carpeta del workspace.
