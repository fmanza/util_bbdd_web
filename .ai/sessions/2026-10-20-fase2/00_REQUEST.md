# REQUEST

## Session metadata
- id: 2026-10-20-fase2
- fecha: 2026-10-20
- rama: develop
- skill: phase
- fase solicitada: Fase 2 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
«Adelante» tras cerrar la Fase 1 (siguiente paso: `/phase 2`). Inputs aclarados con el usuario: alcance completo;
mejoras opcionales: no (la matriz de capacidades es «mejora incluida» del ROADMAP); dependencias nuevas:
`react-hook-form` + `zod`, y después `cryptography` como directa; motores de prueba: contenedores bench de util_bbdd.

## Objetivo operativo de esta sesión
- Catálogo de motores con ficha y matriz de capacidades construidas en la capa anticorrupción.
- Conexiones con secreto cifrado (Fernet), visibilidad privada/compartida, prueba y readiness en subproceso.
- Allowlist anti-SSRF gestionada por el admin y confinamiento de rutas en `UBW_FILES_DIR`.
- Frontend con formulario dinámico (RHF + Zod), E2E y pruebas de integración contra los bench.

## Restricciones explícitas
- Dependencias nuevas solo `react-hook-form`, `zod` y `cryptography` (sin `@hookform/resolvers`).
- Sin servicios externos en el CI; pruebas contra motores reales marcadas `integration`.
- No adelantar historias de fases posteriores. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.3.0 con la DoD común y la de la Fase 2.
