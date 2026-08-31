"""Validação de origem para a superfície HTTP/WebSocket local da Aila."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def local_origin_allowed(
    origin: str | None, host_header: str, client_host: str | None
) -> bool:
    """Aceita browser na mesma porta loopback ou cliente local sem Origin."""
    if not origin:
        return loopback_host(client_host)
    try:
        parsed = urlparse(origin)
        # Host do app é IPv4/localhost hoje. split simples evita aceitar uma
        # origem em outra porta; IPv6 entre colchetes continua coberto abaixo.
        if host_header.startswith("["):
            end = host_header.find("]")
            port_text = host_header[end + 2:] if host_header[end + 1:end + 2] == ":" else ""
        else:
            port_text = host_header.rsplit(":", 1)[1] if ":" in host_header else ""
        expected_port = int(port_text) if port_text else None
        return (
            parsed.scheme in {"http", "https"}
            and loopback_host(parsed.hostname)
            and (expected_port is None or parsed.port == expected_port)
        )
    except (TypeError, ValueError):
        return False
