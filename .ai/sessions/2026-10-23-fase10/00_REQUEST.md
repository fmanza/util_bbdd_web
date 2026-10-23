# REQUEST

## Session metadata
- id: 2026-10-23-fase10
- fecha: 2026-10-23
- rama: develop
- skill: phase
- fase solicitada: Fase 10 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 10`. Inputs:
- alcance **completo**;
- util_bbdd publicado en **GitHub Releases**;
- dependencia nueva **`prometheus-client`** y rate limiting **propio**;
- **ninguna** mejora opcional.

Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites». Durante IMPLEMENT se confirmó la subida del wheel a la
release `v4.0.0` de `fmanza/util_bbdd` («Sí, súbelo»).

## Objetivo operativo de esta sesión
- Revisión ASVS L2 con remediación, cabeceras, rate limiting, métricas, `request_id`, copias, guía tras TLS, E2E de
  todos los flujos, prueba de carga, variantes verificadas y retirada de `vendor/`.

## Restricciones explícitas
- Dependencias nuevas: solo `prometheus-client`.
- Sin modificar util_bbdd (solo un asset en su release, con confirmación).
- Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 1.0.0.
