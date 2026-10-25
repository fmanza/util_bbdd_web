# Documentación de util_bbdd_web 1.0.0

Se lee en GitHub o como sitio web con [Zensical](https://zensical.org): desde la raíz del repositorio,
`uv run --frozen --project backend --only-group docs zensical serve` (<http://127.0.0.1:8000>) o `… build` (genera
`site/`).

## Para empezar

| Si eres… | Lee primero | Después |
|---|---|---|
| Usuario de la aplicación | [Guía de usuario](guides/guia_usuario.md) | La guía de cada operación (abajo) |
| Quien la instala o la opera | [Puesta en marcha](guides/puesta_en_marcha.md) | [Despliegue](guides/deployment.md), [Solución de problemas](guides/troubleshooting.md) |
| Desarrollador | [Puesta en marcha › En local](guides/puesta_en_marcha.md#3-en-local) | [Guía de desarrolladores](guides/onboarding_dev.md), [Arquitectura](architecture.md) |

## Documentación funcional (uso)

| Guía | Contenido |
|---|---|
| [Guía de usuario](guides/guia_usuario.md) | Qué se puede hacer, roles y permisos, primeros pasos, escritura en dos pasos |
| [Usuarios, sesiones y auditoría](guides/usuarios_y_sesiones.md) | Inicio de sesión, contraseñas, administración de usuarios, sesiones y auditoría |
| [Motores y conexiones](guides/conexiones.md) | Catálogo de motores, conexiones personales y compartidas, prueba y readiness |
| [Proyectos y ejecuciones](guides/proyectos_y_ejecuciones.md) | Proyectos, miembros, lanzar y seguir ejecuciones, artefactos, retención |
| [Explorador y SQL](guides/explorador.md) | Metadatos, DDL, queries nombradas, SQL de solo lectura |
| [Documentación y grafos](guides/documentacion.md) | Documentación Word/Excel/HTML y grafos de relaciones |
| [Comparación de esquemas](guides/comparacion.md) | Diff de esquemas, visor y evolución |
| [Migración DDL](guides/migracion.md) | Plan de migración entre motores, modo seco y aplicación |
| [Volcado de datos](guides/volcado.md) | Copia de filas entre conexiones con vista previa |
| [Carga bulk](guides/carga.md) | Insertar, actualizar o borrar filas desde CSV/Excel |

## Documentación técnica

| Documento | Contenido |
|---|---|
| [Puesta en marcha](guides/puesta_en_marcha.md) | Local con Docker, desarrollo sin Docker, producción paso a paso, comandos de operación |
| [Despliegue](guides/deployment.md) | Referencia de producción: proxy TLS, límites, logs y métricas, variantes, copias, carga, actualización |
| [Solución de problemas](guides/troubleshooting.md) | Errores frecuentes y su causa |
| [Seguridad (ASVS L2)](security/ASVS_L2.md) | Revisión OWASP ASVS nivel 2 y riesgos aceptados |
| [Arquitectura](architecture.md) | Componentes, capas, configuración (`UBW_*`) |
| [Guía de desarrolladores](guides/onboarding_dev.md) | Flujo de trabajo, contrato API, pruebas y E2E |
| [ADR](adr/) | Decisiones de arquitectura (ADR-001 a ADR-012) |
| [ROADMAP](plan/ROADMAP.md), [huecos de util_bbdd](plan/UTIL_BBDD_GAPS.md) y [su plan](plan/UTIL_BBDD_GAPS_PLAN.md) | Plan por fases, limitaciones de la librería y plan para resolverlas |
| [CHANGELOG](https://github.com/fmanza/util_bbdd_web/blob/develop/CHANGELOG.md) | Cambios por versión |
