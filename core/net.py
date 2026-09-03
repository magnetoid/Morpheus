"""Outbound-request safety: one SSRF gate for every server-initiated fetch.

Morpheus makes outbound HTTP on behalf of *untrusted input*: a merchant types a
webhook URL, an agent hands `pdf_url` to a catalog tool, a channel plugin follows
a report link. Every one of those is a request the SERVER makes from inside the
network, so an attacker who controls the URL can reach anything the server can —
cloud metadata (169.254.169.254 → instance credentials), a database admin port,
an internal-only service. That is SSRF, and the only reliable defence is to
refuse before the socket opens.

This module is the single home for that check. It started life inside
`catalog/services/_helpers.py` guarding the agent PDF/cover download; it lives in
core now because the same gate is needed by webhook delivery and by any plugin
that fetches a caller-supplied URL — and because two copies of a security check
WILL drift, and the looser copy becomes the hole (the CLAUDE.md "two lists with
the same name" landmine, applied to a security boundary).

**Known limit, stated honestly:** `getaddrinfo` resolves the host, then
`requests` resolves it AGAIN when it connects. An attacker controlling DNS can
answer differently the second time (DNS rebinding / TOCTOU). Closing that fully
requires pinning the resolved address into the connection, which means a custom
transport adapter. What this does guarantee is that a host resolving to an
unsafe address at check time is refused, which stops the entire class of
"just point it at the metadata endpoint" attacks.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger('morpheus.net')

#: Belt-and-braces literals. These are already covered by the link-local /
#: private checks below; listing them makes the intent greppable and survives
#: someone "simplifying" the range checks later.
BLOCKED_LITERAL_IPS = frozenset(
    {
        '169.254.169.254',  # AWS/GCP/Azure IMDS
        '100.100.100.200',  # Alibaba Cloud metadata
    }
)


class UnsafeUrlError(ValueError):
    """Raised when a URL is refused by the egress gate."""


class UnresolvableHostError(UnsafeUrlError):
    """The host could not be resolved — refused, but TRANSIENTLY.

    Deliberately distinct from a plain `UnsafeUrlError`, because the two demand
    opposite handling. "Resolves to 127.0.0.1" is permanent and must never be
    retried. "DNS did not answer" is usually a blip, and treating it as
    permanent would let a brief resolver outage kill every queued webhook
    instead of retrying it. Callers doing a one-shot synchronous fetch can just
    catch the base class; a retrying deliverer should catch this first.

    Security note: allowing a retry here concedes nothing. A host that does not
    resolve cannot be connected to, and if it *starts* resolving the full check
    runs again on the next attempt.
    """


def is_public_ip(ip) -> bool:
    """True iff `ip` is a routable public address."""
    if str(ip) in BLOCKED_LITERAL_IPS:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_remote_host(host: str) -> bool:
    """True iff `host` resolves ONLY to public, routable addresses.

    A literal IP is checked directly. A name is resolved with `getaddrinfo` and
    EVERY returned record must be public — one forward lookup can return several
    addresses and it only takes one internal answer to make the fetch dangerous.
    A resolution failure refuses rather than allows: unknown is not safe.
    """
    if not host:
        return False
    try:
        return is_public_ip(ipaddress.ip_address(host))
    except ValueError:
        pass  # not a literal — resolve it

    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError, UnicodeError) as e:
        raise UnresolvableHostError(f'host {host!r} could not be resolved') from e

    seen_any = False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not is_public_ip(ip):
            return False
        seen_any = True
    return seen_any


def resolves_safely(host: str) -> bool:
    """Non-raising form of :func:`is_safe_remote_host` — an unresolvable host
    reads as unsafe. Kept for callers that want one boolean and no retry
    distinction (the catalog download path)."""
    try:
        return is_safe_remote_host(host)
    except UnresolvableHostError:
        return False


def check_outbound_url(url: str, *, field: str = 'url', require_https: bool = True) -> str:
    """Validate `url` for a server-initiated fetch; return the host.

    Raises `UnsafeUrlError` for a bad scheme, a missing host, or a host that
    resolves anywhere non-public. Callers that must tolerate http:// (legacy
    webhook receivers) pass ``require_https=False`` — the SSRF check still runs,
    because that is the part protecting the network.
    """
    parsed = urlparse(url or '')
    allowed = ('https',) if require_https else ('https', 'http')
    if parsed.scheme not in allowed:
        raise UnsafeUrlError(f'{field} must be an {" or ".join(allowed)}:// URL')
    host = (parsed.hostname or '').lower()  # .hostname strips IPv6 brackets
    if not host:
        raise UnsafeUrlError(f'{field} is not a valid URL')
    if not is_safe_remote_host(host):
        raise UnsafeUrlError(f'{field} host {host!r} is not a public address (SSRF guard)')
    return host


def is_safe_outbound_url(url: str, *, require_https: bool = True) -> bool:
    """Non-raising form of :func:`check_outbound_url`."""
    try:
        check_outbound_url(url, require_https=require_https)
    except UnsafeUrlError:
        return False
    return True
