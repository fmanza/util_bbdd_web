"""Prueba de carga básica contra una instancia en marcha (Fase 10). Sin dependencias nuevas: httpx + asyncio.

Cada usuario virtual inicia su propia sesión (con la cuenta indicada) y repite lecturas habituales de la SPA
(usuario, proyectos, motores, ejecuciones del proyecto y detalle de una ejecución); de vez en cuando lanza una
ejecución ``noop`` corta. Al terminar imprime p50/p95/p99 por ruta y el recuento de estados, y borra el proyecto de
prueba. Código de salida 1 si no se cumplen los umbrales (p95 de lecturas y tasa de errores 5xx/red).

Uso (desde ``backend/``, con la aplicación levantada; la contraseña se lee de la entrada estándar)::

    uv run --frozen python ../scripts/load_test.py --base http://127.0.0.1:8080 --user e2e-admin \\
        --users 20 --duration 60 < contraseña.txt

Con más usuarios que ``UBW_RATE_LIMIT_LOGIN_PER_MINUTE`` los inicios de sesión darán 429: se reintentan.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import httpx

READ_ROUTES = ("/api/v1/auth/me", "/api/v1/projects", "/api/v1/engines", "/api/v1/projects/{pid}/runs")


@dataclass
class Stats:
    latencies: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    statuses: Counter[str] = field(default_factory=Counter)
    errors: int = 0

    def record(self, route: str, started: float, response: httpx.Response | None) -> None:
        self.latencies[route].append(time.perf_counter() - started)
        if response is None:
            self.errors += 1
            self.statuses["network"] += 1
            return
        self.statuses[str(response.status_code)] += 1
        if response.status_code >= 500:
            self.errors += 1


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def _keep_cookies(client: httpx.AsyncClient, response: httpx.Response) -> None:
    """Guarda las cookies recibidas y las envía a mano en ``Cookie``.

    Con TLS la aplicación pone cookies ``Secure`` (``__Host-``) que httpx no reenvía por HTTP: así la prueba también
    vale contra ``http://127.0.0.1:8080`` (sin proxy delante).
    """
    jar = dict(item.split("=", 1) for item in client.headers.get("Cookie", "").split("; ") if "=" in item)
    jar.update(response.cookies.items())
    client.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())


async def _login(client: httpx.AsyncClient, user: str, password: str) -> None:
    for attempt in range(10):
        first = await client.get("/api/v1/auth/csrf")
        _keep_cookies(client, first)
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": user, "password": password},
            headers={"X-CSRF-Token": first.json()["csrf_token"]},
        )
        if response.status_code == 200:
            _keep_cookies(client, response)
            client.headers["X-CSRF-Token"] = next(v for k, v in response.cookies.items() if k.endswith("ubw_csrf"))
            return
        if response.status_code != 429:
            raise SystemExit(f"Inicio de sesión fallido: {response.status_code}")
        await asyncio.sleep(int(response.headers.get("Retry-After", "2")) + attempt)
    raise SystemExit("Inicio de sesión: demasiados 429")


async def _virtual_user(base: str, args: argparse.Namespace, password: str, pid: int, deadline: float,
                        stats: Stats) -> None:  # fmt: skip
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        await _login(client, args.user, password)
        run_ids: list[str] = []
        while time.perf_counter() < deadline:
            if random.random() < args.launch_ratio:  # noqa: S311 - carga sintética
                route, started = "POST /projects/{pid}/runs", time.perf_counter()
                try:
                    response = await client.post(
                        f"/api/v1/projects/{pid}/runs",
                        json={"operation": "noop", "params": {"steps": 1, "step_seconds": 0}},
                    )
                    if response.status_code == 202:
                        run_ids.append(response.json()["id"])
                except httpx.HTTPError:
                    response = None
                stats.record(route, started, response)
            else:
                template = random.choice(READ_ROUTES)  # noqa: S311
                if run_ids and random.random() < 0.25:  # noqa: S311
                    template, path = "/api/v1/runs/{run_id}", f"/api/v1/runs/{random.choice(run_ids)}"  # noqa: S311
                else:
                    path = template.format(pid=pid)
                started = time.perf_counter()
                try:
                    response = await client.get(path)
                except httpx.HTTPError:
                    response = None
                stats.record(f"GET {template}", started, response)
            await asyncio.sleep(args.think)


async def _delete_project(client: httpx.AsyncClient, pid: int, *, wait: float = 120.0) -> None:
    """Borra el proyecto de prueba; con ejecuciones aún en cola la API responde 409 y se reintenta."""
    deadline = time.perf_counter() + wait
    while True:
        response = await client.delete(f"/api/v1/projects/{pid}")
        if response.status_code in (204, 404):
            return
        if response.status_code != 409 or time.perf_counter() > deadline:
            print(f"Aviso: no se pudo borrar el proyecto de prueba {pid} ({response.status_code}).")
            return
        await asyncio.sleep(2)


async def main_async(args: argparse.Namespace, password: str) -> int:
    stats = Stats()
    async with httpx.AsyncClient(base_url=args.base, timeout=30) as admin:
        await _login(admin, args.user, password)
        project = await admin.post("/api/v1/projects", json={"name": f"carga-{int(time.time())}", "description": ""})
        project.raise_for_status()
        pid = project.json()["id"]
        try:
            deadline = time.perf_counter() + args.duration
            await asyncio.gather(
                *(_virtual_user(args.base, args, password, pid, deadline, stats) for _ in range(args.users))
            )
        finally:
            await _delete_project(admin, pid)

    total = sum(stats.statuses.values())
    print(f"Usuarios: {args.users} · duración: {args.duration} s · peticiones: {total} ({total / args.duration:.1f}/s)")
    print(f"{'ruta':<36} {'n':>6} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8}")
    worst_read = 0.0
    for route, values in sorted(stats.latencies.items()):
        p50, p95, p99 = (_percentile(values, p) * 1000 for p in (50, 95, 99))
        if route.startswith("GET"):
            worst_read = max(worst_read, p95)
        print(f"{route:<36} {len(values):>6} {p50:>8.1f} {p95:>8.1f} {p99:>8.1f}")
    print("Estados:", dict(sorted(stats.statuses.items())))
    mean = statistics.mean(v for values in stats.latencies.values() for v in values) * 1000 if total else 0
    print(f"Media global: {mean:.1f} ms · errores 5xx/red: {stats.errors}")
    error_rate = stats.errors / total if total else 1.0
    ok = worst_read <= args.max_p95_ms and error_rate <= args.max_error_rate
    print(
        "Resultado:",
        "OK" if ok else "FALLA",
        f"(p95 lecturas ≤ {args.max_p95_ms} ms, errores ≤ {args.max_error_rate:.0%})",
    )
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba de carga básica de util_bbdd_web")
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--user", required=True, help="cuenta con la que entra cada usuario virtual")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--duration", type=int, default=60, help="segundos")
    parser.add_argument("--think", type=float, default=0.2, help="pausa entre peticiones de un usuario (s)")
    parser.add_argument("--launch-ratio", type=float, default=0.02, help="fracción de peticiones que lanzan noop")
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\r\n")
    return asyncio.run(main_async(args, password))


if __name__ == "__main__":
    raise SystemExit(main())
