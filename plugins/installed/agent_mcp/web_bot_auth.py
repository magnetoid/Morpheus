"""Web Bot Auth at the origin — RFC 9421 HTTP Message Signatures from agents.

draft-meunier-web-bot-auth-architecture: an agent signs each request with an
Ed25519 key it publishes as a JWKS at
``<origin>/.well-known/http-message-signatures-directory``, names that origin
in ``Signature-Agent``, names the key by its RFC 7638 thumbprint in ``keyid``,
covers ``@authority`` (and ``signature-agent``) and tags the signature
``web-bot-auth``. Cloudflare verifies this at the edge for proxied zones and
stamps ``X-Verified-Agent-*`` (``middleware.py``); this module does the same
verification at the origin, so a store that is not proxied — or has no proxy
secret configured — still knows which agent it is talking to.

Everything here fails SOFT: a request that does not verify is an anonymous
request, never a refused one. The result is informational (which agent placed
an order), not authorization — scopes and consent gate writes as before.

The one thing an anonymous request can make the origin do is fetch a key
directory, so ``Signature-Agent`` is trusted only as a public https host with a
fixed path, the body is capped, a failed fetch is remembered, and the number
of fetches per minute is bounded for the whole process.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.core.cache import cache

logger = logging.getLogger('morpheus.agent_mcp.web_bot_auth')

TAG = 'web-bot-auth'
DIRECTORY_PATH = '/.well-known/http-message-signatures-directory'
COVERED_REQUIRED = ('@authority',)
MAX_WINDOW_S = 86400  # created → expires; the draft wants short-lived signatures
CLOCK_SKEW_S = 60
JWKS_TTL_S = 3600
JWKS_NEGATIVE_TTL_S = 300
JWKS_MAX_BYTES = 65536
FETCH_TIMEOUT_S = 3
MAX_FETCHES_PER_MINUTE = 30

_NEGATIVE = {'__unavailable__': True}
_LABEL_RE = re.compile(r'^[a-z*][a-z0-9_\-.*]*$')
_INT_RE = re.compile(r'^-?\d+$')


@dataclass(frozen=True)
class VerifiedBot:
    origin: str  # the Signature-Agent origin, e.g. https://agent.example
    keyid: str  # the RFC 7638 thumbprint the agent signed with


# ── JWK ───────────────────────────────────────────────────────────────────


def _b64url_decode(value: str) -> bytes:
    value = value.strip()
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def jwk_thumbprint(jwk: dict) -> str:
    """RFC 7638 thumbprint of an OKP key: SHA-256 over the canonical JSON of
    its required members (``crv``, ``kty``, ``x``, sorted, no whitespace)."""
    canonical = json.dumps(
        {'crv': jwk['crv'], 'kty': jwk['kty'], 'x': jwk['x']},
        separators=(',', ':'),
        sort_keys=True,
    )
    return _b64url(hashlib.sha256(canonical.encode('utf-8')).digest())


# ── Structured-field parsing (the subset the draft uses) ──────────────────


def _split_top_level(value: str, sep: str) -> list[str]:
    """Split on ``sep`` outside quoted strings and parentheses."""
    parts, buf, depth, quoted = [], [], 0, False
    i = 0
    while i < len(value):
        ch = value[i]
        if quoted:
            buf.append(ch)
            if ch == '\\' and i + 1 < len(value):
                buf.append(value[i + 1])
                i += 1
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            buf.append(ch)
        elif ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append(''.join(buf).strip())
    return [p for p in parts if p]


def _unquote(value: str) -> str:
    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        raise ValueError('expected a quoted string')
    inner = value[1:-1]
    if '"' in inner.replace('\\"', ''):
        raise ValueError('unescaped quote')
    return inner.replace('\\"', '"').replace('\\\\', '\\')


def _parse_params(parts: list[str]) -> dict:
    params: dict = {}
    for part in parts:
        if '=' not in part:
            raise ValueError(f'bare parameter {part!r}')
        name, raw = part.split('=', 1)
        name = name.strip()
        raw = raw.strip()
        if not _LABEL_RE.match(name):
            raise ValueError(f'bad parameter name {name!r}')
        if raw.startswith('"'):
            params[name] = _unquote(raw)
        elif _INT_RE.match(raw):
            params[name] = int(raw)
        else:
            raise ValueError(f'unsupported parameter value for {name!r}')
    return params


def _parse_dictionary(value: str) -> dict[str, str]:
    """``a=..., b=...`` → {label: raw member text}."""
    members: dict[str, str] = {}
    for member in _split_top_level(value, ','):
        if '=' not in member:
            raise ValueError('dictionary member without a value')
        label, raw = member.split('=', 1)
        label = label.strip()
        if not _LABEL_RE.match(label):
            raise ValueError(f'bad label {label!r}')
        members[label] = raw.strip()
    return members


def parse_signature_input(value: str) -> tuple[str, list[str], dict, str]:
    """One ``Signature-Input`` member → (label, components, params, raw).

    ``raw`` is the member text exactly as sent (the inner list plus its
    parameters): RFC 9421 makes it the ``@signature-params`` line of the
    signature base, so it must be used verbatim, never re-serialised.
    When several signatures are present, the one tagged ``web-bot-auth``
    wins; without a tag the first one does.
    """
    members = _parse_dictionary(value)
    if not members:
        raise ValueError('empty Signature-Input')
    chosen = None
    for label, raw in members.items():
        if raw.startswith('(') and f'tag="{TAG}"' in raw:
            chosen = (label, raw)
            break
    if chosen is None:
        chosen = next(iter(members.items()))
    label, raw = chosen
    if not raw.startswith('('):
        raise ValueError('signature parameters must be an inner list')
    end = raw.find(')')
    if end < 0:
        raise ValueError('unterminated inner list')
    components = []
    for item in raw[1:end].split():
        if ';' in item:
            raise ValueError('component parameters are not supported')
        components.append(_unquote(item))
    params = _parse_params(_split_top_level(raw[end + 1 :], ';'))
    return label, components, params, raw


def parse_signature(value: str, label: str) -> bytes:
    """The ``Signature`` member for ``label`` → raw signature bytes."""
    raw = _parse_dictionary(value).get(label)
    if raw is None or len(raw) < 2 or raw[0] != ':' or raw[-1] != ':':
        raise ValueError('signature is not a byte sequence')
    try:
        return base64.b64decode(raw[1:-1], validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError('signature is not base64') from e


# ── The agent's origin ────────────────────────────────────────────────────


def agent_origin(header_value: str) -> str | None:
    """``Signature-Agent`` → ``https://host[:port]`` when it names a public
    https origin the store may fetch a directory from, else None.

    Rejected: anything unquoted, http, a path, userinfo, an IP literal,
    ``localhost``/``.local``/``.internal``, and a dotless host — on a shared
    Docker network a bare service name (``web``, ``db``) resolves to another
    store's container.
    """
    try:
        return _parse_agent_origin(header_value)
    except ValueError:
        return None


def _parse_agent_origin(header_value: str) -> str:
    value = _unquote((header_value or '').strip())
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.netloc or parts.username or parts.password:
        raise ValueError('not a plain https origin')
    if parts.path not in ('', '/') or parts.query or parts.fragment:
        raise ValueError('an origin has no path')
    host = (parts.hostname or '').lower()
    if not host or '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('not a public host')
    if host == 'localhost' or host.startswith('localhost.'):
        raise ValueError('not a public host')
    try:
        ipaddress.ip_address(host.strip('[]'))
    except ValueError:
        pass
    else:
        raise ValueError('an IP literal is never a published agent')
    port = parts.port  # raises ValueError on a bad port
    return f'https://{host}:{port}' if port and port != 443 else f'https://{host}'


# ── Key directory ─────────────────────────────────────────────────────────


def _fetch_jwks(origin: str) -> dict:
    """GET the agent's key directory (fixed path, https only, size-capped)."""
    import requests  # noqa: PLC0415

    resp = requests.get(
        origin + DIRECTORY_PATH,
        timeout=FETCH_TIMEOUT_S,
        allow_redirects=False,
        stream=True,
        headers={
            'Accept': 'application/http-message-signatures-directory+json, application/json',
            'User-Agent': 'Morpheus web-bot-auth verifier',
        },
    )
    try:
        if resp.status_code != 200:
            raise ValueError(f'directory answered {resp.status_code}')
        declared = resp.headers.get('Content-Length')
        if declared and declared.isdigit() and int(declared) > JWKS_MAX_BYTES:
            raise ValueError('directory too large')
        body = b''
        for chunk in resp.iter_content(chunk_size=8192):
            body += chunk
            if len(body) > JWKS_MAX_BYTES:
                raise ValueError('directory too large')
    finally:
        resp.close()
    data = json.loads(body.decode('utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('keys'), list):
        raise ValueError('directory is not a JWKS')
    return data


def _fetch_budget_ok() -> bool:
    key = f'wba:fetches:{int(time.time()) // 60}'
    try:
        count = cache.get(key, 0)
        if count >= MAX_FETCHES_PER_MINUTE:
            return False
        cache.set(key, count + 1, timeout=120)
    except Exception:  # noqa: BLE001 — a cache outage must not turn into fetches
        return False
    return True


def directory_keys(origin: str) -> list[dict]:
    """The agent's JWKS keys, cached per origin; [] when unavailable."""
    cache_key = f'wba:jwks:{origin}'
    cached = cache.get(cache_key)
    if cached is not None:
        return [] if cached == _NEGATIVE else list(cached.get('keys') or [])
    if not _fetch_budget_ok():
        logger.info('web-bot-auth: directory fetch budget exhausted; %s unverified', origin)
        return []
    try:
        jwks = _fetch_jwks(origin)
    except Exception as e:  # noqa: BLE001 — unverifiable, not refused
        logger.info('web-bot-auth: directory for %s unavailable: %s', origin, e)
        cache.set(cache_key, _NEGATIVE, timeout=JWKS_NEGATIVE_TTL_S)
        return []
    cache.set(cache_key, jwks, timeout=JWKS_TTL_S)
    return list(jwks.get('keys') or [])


def _public_key(keys: list[dict], keyid: str):
    from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: PLC0415

    for jwk in keys:
        if not isinstance(jwk, dict) or jwk.get('kty') != 'OKP' or jwk.get('crv') != 'Ed25519':
            continue
        if not isinstance(jwk.get('x'), str):
            continue
        try:
            if jwk.get('kid') != keyid and jwk_thumbprint(jwk) != keyid:
                continue
            return ed25519.Ed25519PublicKey.from_public_bytes(_b64url_decode(jwk['x']))
        except Exception as e:  # noqa: BLE001 — a malformed key is skipped
            logger.debug('web-bot-auth: skipping malformed key: %s', e)
            continue
    return None


# ── Verification ──────────────────────────────────────────────────────────


_DERIVED = {
    '@authority': lambda r: r.get_host().lower(),
    '@method': lambda r: r.method.upper(),
    '@path': lambda r: r.path,
    '@query': lambda r: '?' + r.META.get('QUERY_STRING', ''),
    '@scheme': lambda r: r.scheme,
    '@target-uri': lambda r: r.build_absolute_uri(),
}


def _component_value(request, name: str) -> str:
    if name.startswith('@'):
        derive = _DERIVED.get(name)
        if derive is None:
            raise ValueError(f'unsupported derived component {name}')
        return derive(request)
    value = request.headers.get(name)
    if value is None:
        raise ValueError(f'covered field {name} is absent')
    return value.strip()


def verify_request(request) -> VerifiedBot | None:
    """The agent that signed this request, or None. Never raises."""
    agent_header = request.META.get('HTTP_SIGNATURE_AGENT')
    if not agent_header:
        return None
    try:
        origin = agent_origin(agent_header)
        if origin is None:
            raise ValueError('Signature-Agent is not a public https origin')
        label, components, params, raw = parse_signature_input(
            request.META.get('HTTP_SIGNATURE_INPUT', '')
        )
        signature = parse_signature(request.META.get('HTTP_SIGNATURE', ''), label)
        if params.get('tag') != TAG:
            raise ValueError('not a web-bot-auth signature')
        if params.get('alg') not in (None, 'ed25519'):
            raise ValueError('unsupported alg')
        keyid = params.get('keyid')
        created, expires = params.get('created'), params.get('expires')
        if not isinstance(keyid, str) or not keyid:
            raise ValueError('keyid missing')
        if not isinstance(created, int) or not isinstance(expires, int):
            raise ValueError('created/expires missing')
        now = int(time.time())
        if created > now + CLOCK_SKEW_S or expires <= now or expires - created > MAX_WINDOW_S:
            raise ValueError('signature outside its validity window')
        if any(c not in components for c in COVERED_REQUIRED):
            raise ValueError('@authority is not covered')
        lines = [f'"{c}": {_component_value(request, c)}' for c in components]
        lines.append(f'"@signature-params": {raw}')
        base = '\n'.join(lines).encode('utf-8')
        key = _public_key(directory_keys(origin), keyid)
        if key is None:
            raise ValueError('no matching key in the directory')
        key.verify(signature, base)
    except Exception as e:  # noqa: BLE001 — malformed or forged: anonymous, not refused
        logger.debug('web-bot-auth: request not verified: %s', e)
        return None
    return VerifiedBot(origin=origin, keyid=keyid)
