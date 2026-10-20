# util_bbdd_web

Aplicación web multiusuario sobre [util_bbdd](vendor/wheels/): catálogo de motores con sus capacidades, conexiones
cifradas, proyectos por usuario y ejecuciones de util_bbdd (documentación, grafos, comparación de esquemas,
migración DDL, volcado y carga bulk) con los resultados guardados y **agrupados por ejecución**.

> Estado: **0.3.0 — Fase 2 (catálogo de motores y conexiones)**. El plan completo está en [docs/plan/ROADMAP.md](docs/plan/ROADMAP.md).

## Arranque rápido

```bash
python scripts/generate_secrets.py
docker compose up -d --build
```

Crea el primer administrador (no hay credenciales por defecto):

```bash
docker compose exec web python -m app.cli create-admin --username admin
```

Abre <http://127.0.0.1:8080> e inicia sesión. Estado del servicio: <http://127.0.0.1:8080/api/health>.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React 19 + TypeScript 5.9, Vite 8, React Router 8, TanStack Query 5, Mantine 9, i18next |
| Backend | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2.1, Alembic |
| Persistencia | SQLite (WAL) en volumen `data`; salidas en volumen `workspace` |
| Librería | util_bbdd 4.0.0 (wheel en `vendor/wheels/`, ADR-006) |
| Contenedor | Dockerfile multi-stage, usuario no root, sistema de ficheros de solo lectura |

## Documentación

- [Arquitectura](docs/architecture.md) · [Decisiones (ADR)](docs/adr/) · [ROADMAP](docs/plan/ROADMAP.md)
- [Incorporación de desarrolladores](docs/guides/onboarding_dev.md) · [Despliegue](docs/guides/deployment.md) ·
  [Solución de problemas](docs/guides/troubleshooting.md)
- Uso: [Usuarios, sesiones y auditoría](docs/guides/usuarios_y_sesiones.md) ·
  [Motores y conexiones](docs/guides/conexiones.md)
- Asistentes IA: [CLAUDE.md](CLAUDE.md), [.github/copilot-instructions.md](.github/copilot-instructions.md),
  [.github/SHARED_INSTRUCTIONS.md](.github/SHARED_INSTRUCTIONS.md)

## Licencia

MIT — ver [LICENSE](LICENSE).
