# ADR-003 — Autenticación por sesión en cookie con CSRF

- **Estado**: Aceptado (implementado en la Fase 1, 0.2.0)
- **Fecha**: 2026-10-19

## Contexto

SPA y API se sirven desde el mismo origen. Se necesitan usuarios, roles y revocación inmediata (un admin debe poder
cerrar la sesión de otro).

## Decisión

- **Sesión de servidor** (tabla `sessions`, identificador aleatorio de 256 bits) en cookie
  `HttpOnly; Secure; SameSite=Lax; Path=/`, rotada al iniciar sesión, con caducidad por inactividad y absoluta.
- **CSRF** con token de doble envío (cookie no `HttpOnly` + cabecera `X-CSRF-Token`) en métodos no seguros.
- Contraseñas con **Argon2id** (`pwdlib[argon2]`); bloqueo temporal tras intentos fallidos.
- Primer admin creado por CLI; sin credenciales por defecto.
- **No JWT**: no aporta nada con un solo origen y complica la revocación; los tokens personales para CI (mejora
  opcional) serán tokens opacos almacenados con hash.

## Consecuencias

- Una consulta a `sessions` por petición (barata en SQLite con índice).
- En desarrollo sin HTTPS, `Secure` se desactiva solo con `UBW_ENVIRONMENT=development`.

## Notas de implementación (Fase 1)

- En `sessions` se guarda el **SHA-256 del token**, no el token: una copia de `config.db` no permite suplantar
  sesiones.
- CSRF de **doble envío firmado**: con sesión, el token es `HMAC-SHA256(ubw_app_secret_key, token_de_sesión)`, lo que
  anula la inyección de cookies desde subdominios. Antes del login, `GET /api/v1/auth/csrf` entrega un token
  aleatorio (protege el propio login).
- Login con un único error genérico (usuario inexistente, desactivado, bloqueado o contraseña mala) y verificación
  contra un hash ficticio para igualar tiempos.
- `last_seen_at` se actualiza como mucho una vez por minuto (SQLite tiene un único escritor).
- Cambiar la contraseña cierra las demás sesiones del usuario; desactivar o restablecer la contraseña cierra todas.
- Debe quedar siempre un admin activo (`409`); un admin no puede desactivarse ni quitarse el rol.
- Pendiente para la Fase 10: prefijo `__Host-` en las cookies y *rate limiting* por IP del login.
