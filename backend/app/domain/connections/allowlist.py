"""Allowlist de destinos de las conexiones salientes (anti-SSRF).

Política (denegación por defecto):

- Siempre denegados: link-local (``169.254.0.0/16`` y ``fe80::/10``, metadatos cloud), multicast, sin especificar y
  reservados.
- Loopback: solo si una entrada **CIDR** lo incluye de forma explícita (``127.0.0.1/32``).
- Resto: permitido si el nombre de host encaja en un patrón (``db.corp``, ``*.corp``, ``*``) o **todas** sus IP
  resueltas están en alguna red CIDR.

La comprobación se hace justo antes de conectar. Entre la resolución y la conexión del driver cabe un *DNS rebinding*
(riesgo residual documentado: sustituir el host por la IP rompería la verificación TLS).
"""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AllowlistEntry
from app.domain.connections.errors import (
    AllowlistDuplicateError,
    AllowlistEntryNotFoundError,
    InvalidAllowlistPatternError,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
Resolver = Callable[[str], list[IPAddress]]

_HOSTNAME = re.compile(r"^(\*|(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*)$")
_DNS_TIMEOUT = 5.0
_DNS_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="allowlist-dns")


@dataclass(frozen=True)
class Policy:
    """Patrones ya interpretados."""

    networks: tuple[IPNetwork, ...]
    hostnames: tuple[str, ...]


def normalize_pattern(pattern: str) -> str:
    """Patrón canónico (CIDR normalizado o nombre en minúsculas).

    Raises:
        InvalidAllowlistPatternError: Ni red CIDR/IP ni nombre de host válido.
    """
    value = pattern.strip().lower()
    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError:
        pass
    if _HOSTNAME.fullmatch(value) and len(value) <= 253:
        return value
    raise InvalidAllowlistPatternError(
        "Usa una red CIDR (10.0.0.0/8), una IP, un nombre de host (db.empresa.local) o un comodín (*.empresa.local)."
    )


def build_policy(patterns: Iterable[str]) -> Policy:
    networks: list[IPNetwork] = []
    hostnames: list[str] = []
    for pattern in patterns:
        try:
            networks.append(ipaddress.ip_network(pattern, strict=False))
        except ValueError:
            hostnames.append(pattern.lower())
    return Policy(networks=tuple(networks), hostnames=tuple(hostnames))


def _hostname_matches(host: str, patterns: Iterable[str]) -> bool:
    host = host.lower().rstrip(".")
    for pattern in patterns:
        if pattern == "*" or pattern == host:
            return True
        if pattern.startswith("*.") and host.endswith(pattern[1:]):
            return True
    return False


def _always_denied(ip: IPAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved


def _unmapped(ip: IPAddress) -> IPAddress:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def resolve(host: str) -> list[IPAddress]:
    """IP de ``host`` (literal o por DNS, con timeout).

    Raises:
        OSError: No se puede resolver a tiempo.
    """
    literal = host.strip("[]")
    try:
        return [ipaddress.ip_address(literal)]
    except ValueError:
        pass
    future = _DNS_POOL.submit(socket.getaddrinfo, host, None, proto=socket.IPPROTO_TCP)
    try:
        infos = future.result(timeout=_DNS_TIMEOUT)
    except FutureTimeout:
        raise OSError(f"Timeout resolviendo {host}") from None
    return list(dict.fromkeys(ipaddress.ip_address(info[4][0]) for info in infos))


def is_allowed(host: str, policy: Policy, resolver: Resolver = resolve) -> bool:
    """``True`` si la política permite conectar con ``host``."""
    try:
        addresses = [_unmapped(ip) for ip in resolver(host)]
    except OSError:
        return False
    if not addresses:
        return False
    by_name = _hostname_matches(host, policy.hostnames)
    for ip in addresses:
        if _always_denied(ip):
            return False
        in_network = any(ip.version == net.version and ip in net for net in policy.networks)
        if ip.is_loopback and not in_network:
            return False
        if not (by_name or in_network):
            return False
    return True


# --- hosts de los parámetros -------------------------------------------------------------------------------------

_JDBC_NET = re.compile(r"^jdbc:hsqldb:(?:hsqls?|https?)://(\[[^\]]+\]|[^:/;]+)", re.IGNORECASE)
_ORACLE_HOST = re.compile(r"\(\s*HOST\s*=\s*([^)\s]+)\s*\)", re.IGNORECASE)


def _dsn_host(dsn: str) -> list[str]:
    if "(" in dsn:
        return _ORACLE_HOST.findall(dsn)
    rest = re.sub(r"^[a-z]+://", "", dsn.strip(), flags=re.IGNORECASE).lstrip("/")
    if rest.startswith("["):
        return [rest[1 : rest.index("]")]] if "]" in rest else []
    host = re.split(r"[:/]", rest, maxsplit=1)[0]
    return [host] if host else []


def target_hosts(db_type: str, conn_params: dict[str, Any]) -> list[str]:
    """Hosts a los que conectará el driver con ``conn_params`` (ya con los valores por defecto aplicados)."""
    if db_type == "sqlite":
        return []
    if db_type == "hsqldb":
        match = _JDBC_NET.match(str(conn_params.get("jdbc_url", "")))
        return [match.group(1).strip("[]")] if match else []
    if db_type == "oracle" and conn_params.get("dsn"):
        return _dsn_host(str(conn_params["dsn"]))
    host = conn_params.get("host")
    return [str(host)] if host else []


# --- persistencia ------------------------------------------------------------------------------------------------


def list_entries(db: Session) -> list[AllowlistEntry]:
    return list(db.scalars(select(AllowlistEntry).order_by(AllowlistEntry.pattern)).all())


def current_policy(db: Session) -> Policy:
    return build_policy(entry.pattern for entry in list_entries(db))


def add_entry(db: Session, *, pattern: str, description: str, actor_id: int, ctx: RequestContext) -> AllowlistEntry:
    """Añade un destino permitido.

    Raises:
        InvalidAllowlistPatternError: Patrón no válido.
        AllowlistDuplicateError: Ya existe.
    """
    normalized = normalize_pattern(pattern)
    if db.scalar(select(AllowlistEntry).where(AllowlistEntry.pattern == normalized)) is not None:
        raise AllowlistDuplicateError()
    entry = AllowlistEntry(pattern=normalized, description=description.strip(), created_by=actor_id)
    db.add(entry)
    db.flush()
    audit.record(
        db,
        action=AuditAction.ALLOWLIST_CREATE,
        ctx=ctx,
        actor_id=actor_id,
        target_type="allowlist",
        target_id=entry.id,
        details={"pattern": normalized},
    )
    db.commit()
    return entry


def delete_entry(db: Session, entry_id: int, *, actor_id: int, ctx: RequestContext) -> None:
    """Quita un destino permitido.

    Raises:
        AllowlistEntryNotFoundError: No existe.
    """
    entry = db.get(AllowlistEntry, entry_id)
    if entry is None:
        raise AllowlistEntryNotFoundError()
    audit.record(
        db,
        action=AuditAction.ALLOWLIST_DELETE,
        ctx=ctx,
        actor_id=actor_id,
        target_type="allowlist",
        target_id=entry.id,
        details={"pattern": entry.pattern},
    )
    db.delete(entry)
    db.commit()
