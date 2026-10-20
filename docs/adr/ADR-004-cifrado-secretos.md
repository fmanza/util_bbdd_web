# ADR-004 — Cifrado de secretos de conexión

- **Estado**: Aceptado (implementado en la Fase 2, 0.3.0)
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

## Notas de implementación (Fase 2)

- `connections.secret_enc` guarda `{"password": …}` cifrado con `MultiFernet` (`app/domain/connections/crypto.py`);
  `params` (JSON) nunca contiene secretos: la API rechaza `password` dentro de `params` (422).
- En producción la API no arranca sin `UBW_FERNET_KEYS`; en `development`/`test` se usa una clave efímera con aviso.
- `python -m app.cli rotate-secrets` re-cifra con la clave principal; si algún secreto no se descifra, no guarda nada.
- El secreto se descifra solo para probar la conexión y viaja al subproceso por la tubería de `multiprocessing`
  (nunca argv ni entorno). El subproceso desactiva logging y salida estándar; al padre vuelve un código de error
  (`driver_missing`, `invalid_config`, `connection_failed`, `timeout`…) y el tipo de la excepción, nunca su mensaje.
- Verificado en la Fase 2: la contraseña no aparece en respuestas, logs del contenedor, auditoría ni en
  `config.db` + WAL.
