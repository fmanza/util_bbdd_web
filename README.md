# util_bbdd_web

Aplicación web multiusuario sobre [util_bbdd](https://github.com/fmanza/util_bbdd). Ofrece:

- catálogo de motores con sus capacidades;
- conexiones cifradas;
- proyectos por usuario;
- ejecuciones de util_bbdd (documentación, grafos, comparación de esquemas, migración DDL, volcado y carga bulk),
  con los resultados guardados y **agrupados por ejecución**.

> Estado: **1.0.0 — release** (Fases 0–10 cerradas; revisión [ASVS L2](docs/security/ASVS_L2.md)). Novedades en el
> [CHANGELOG](CHANGELOG.md).

## Puesta en marcha

Guía completa (local y producción): **[docs/guides/puesta_en_marcha.md](docs/guides/puesta_en_marcha.md)**.

### Probar en local (Docker)

```bash
python scripts/generate_secrets.py                                   # secrets/*.txt (no se versionan)
docker compose up -d --build                                         # web (API + SPA) y worker
docker compose exec web python -m app.cli create-admin --username admin
```

Abre <http://127.0.0.1:8080>. Estado: <http://127.0.0.1:8080/api/health> (`"status": "ok"`, `"worker": "ok"`).

### Desarrollar

API con recarga en caliente (uv o Docker), worker y Vite en <http://localhost:5173>: ver
[Puesta en marcha › En local](docs/guides/puesta_en_marcha.md#3-en-local) y la
[guía de desarrolladores](docs/guides/onboarding_dev.md).

### Producción

Servidor interno con Docker Compose detrás de un proxy TLS. Pasos:

1. Desplegar una versión etiquetada.
2. Generar los secretos, legibles por el uid 10001.
3. Crear el `.env` a partir de [.env.example](.env.example).
4. Configurar el proxy (nginx o Caddy).
5. Crear el primer administrador y los destinos permitidos.
6. Programar las copias de seguridad.

Detalle en [Puesta en marcha › En producción](docs/guides/puesta_en_marcha.md#4-en-producción) y referencia en
[Despliegue](docs/guides/deployment.md).

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React 19 + TypeScript 5.9, Vite 8, React Router 8, TanStack Query 5, Mantine 9, i18next |
| Backend | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2.1, Alembic, prometheus-client |
| Persistencia | SQLite (WAL) en el volumen `data`; salidas en el volumen `workspace` |
| Librería | util_bbdd 4.1.0 (wheel de la release v4.1.0 en GitHub, hash fijado en `uv.lock`, ADR-006) |
| Contenedor | Dockerfile multi-stage, usuario no root, sistema de ficheros de solo lectura, sin capacidades |

## Documentación

Índice completo: [docs/README.md](docs/README.md).

- **Uso**: [Guía de usuario](docs/guides/guia_usuario.md) (empieza aquí) · [Usuarios y sesiones](docs/guides/usuarios_y_sesiones.md) ·
  [Motores y conexiones](docs/guides/conexiones.md) · [Proyectos y ejecuciones](docs/guides/proyectos_y_ejecuciones.md) ·
  [Explorador y SQL](docs/guides/explorador.md) · [Documentación y grafos](docs/guides/documentacion.md) ·
  [Comparación](docs/guides/comparacion.md) · [Migración DDL](docs/guides/migracion.md) ·
  [Volcado](docs/guides/volcado.md) · [Carga bulk](docs/guides/carga.md)
- **Operación**: [Puesta en marcha](docs/guides/puesta_en_marcha.md) · [Despliegue](docs/guides/deployment.md) ·
  [Solución de problemas](docs/guides/troubleshooting.md) · [Seguridad (ASVS L2)](docs/security/ASVS_L2.md)
- **Desarrollo**: [Guía de desarrolladores](docs/guides/onboarding_dev.md) · [Arquitectura](docs/architecture.md) ·
  [Decisiones (ADR)](docs/adr/) · [ROADMAP](docs/plan/ROADMAP.md) · [Huecos de util_bbdd](docs/plan/UTIL_BBDD_GAPS.md)
- **Asistentes IA**: [CLAUDE.md](CLAUDE.md), [.github/copilot-instructions.md](.github/copilot-instructions.md),
  [.github/SHARED_INSTRUCTIONS.md](.github/SHARED_INSTRUCTIONS.md)

## Licencia

MIT — ver [LICENSE](LICENSE).
