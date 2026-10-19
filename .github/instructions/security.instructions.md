---
applyTo: "backend/**,frontend/src/**,docker/**,docker-compose*.yml"
---
# Seguridad — reglas obligatorias

## Identidad (Fase 1, ADR-003)
- Contraseñas con Argon2id (`pwdlib`); política mínima de longitud; bloqueo temporal tras intentos fallidos.
- Sesión de servidor (tabla `sessions`) en cookie `HttpOnly; Secure; SameSite=Lax; Path=/`; rotación al iniciar
  sesión; caducidad por inactividad y absoluta; revocación por el admin.
- CSRF: token de doble envío (cookie legible + cabecera `X-CSRF-Token`) en todo método no seguro.
- Sin CORS: frontend y API comparten origen. Sin tokens en `localStorage`.
- El primer admin se crea por CLI; no existen credenciales por defecto.

## Autorización
- Cada consulta filtra por usuario o pertenencia al proyecto en el **servicio**, no solo en el router.
- Recurso ajeno → `404` (no revelar existencia).

## Secretos (ADR-004)
- Contraseñas de conexión cifradas con Fernet (MultiFernet para rotación); clave por Docker secret `ubw_fernet_keys`.
- Nunca en respuestas, logs, `run.json`, mensajes de error ni excepciones re-lanzadas: sanear con el saneador común
  y registrar solo `type(exc).__name__`.

## Conexiones salientes
- Allowlist de hosts/redes configurable por el admin (anti-SSRF); denegar por defecto rangos de metadatos cloud
  (`169.254.0.0/16`) y loopback salvo configuración explícita.
- Timeouts de conexión y consulta siempre definidos.

## Workspace y ficheros
- Rutas construidas solo con IDs; `resolve()` + `is_relative_to(raíz_del_run)` antes de servir.
- Subidas: tamaño máximo, extensión y tipo MIME permitidos, nombre regenerado; nunca se ejecutan.
- Vistas previas HTML en `iframe sandbox`; `Content-Disposition: attachment` en descargas.

## Cabeceras y transporte
- CSP estricta (`default-src 'self'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
  `X-Frame-Options: DENY` (salvo vistas previas), HSTS detrás del proxy TLS.

## Contenedor
- Usuario no root, `read_only`, `cap_drop: ALL`, `no-new-privileges`, puertos en `127.0.0.1` por defecto,
  secretos solo por Docker secrets, imágenes con versión exacta.
