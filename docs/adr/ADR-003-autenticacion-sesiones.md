# ADR-003 — Autenticación por sesión en cookie con CSRF

- **Estado**: Aceptado (implementación en Fase 1)
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
