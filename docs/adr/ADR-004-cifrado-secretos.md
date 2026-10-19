# ADR-004 — Cifrado de secretos de conexión

- **Estado**: Aceptado (implementación en Fase 2)
- **Fecha**: 2026-10-19

## Decisión

- Las contraseñas (y cualquier parámetro sensible) de las conexiones se guardan en `connections.secret_enc` cifradas
  con **Fernet** (`cryptography`), separadas de `params` (JSON sin secretos).
- Claves en el Docker secret `ubw_fernet_keys` (fichero `secrets/fernet_keys.txt`), separadas por comas:
  **MultiFernet**, la primera cifra y todas descifran. Rotación: anteponer una clave nueva, ejecutar
  `python -m app.cli rotate-secrets` (re-cifra) y retirar la antigua.
- El secreto se descifra solo en el proceso que conecta (worker o prueba de conexión), nunca se devuelve por la API
  y se elimina de cualquier `dict` antes de registrar o persistir (`run.json`).
- Mensajes de excepción de drivers saneados: se registra el tipo de excepción, no el mensaje.

## Consecuencias

- Perder `fernet_keys.txt` obliga a reintroducir las contraseñas: se incluye en la guía de backup.
