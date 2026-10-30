# Despliegue

Referencia de producción. Para instalar paso a paso (local y servidor) empieza por
[Puesta en marcha](puesta_en_marcha.md); aquí están los detalles de cada pieza.

## Servidor interno con Docker Compose

```bash
python scripts/generate_secrets.py
docker compose up -d --build
# Arranca web (API + SPA) y worker (ejecuciones). /api/health informa "worker": "ok" cuando el worker late.
```

### Primer administrador

No hay credenciales por defecto. Tras el primer arranque, crea el administrador con el CLI (pide la contraseña dos
veces, mínimo 12 caracteres):

```bash
docker compose exec web python -m app.cli create-admin --username admin --display-name "Administración"
```

Para automatizarlo, `--password-stdin` lee la contraseña de la entrada estándar
(`printf '%s\n' "$PASS" | docker compose exec -T web python -m app.cli create-admin --username admin --password-stdin`).
El resto de usuarios se gestiona desde **Administración → Usuarios** ([guía](usuarios_y_sesiones.md)).

### Usuarios de BD para las conexiones

El explorador y el SQL libre solo leen, y el SQL libre se ejecuta en una transacción de solo lectura, pero la
protección más fuerte es que las conexiones usen un **usuario de BD con solo permisos de lectura** (`SELECT` y acceso
al catálogo). Es imprescindible en **SQL Server**, que no tiene transacciones de solo lectura. Reserva los usuarios con
escritura para las conexiones sin «Solo lectura» de las fases de migración, volcado y carga. Para aplicar
migraciones DDL, ese usuario necesita permisos de `CREATE` (tablas, índices, vistas, secuencias y triggers) en el
schema destino, y el usuario de la web, el permiso «Puede aplicar DDL» ([guía](migracion.md)). Para volcar datos
([guía](volcado.md)) el usuario de BD destino necesita `INSERT` (y `DELETE`/`TRUNCATE` si se vacía) y, para que
util_bbdd desactive y reactive constraints e índices, `ALTER` sobre esas tablas. Para la carga bulk
([guía](carga.md)), `INSERT`, `UPDATE` o `DELETE` sobre la tabla destino según la operación.

### Destinos y ficheros de las conexiones

- **Allowlist**: ninguna conexión de red funciona hasta que un admin añade sus destinos en *Administración →
  Destinos permitidos* (red CIDR, host o `*.dominio`). Las IP de metadatos cloud se bloquean siempre; loopback solo
  con una red explícita (`127.0.0.1/32`). Para alcanzar una BD del propio equipo con Docker Desktop, usa el host
  `host.docker.internal` y añádelo a la lista.
- **Ficheros** (SQLite, JAR de HSQLDB, certificados TLS): deben estar en `UBW_FILES_DIR` (`/data/files`, en el
  volumen `data`). Para copiarlos: `docker compose cp ./ventas.db web:/data/files/ventas.db` y, en la conexión,
  `database = ventas.db`.

### Oracle en modo thick (Instant Client)

Por defecto Oracle usa el modo **thin** de `oracledb`, que no necesita cliente y conecta con Oracle 12.1 o posterior.
El modo **thick** solo hace falta para Oracle 11g o para funciones que thin no tiene (p. ej. Native Network
Encryption). Necesita el Oracle Instant Client, que la imagen no incluye (licencia de Oracle): lo copia el admin a
`UBW_FILES_DIR`, y `oracle_client_path` es la carpeta **relativa** a `UBW_FILES_DIR`. Una ruta absoluta fuera de ella
(`C:\oracle\…`, `/opt/oracle/…`) se rechaza con «debe ser una ruta dentro de la carpeta de ficheros del servidor».

Verificado con el Instant Client 19.32 (Linux x86_64) y `oracledb` 26.0.1. Todos los comandos se ejecutan desde la
raíz del proyecto (donde está `docker-compose.yml`; si no, `no configuration file provided`).

1. **Descarga el Instant Client *Basic* para Linux** (no el de Windows: el backend corre en Linux), de la
   arquitectura del contenedor (`docker compose exec web uname -m`: `x86_64` o `aarch64`). La versión depende de la
   BD: 19 conecta con 11.2 o posterior; 21, con 12.1 o posterior; 23, con 19 o posterior. Para Oracle 11g, el 19.

2. **Descomprímelo en el volumen `data`** con un contenedor de usar y tirar. `unzip` conserva los enlaces simbólicos
   (`libclntsh.so` → `libclntsh.so.19.1`), que el Explorador de Windows rompe, y el `chown` deja la carpeta a nombre
   del usuario `app` (uid 10001). El volumen se llama `<proyecto>_data` (`docker volume ls`):

    ```bash
    docker run --rm -v util_bbdd_web_data:/data -v "$PWD:/in:ro" python:3.12.14-slim-bookworm sh -c \
      'apt-get update -qq && apt-get install -y -qq unzip && unzip -q /in/instantclient-basic-linux.x64-19.32.0.0.0dbru.zip -d /data/files && chown -R 10001:10001 /data/files/instantclient_19_32'
    ```

    En PowerShell, `${PWD}` en lugar de `$PWD` y todo en una línea; en Git Bash, `MSYS_NO_PATHCONV=1` delante.
    Con `docker compose cp` también se copia, pero la carpeta queda de root y, con `cap_drop: ALL`, no se puede
    borrar después desde el contenedor.

3. **Imagen con `libaio1` y la carpeta en el entorno**, en `.env`:

    ```bash
    WITH_ORACLE_THICK=true
    UBW_ORACLE_CLIENT_DIR=instantclient_19_32    # relativa a UBW_FILES_DIR
    ```

    ```bash
    docker compose build
    docker compose up -d
    ```

    El Instant Client 19 no lleva RUNPATH `$ORIGIN`: `libclntsh.so` se encuentra por `oracle_client_path`, pero sus
    dependencias (`libnnz19.so`) solo por `LD_LIBRARY_PATH`, que tiene que existir al arrancar el proceso. El
    *entrypoint* la monta con `UBW_ORACLE_CLIENT_DIR`; las pruebas de conexión y los jobs la heredan.

4. **Comprueba que carga** antes de tocar la conexión. `docker compose exec` no pasa por el *entrypoint*, así que la
   prueba toma `LD_LIBRARY_PATH` del proceso de la aplicación (PID 1):

    ```bash
    docker compose exec web sh -c 'L=$(tr "\0" "\n" </proc/1/environ | grep ^LD_LIBRARY_PATH= | cut -d= -f2-); echo "$L"; LD_LIBRARY_PATH="$L" python -c "import oracledb; oracledb.init_oracle_client(lib_dir=\"/data/files/instantclient_19_32\"); print(oracledb.clientversion())"'
    ```

    Debe imprimir `/data/files/instantclient_19_32` y `(19, 32, 0, 0, 0)`. Repite con `worker` en lugar de `web`.

5. **En la conexión Oracle**: `oracle_client_path = instantclient_19_32` (sin `/data/files/`, la misma carpeta que
   `UBW_ORACLE_CLIENT_DIR`) y activa `oracle_thick_mode`. Guarda y pulsa *Probar conexión*.

**Cambiar de versión**: descomprime la nueva (paso 2), cambia `UBW_ORACLE_CLIENT_DIR` y `docker compose up -d`, y
actualiza `oracle_client_path` en las conexiones. Para borrar la antigua:
`docker compose exec web rm -rf /data/files/instantclient_19_32`. Si se copió con `docker compose cp` (de root),
primero `docker compose exec -u root web find /data/files/<carpeta> -mindepth 1 -delete` y después
`docker compose exec web rmdir /data/files/<carpeta>`.

El modo thick se inicializa una vez por proceso y no se puede volver a thin. La web abre cada prueba de conexión y cada
ejecución en un subproceso propio (ADR-002), así que las conexiones thin y thick conviven sin problema. Como
`LD_LIBRARY_PATH` es una sola, hay **un Instant Client por despliegue**: todas las conexiones thick usan el mismo.

## Detrás de un proxy inverso con TLS

Por defecto el puerto se publica solo en `127.0.0.1:8080`. Para acceso desde la red, pon delante un **proxy
inverso con TLS** (nginx, Caddy, Traefik) y no expongas el contenedor directamente. Con TLS la aplicación usa cookies
`__Host-ubw_session` y `__Host-ubw_csrf` (`Secure`, `Path=/`, sin `Domain`) y envía HSTS; sin HTTPS el navegador no
las guarda (salvo en `localhost`).

### nginx

```nginx
server {
    listen 443 ssl;
    server_name util-bbdd.example.internal;
    # ssl_certificate / ssl_certificate_key …
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;  # mismo id en los logs del proxy y de la aplicación
        proxy_buffering off;                        # SSE de progreso (Fase 3)
        client_max_body_size 51m;                   # carga: «Tamaño máximo de un fichero» + margen (1025m para 1 GB)
        proxy_request_buffering off;                # la subida pasa a la aplicación sin copiarse antes en el proxy
        proxy_read_timeout 600s;                    # comprobar un fichero grande tras recibirlo lleva su tiempo
    }
    location = /metrics {
        allow 10.0.0.0/8;                           # solo el Prometheus de la red interna
        deny all;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

### Caddy

```caddyfile
util-bbdd.example.internal {
    request_body {
        max_size 51MB   # carga: «Tamaño máximo de un fichero» + margen (1025MB para 1 GB)
    }
    @metrics path /metrics
    handle @metrics {
        @outside not remote_ip 10.0.0.0/8
        respond @outside 403
        reverse_proxy 127.0.0.1:8080
    }
    reverse_proxy 127.0.0.1:8080 {
        flush_interval -1   # SSE sin búfer
    }
}
```

### IP real del cliente

uvicorn solo atiende `X-Forwarded-For`/`X-Forwarded-Proto` de las IP de `FORWARDED_ALLOW_IPS` (en el compose,
`UBW_FORWARDED_ALLOW_IPS`, `127.0.0.1` por defecto). Con el proxy en el mismo equipo y el puerto publicado por
Docker, las peticiones llegan desde la pasarela de la red de Docker: indica su IP o red
(`UBW_FORWARDED_ALLOW_IPS=172.16.0.0/12`). Sin eso, el rate limiting por IP y la auditoría ven la IP del proxy para
todos los usuarios y HSTS no se envía.

Si subes el tamaño máximo de un fichero de carga, sube también el límite de cuerpo del proxy (nginx responde 413
antes de llegar a la aplicación). Los ficheros subidos se guardan en el volumen del workspace y cuentan para la cuota
del usuario. Para ficheros de cientos de MB, ver [Ficheros grandes en la carga](#ficheros-grandes-en-la-carga).

### Ficheros grandes en la carga

Los límites de la carga se cambian sin reiniciar en *Administración → Almacenamiento → Carga de ficheros* (ADR-012):
tamaño máximo de un fichero (`UBW_UPLOAD_MAX_MB`, 50 MB por defecto, hasta 2048), tamaño descomprimido de un Excel
(`UBW_UPLOAD_MAX_UNCOMPRESSED_MB`, 300) y filas máximas (`UBW_BULK_MAX_ROWS`, 1 000 000). Las variables son el valor
por defecto. Para subir CSV de, por ejemplo, 1 GB:

- **Proxy**: `client_max_body_size 1025m` (y `proxy_request_buffering off`) en nginx o `max_size 1025MB` en Caddy, y
  tiempos de espera holgados. Una subida de 1 GB tarda minutos por una red lenta.
- **Disco**: el multipart se recibe en un temporal del volumen workspace (`TMPDIR=<workspace>/.tmp`, que crea el
  *entrypoint*; `/tmp` es un `tmpfs` en memoria) y después se copia a `uploads/`. Durante la subida el fichero ocupa
  el doble. Fuera de Docker, apunta `TMPDIR` a un disco con espacio. Sube también la cuota del usuario.
- **Memoria**: un CSV se lee y se carga por bloques de 50 000 filas, sin tenerlo entero en memoria. Un **Excel** y una
  carga con **plan paralelo** sí se leen enteros: la vista previa avisa si se pide el plan paralelo con un fichero de
  más de 200 MB. Para ficheros grandes, CSV y sin plan paralelo.
- **Tiempo**: la vista previa recorre el fichero entero (filas y coincidencias por clave primaria) y la carga lo
  vuelve a leer. Si una carga puede pasar de una hora, sube `UBW_JOB_TIMEOUT_SECONDS`.
- **Destino**: sin plan paralelo la carga va en **una sola transacción**. Con millones de filas el motor necesita
  espacio de deshacer y de log (undo/redo de Oracle, log de transacciones de SQL Server, WAL de PostgreSQL); si no lo
  tiene, parte el fichero.

## Cabeceras y rate limiting

La aplicación pone CSP (`script-src 'self'`), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`,
COOP/CORP y `Cache-Control: no-store` en `/api`; el proxy no necesita añadirlas (si lo hace, que no las duplique con
otros valores). Revisión de seguridad: [ASVS L2](../security/ASVS_L2.md).

Límites en memoria del proceso `web` (429 con `Retry-After`):

| Variable | Por defecto | Qué limita |
|---|---|---|
| `UBW_RATE_LIMIT_API_PER_MINUTE` | 600 | Peticiones a `/api` por sesión |
| `UBW_RATE_LIMIT_ANONYMOUS_PER_MINUTE` | 300 | Peticiones a `/api` sin sesión, por IP |
| `UBW_RATE_LIMIT_LOGIN_PER_MINUTE` | 30 | Intentos de inicio de sesión por IP |
| `UBW_RATE_LIMIT_LOGIN_FAILURES` | 10 | Inicios de sesión fallidos por IP en 15 min (además del bloqueo por cuenta) |
| `UBW_RATE_LIMIT_UPLOADS_PER_HOUR` | 60 | Subidas por sesión |
| `UBW_RATE_LIMIT_ENABLED` | `true` | Desactivarlo solo si el proxy ya limita |

Las tres primeras de login y anónimas se pueden fijar en el entorno de `docker compose`; el resto, añadiéndolas a
`environment` en `docker-compose.yml`. Los contadores se reinician al reiniciar `web` y, con varios procesos de la
API, cada uno lleva su cuenta.

## Logs y métricas

- **Logs**: una línea JSON por evento en la salida estándar (`docker compose logs web worker`). Cada petición a `/api`
  escribe `app.access` con método, ruta plantilla (`/api/v1/runs/{run_id}`), estado, milisegundos y `request_id`; el
  mismo `request_id` va en la cabecera `X-Request-ID` y en los errores (la SPA lo muestra como «Referencia»). Si el
  proxy envía `X-Request-ID` válido (8–64 caracteres `A-Za-z0-9._-`), se reutiliza.
- **Métricas Prometheus** en `GET /metrics`, desactivadas por defecto. Para activarlas, descomenta el secret
  `ubw_metrics_token` en `docker-compose.yml` (lo crea `scripts/generate_secrets.py` en `secrets/metrics_token.txt`)
  y configura el *scrape* con `authorization: { credentials_file: … }`. Series: `ubw_http_requests_total` y
  `ubw_http_request_duration_seconds` por método, ruta plantilla y estado; `ubw_rate_limited_total` por regla;
  `ubw_runs` por estado y operación; `ubw_worker_heartbeat_age_seconds`; `ubw_info` con las versiones. No llevan
  usuarios, proyectos ni identificadores.

## Variantes de imagen

| Variante | Comando | Tamaño (1.0.0) |
|---|---|---|
| Base | `docker compose build` | ≈ 770 MB |
| Con HSQLDB (JRE + jaydebeapi) y/o ODBC para SQL Server (msodbcsql18 + `pyodbc`) | `WITH_HSQLDB=true WITH_ODBC=true docker compose build` | ≈ 1,06 GB con las dos |
| Con Oracle thick (`libaio1`; el Instant Client va aparte, [ver arriba](#oracle-en-modo-thick-instant-client)) | `WITH_ORACLE_THICK=true docker compose build` | Sin medir (solo añade `libaio1`) |

Verificado en la 1.0.0 contra el bench: HSQLDB 2.7.4 por JDBC (el JAR del driver va en `UBW_FILES_DIR`, parámetro
`jdbc_jar`) y SQL Server 2022 con `sql_server_driver = pyodbc` y `driver_name = ODBC Driver 18 for SQL Server`.

## Copias de seguridad

```bash
# En caliente: instantánea consistente de config.db (API backup de sqlite3), workspace y UBW_FILES_DIR.
docker compose exec web python -m app.cli backup              # → /data/backups/ubw-backup-<UTC>/
docker compose cp web:/data/backups/ubw-backup-<UTC> ./copias/
docker compose exec web python -m app.cli verify-backup --from /data/backups/ubw-backup-<UTC>
```

Cada copia tiene `config.db`, `workspace.tar.gz`, `files.tar.gz` y `manifest.json` (versión, revisión de Alembic y
SHA-256 de cada fichero). Las ejecuciones en curso pueden quedar incompletas en el tar del workspace. Borra las copias
antiguas de `/data/backups` (ocupan el volumen `data`).

**Los secretos no van en la copia**: guarda aparte `secrets/fernet_keys.txt` y `secrets/app_secret_key.txt` (y
`metrics_token.txt`). Sin la clave Fernet con la que se cifraron, las contraseñas de las conexiones restauradas no se
pueden descifrar.

Restaurar, con la aplicación parada:

```bash
docker compose stop
docker compose run --rm --no-deps -v "$PWD/copias:/restore:ro" web \
    python -m app.cli restore --from /restore/ubw-backup-<UTC> --force
docker compose up -d        # aplica las migraciones pendientes si la copia es de una versión anterior
```

`restore` valida el manifiesto y los `tar` antes de tocar nada, guarda la `config.db` actual como
`config.db.pre-restore-<UTC>`, se niega si hay un worker latiendo y rechaza copias de una versión más nueva.

## Prueba de carga

`scripts/load_test.py` (httpx, sin dependencias nuevas) simula N usuarios con sesión propia que navegan y lanzan
`noop`. Resultado en la 1.0.0 (Docker Desktop en un portátil, cliente en el mismo equipo, 20 usuarios, 60 s):

| Escenario | Peticiones/s | p95 peor lectura | Errores 5xx |
|---|---|---|---|
| Solo lecturas (`--launch-ratio 0`) | 82 | 104 ms (proyectos) | 0 |
| Con ~85 lanzamientos de `noop` por minuto (por defecto) | 78 | 591 ms (historial del proyecto) | 0 |

Con lanzamientos continuos cada job es un subproceso Python (ADR-002) que compite por la CPU con la API; es un
escenario de estrés, no de uso normal. Repite la prueba en el servidor real antes de dimensionarlo.

```bash
cd backend && uv run --frozen python ../scripts/load_test.py --base https://util-bbdd.example.internal \
    --user carga --users 20 --duration 60 < contraseña.txt
```

## Actualizar

```bash
git fetch --tags && git checkout vX.Y.Z   # una versión etiquetada; UBW_TAG=X.Y.Z en .env
docker compose build        # descarga util_bbdd de su release de GitHub (hash fijado en uv.lock)
docker compose up -d        # entrypoint aplica alembic upgrade head
```

Publicar la versión y desplegarla paso a paso: [Publicar una versión](publicar_version.md).

Antes, haz una copia (`app.cli backup`). Rollback: volver a la imagen anterior y restaurar la copia (o, si solo hubo
migraciones, `docker compose run --rm web alembic downgrade <rev>` antes de arrancarla).

**De 0.x a 1.0.0**: las cookies pasan a llamarse `__Host-ubw_session`/`__Host-ubw_csrf`, así que todos los usuarios
vuelven a iniciar sesión; las contraseñas nuevas o cambiadas se comprueban contra la lista de contraseñas comunes; el
build ya no usa `vendor/` y necesita acceso a `github.com` (además de PyPI).
