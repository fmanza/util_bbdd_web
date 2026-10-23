# Despliegue

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
(`printf '%s
' "$PASS" | docker compose exec -T web python -m app.cli create-admin --username admin --password-stdin`).
El resto de usuarios se gestiona desde **Administración → Usuarios** ([guía](usuarios_y_sesiones.md)).

### Usuarios de BD para las conexiones

El explorador y el SQL libre solo leen, y el SQL libre se ejecuta en una transacción de solo lectura, pero la
protección más fuerte es que las conexiones usen un **usuario de BD con solo permisos de lectura** (`SELECT` y acceso
al catálogo). Es imprescindible en **SQL Server**, que no tiene transacciones de solo lectura. Reserva los usuarios con
escritura para las conexiones sin «Solo lectura» de las fases de migración, volcado y carga. Para aplicar
migraciones DDL, ese usuario necesita permisos de `CREATE` (tablas, índices, vistas, secuencias y triggers) en el
schema destino, y el usuario de la web, el permiso «Puede aplicar DDL» ([guía](migracion.md)). Para volcar datos
([guía](volcado.md)) el usuario de BD destino necesita `INSERT` (y `DELETE`/`TRUNCATE` si se vacía) y, para que
util_bbdd desactive y reactive constraints e índices, `ALTER` sobre esas tablas.

### Destinos y ficheros de las conexiones

- **Allowlist**: ninguna conexión de red funciona hasta que un admin añade sus destinos en *Administración →
  Destinos permitidos* (red CIDR, host o `*.dominio`). Las IP de metadatos cloud se bloquean siempre; loopback solo
  con una red explícita (`127.0.0.1/32`). Para alcanzar una BD del propio equipo con Docker Desktop, usa el host
  `host.docker.internal` y añádelo a la lista.
- **Ficheros** (SQLite, JAR de HSQLDB, certificados TLS): deben estar en `UBW_FILES_DIR` (`/data/files`, en el
  volumen `data`). Para copiarlos: `docker compose cp ./ventas.db web:/data/files/ventas.db` y, en la conexión,
  `database = ventas.db`.

Por defecto el puerto se publica solo en `127.0.0.1:8080`. Para acceso desde la red, pon delante un **proxy
inverso con TLS** (nginx, Caddy, Traefik) y no expongas el contenedor directamente:

```nginx
server {
    listen 443 ssl;
    server_name util-bbdd.example.internal;
    # ssl_certificate / ssl_certificate_key …
    add_header Strict-Transport-Security "max-age=31536000" always;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;              # SSE de progreso (Fase 3)
    }
}
```

## Variantes de imagen

| Variante | Comando |
|---|---|
| Con HSQLDB (JRE + jaydebeapi) | `WITH_HSQLDB=true docker compose build` |
| Con ODBC para SQL Server (`pyodbc`) | `WITH_ODBC=true docker compose build` |

## Copias de seguridad

| Qué | Cómo |
|---|---|
| `config.db` | `docker compose exec web python -c "import sqlite3; s=sqlite3.connect('/data/config.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d)"` y copiar `backup.db` fuera del volumen. **No copiar solo `config.db`**: con WAL se perderían escrituras recientes |
| Workspace | Copia del volumen `workspace` |
| Secretos | `secrets/fernet_keys.txt` y `secrets/app_secret_key.txt` en un gestor seguro; sin `fernet_keys` no se pueden descifrar las conexiones |

## Actualizar

```bash
git pull
docker compose build
docker compose up -d        # entrypoint aplica alembic upgrade head
```

Rollback: volver a la imagen anterior y, si hubo migraciones, `docker compose run --rm web alembic downgrade <rev>`
antes de arrancarla (o restaurar el backup de `config.db`).
