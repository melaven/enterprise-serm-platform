"""SSRF-гард для парсеров: вызывать ПЕРЕД каждым запросом и после каждого редиректа."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"https"}


class SSRFBlocked(ValueError):
    pass


def assert_public_url(url: str, allowed_hosts: frozenset[str] | None = None) -> list[str]:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES or not parts.hostname or parts.username or parts.password:
        raise SSRFBlocked("scheme/host/userinfo")
    host = parts.hostname.lower()
    if allowed_hosts is not None and not any(host == h or host.endswith("." + h) for h in allowed_hosts):
        raise SSRFBlocked("host not in allowlist")
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFBlocked("dns") from e
    ips = sorted({i[4][0] for i in infos})
    for ip in ips:
        a = ipaddress.ip_address(ip)
        if not a.is_global or a.is_multicast:
            raise SSRFBlocked(f"non-public address {ip}")
    return ips   # коннектиться к конкретному IP (pin), иначе DNS-rebinding между проверкой и запросом
