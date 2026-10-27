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
        client_max_body_size 51m;                   # subidas de la carga bulk: UBW_UPLOAD_MAX_MB + margen (Fase 9)
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
        max_size 51MB
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

Si subes `UBW_UPLOAD_MAX_MB`, sube también el límite de cuerpo del proxy (nginx responde 413 antes de llegar a la
aplicación). Los ficheros subidos se guardan en el volumen del workspace y cuentan para la cuota del usuario.

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
