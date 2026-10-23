# Revisión OWASP ASVS 4.0.3 — nivel 2 (release 1.0.0)

- **Fecha**: 2026-10-23 (Fase 10)
- **Alcance**: API (`backend/app`), SPA (`frontend/src`), imagen Docker y despliegue con Docker Compose tras un proxy
  TLS. util_bbdd se trata como dependencia (ADR-006).
- **Método**: revisión del código y de la configuración por capítulo. Cada control se prueba en el CI (tests de API y
  Vitest) o en la E2E contra la imagen. Dependencias auditadas con `npm audit` y `pip-audit`
  (`build/logs/fase10_pip_audit.txt`).
- **Resultado**: sin hallazgos CRITICAL ni HIGH abiertos. Los corregidos en esta fase están marcados **Corregido** y
  tienen test; los riesgos aceptados están al final.

## V1 Arquitectura

| Control | Estado | Evidencia |
|---|---|---|
| Capas y dependencias definidas | Cumple | `.ai/architecture.md`; `tests/unit/test_architecture.py` (capas, ACL de util_bbdd) |
| Decisiones de seguridad documentadas | Cumple | ADR-003 (sesiones), ADR-004 (cifrado), ADR-007 (sitio aislado), ADR-008/009/010 (escritura) |
| Un único punto de control de acceso | Cumple | `api/deps.py` (`CurrentUser`, `AdminUser`, `csrf_protect`), `get_membership`/`get_access` por rol |

## V2 Autenticación

| Control | Estado | Evidencia |
|---|---|---|
| 2.1.1–2.1.2 longitud 12–128 | Cumple | `passwords.check_policy`, `UBW_PASSWORD_MIN_LENGTH` |
| 2.1.7 contraseñas comunes o filtradas | **Corregido** | Lista local del NCSC (45 578 entradas, sin llamadas externas): `domain/identity/data/` |
| 2.2.1 anti-automatización | **Corregido** | Bloqueo por cuenta (ADR-003) + límite por IP de intentos y fallos de login (`test_hardening.py`) |
| 2.4.1 almacenamiento | Cumple | Argon2id (pwdlib), rehash al cambiar parámetros |
| 2.5.x recuperación | Cumple | Sin autoservicio: el admin restablece y se revocan las sesiones |
| 2.2.3/2.7 MFA | Riesgo aceptado | Ver al final |
| Mensajes genéricos y mismo tiempo | Cumple | Mismo error para usuario inexistente, desactivado o bloqueado; `burn_verification` |

## V3 Sesiones

| Control | Estado | Evidencia |
|---|---|---|
| 3.2.1 token nuevo al autenticar | Cumple | Rotación en el login (`test_auth.py`) |
| 3.2.3 token no almacenado en claro | Cumple | Solo SHA-256 en `sessions` |
| 3.3.1–3.3.2 caducidad por inactividad y absoluta | Cumple | `UBW_SESSION_IDLE_MINUTES` / `UBW_SESSION_ABSOLUTE_HOURS` |
| 3.3.3 cerrar las demás sesiones al cambiar la contraseña | Cumple | `change_password` revoca las demás |
| 3.3.4 ver y cerrar sesiones activas | Cumple | *Sesiones* (usuario y admin) |
| 3.4.1–3.4.3 `Secure`, `HttpOnly`, `SameSite` | Cumple | `set_auth_cookies` |
| 3.4.4 prefijo `__Host-` | **Corregido** | `__Host-ubw_session` y `__Host-ubw_csrf` con TLS (E2E `security.spec.ts`) |
| 3.5.x CSRF | Cumple | Doble envío firmado con HMAC de la sesión en todo método no seguro de `/api/v1` |

## V4 Control de acceso

| Control | Estado | Evidencia |
|---|---|---|
| 4.1.x denegar por defecto, en el servidor | Cumple | Dependencias por ruta; roles `owner`/`editor`/`viewer` y permisos especiales |
| 4.2.1 IDOR | Cumple | Recursos de otro proyecto → 404 (tests por fase: runs, uploads, conexiones) |
| 4.3.1 administración | Cumple | `AdminUser`; E2E de usuario sin administración y de miembros con rol |
| Operaciones destructivas | Cumple | Regla 6 de SHARED: permiso + owner + modo seco + confirmación (ADR-008/009/010) |

## V5 Validación, sanitización y codificación

| Control | Estado | Evidencia |
|---|---|---|
| 5.1.x validación de entrada | Cumple | Pydantic con `extra="forbid"`, patrones de identificadores y límites |
| 5.2.x HTML no confiable | Cumple | React escapa; Markdown y HTML generados en iframes `sandbox` con CSP propia (ADR-007) |
| 5.2.6 SSRF | Cumple | Allowlist de destinos, bloqueo de metadatos cloud (Fase 2) |
| 5.3.4 inyección SQL | Cumple | SQLAlchemy con parámetros; SQL libre solo de lectura con `sqlglot` y transacción de solo lectura |
| 5.3.x rutas de fichero | Cumple | Parámetros de ruta confinados a `UBW_FILES_DIR`; workspace con rutas seguras |

## V7 Errores y registro

| Control | Estado | Evidencia |
|---|---|---|
| 7.1.1–7.1.2 sin secretos ni datos sensibles | Cumple | Mensajes de motor saneados (`_engine_message`, `redact_values`); `test_auth.py` comprueba que el token no se registra |
| 7.1.3 eventos de seguridad | Cumple | `audit_log` (login, bloqueo, permisos, escrituras en destino) |
| 7.1.4 formato común con contexto | **Corregido** | JSON con `request_id` y ruta plantilla; `X-Request-ID` en respuestas y *problem details* |
| 7.4.1 errores genéricos | Cumple | *Problem details* sin trazas; 500 sin detalle |

## V8 Protección de datos

| Control | Estado | Evidencia |
|---|---|---|
| 8.2.1 caché de respuestas sensibles | **Corregido** | `Cache-Control: no-store` en `/api` salvo descargas con política propia |
| 8.3.x datos en reposo | Cumple | Secretos de conexión con Fernet (ADR-004); copias sin claves (`app.cli backup`) |
| 8.3.4 datos sensibles en URL | Cumple con nota | Solo el sitio HTML usa URL firmada y temporal (ADR-007) |

## V9 Comunicaciones

| Control | Estado | Evidencia |
|---|---|---|
| 9.1.x TLS | Cumple (despliegue) | Proxy TLS obligatorio fuera de localhost (`deployment.md`); HSTS en producción con HTTPS |
| Confianza en cabeceras del proxy | **Corregido** | `FORWARDED_ALLOW_IPS` explícito en el compose |

## V10 Código malicioso e integridad

| Control | Estado | Evidencia |
|---|---|---|
| 10.3.2 integridad de dependencias | **Corregido** | Locks con hash; util_bbdd desde la release con SHA-256 en `uv.lock` (ADR-006) |
| Edad mínima de versiones | Cumple | `exclude-newer` y `npm --before` (excepciones justificadas) |

## V12 Ficheros

| Control | Estado | Evidencia |
|---|---|---|
| 12.1.x tamaño y bombas zip | Cumple | `UBW_UPLOAD_MAX_MB`, tamaño descomprimido de `.xlsx` (Fase 9) |
| 12.2.1 tipo real | Cumple | Contenido verificado; macros rechazadas |
| 12.3.x nombres y rutas | Cumple | Nombre propio (`<ulid>.<ext>`), fuera de la raíz web |
| 12.5.x | Cumple | Descargas con `nosniff`, CSP `sandbox` y `Content-Disposition` |

## V13 API

| Control | Estado | Evidencia |
|---|---|---|
| 13.1.x | Cumple | Mismo origen, sin CORS; métodos explícitos por ruta |
| 13.2.x JSON | Cumple | Pydantic; tipos de contenido fijados por FastAPI |
| Exposición del esquema | **Corregido** | `/api/openapi.json` y `/api/docs` solo fuera de producción |
| Límites de uso | **Corregido** | Rate limiting por sesión/IP y de subidas; 429 con `Retry-After` |

## V14 Configuración

| Control | Estado | Evidencia |
|---|---|---|
| 14.1.x build reproducible | Cumple | Imagen multi-stage con versiones fijas; contenedor `read_only`, sin capacidades, usuario sin privilegios |
| 14.2.1 componentes sin vulnerabilidades conocidas | **Corregido** | opentelemetry-api 1.45.1 (CVE-2026-114603) y Vite 8.3.4; ver riesgos para mariadb |
| 14.3.2 sin modo depuración ni cabecera `Server` | Cumple | `--no-server-header`, `/api/docs` fuera de producción |
| 14.4.x cabeceras | **Corregido** | CSP de la SPA (`script-src 'self'`), `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP, `frame-ancestors 'none'`; la E2E falla ante una violación de CSP |
| 14.5.x | Cumple | Sin CORS; `X-Request-ID` validado |

## Riesgos aceptados

| Riesgo | Motivo | Mitigación |
|---|---|---|
| Sin MFA propio | Despliegue en red interna; el ROADMAP no lo incluye | Poner delante un proxy con SSO/MFA si se expone fuera de la red interna |
| `style-src 'unsafe-inline'` | Mantine inyecta `<style>` y atributos `style` | `script-src 'self'` sin excepciones; sin datos de usuario como CSS |
| Rate limiting en memoria por proceso | `web` es un solo proceso uvicorn | Con varios procesos se multiplica el límite (documentado); el bloqueo por cuenta está en la BD |
| `mariadb` 1.1.14 (PYSEC-2026-217) | Aviso del C API con `big5` y escape manual; no hay versión corregida | La web no escapa a mano (parámetros enlazados) y usa `utf8mb4` |
| Contenido de negocio en artefactos | Es el propósito de la aplicación (SQL generado, rechazos, ficheros subidos) | Visibles solo para los miembros del proyecto; retención configurable |
