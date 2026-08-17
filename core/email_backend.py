"""SMTP backend that connects over IPv4 (avoids broken IPv6 routes in Docker)."""

from __future__ import annotations

import socket

from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend


def _resolve_ipv4(host: str) -> str:
    infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
    if not infos:
        raise OSError(f"No IPv4 address for SMTP host {host!r}")
    return infos[0][4][0]


class IPv4SMTPBackend(DjangoSMTPBackend):
    """Use IPv4 for smtp.mail.ru and similar hosts inside Docker."""

    def open(self):
        if self.connection:
            return False
        if self.host:
            self.host = _resolve_ipv4(self.host)
        return super().open()
