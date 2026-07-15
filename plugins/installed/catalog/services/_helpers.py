"""Private helpers shared by every services/ module.

Constants, the public ``PublishError`` exception, URL + file download
primitives, slug + SKU uniquifiers, the price coercer, the
``_serialize_*`` formatters, and the variant-field applier all live
here so the public-API modules (products, categories, images,
variants) stay slim.

Leading underscore on the filename marks the module as private — the
storefront/views/ split uses the same convention. External callers
import from the package root (``catalog.services``), never from
``catalog.services._helpers``.
"""

from __future__ import annotations

import io
import ipaddress
import logging
import re
import socket
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import requests
from django.utils.text import slugify

logger = logging.getLogger('morpheus.catalog.services')


# ── Download / validation limits ──────────────────────────────────────
_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB hard cap for PDF
_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB hard cap for cover image
_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # absolute response ceiling
_DOWNLOAD_TIMEOUT = 10  # seconds — was 30, tightened
_ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

# AWS IMDS — exact-literal block, in case the link-local check misses
# something. 169.254.169.254 is both IPv4 link-local and the canonical
# IMDS address.
_BLOCKED_LITERAL_IPS = {'169.254.169.254'}


# ── Field allow-lists ─────────────────────────────────────────────────
_PRODUCT_SCALAR_FIELDS = {
    # str-like
    'name',
    'sku',
    'short_description',
    'description',
    'meta_title',
    'meta_description',
    'focus_keyword',
    'canonical_url',
    'og_title',
    'og_description',
    'twitter_title',
    'twitter_description',
    'twitter_card',
    'weight_unit',
    # bool
    'is_featured',
    'is_taxable',
    'track_inventory',
    'requires_shipping',
    'noindex',
    'nofollow',
    # numeric (handled in coercion)
    'weight',
}

_VALID_PRODUCT_TYPES = {'simple', 'variable', 'digital', 'bundle'}
_VALID_STATUSES = {'draft', 'active', 'archived'}
_VALID_VARIANT_TYPES = {'physical', 'digital', 'audiobook', 'virtual'}
_VALID_INVENTORY_POLICIES = {'deny', 'continue'}


class PublishError(Exception):
    """Raised when a digital-product publish call can't proceed.
    Message is safe to surface to the caller (no internal paths)."""


def _is_safe_remote_host(host: str) -> bool:
    """Return True iff `host` resolves only to public, routable addresses.

    Defends against SSRF. Resolves the host with `getaddrinfo` and checks
    EVERY returned A/AAAA record — a single forward lookup can return
    multiple addresses, and an attacker controlling DNS can also rebind
    between resolution and connection (TOCTOU). We can't fully prevent
    rebinding without pinning the resolved IP into `requests`, but we
    can refuse the request when any returned address is unsafe.

    Rejected ranges:
      - loopback (127.0.0.0/8, ::1)
      - private (10/8, 172.16/12, 192.168/16, etc.)
      - link-local (169.254/16) — covers AWS IMDS
      - reserved
      - multicast
      - the literal AWS IMDS address as a belt-and-suspenders check
    """
    if not host:
        return False
    # Literal IP supplied? Parse it directly and reject if non-public.
    try:
        ip = ipaddress.ip_address(host)
        return _is_public_ip(ip)
    except ValueError:
        pass  # not a literal — fall through to DNS resolution.

    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError, UnicodeError):
        # Resolution failure → refuse rather than silently allow.
        return False

    seen_any = False
    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if not _is_public_ip(ip):
            return False
        seen_any = True
    return seen_any


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    if str(ip) in _BLOCKED_LITERAL_IPS:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _validate_https_url(url: str, *, field: str) -> None:
    parsed = urlparse(url or '')
    if parsed.scheme != 'https':
        raise PublishError(f'{field} must be an https:// URL')
    if not parsed.netloc:
        raise PublishError(f'{field} is not a valid URL')


def _download(url: str, *, max_bytes: int, field: str) -> tuple[bytes, str, str]:
    """Stream `url` → (body, content_type, filename). Hard size + timeout caps."""
    # SSRF gate: reject loopback / private / IMDS hosts before any
    # outbound socket. urlparse strips brackets from IPv6 hosts via
    # .hostname (parsed.netloc would include them).
    parsed = urlparse(url or '')
    host = (parsed.hostname or '').lower()
    if not _is_safe_remote_host(host):
        raise PublishError(f'{field} host {host!r} is not a public address (SSRF guard)')

    # Cap response size at 50 MB regardless of what the caller asked for.
    cap = min(max_bytes, _MAX_DOWNLOAD_BYTES)
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            content_type = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            cl = r.headers.get('Content-Length')
            if cl and int(cl) > cap:
                raise PublishError(f'{field} exceeds {cap // (1024 * 1024)} MB limit')
            buf = io.BytesIO()
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buf.write(chunk)
                if buf.tell() > cap:
                    # Force the connection closed; iter_content + ctx
                    # manager handle the socket release.
                    raise PublishError(f'{field} exceeds {cap // (1024 * 1024)} MB limit')
            url_name = PurePosixPath(urlparse(url).path).name or field
            return buf.getvalue(), content_type, url_name
    except requests.RequestException as e:
        raise PublishError(f'{field} download failed: {e}') from None


def _unique_slug(base: str) -> str:
    """Return a slug that doesn't collide with an existing product."""
    from plugins.installed.catalog.models import Product

    base = slugify(base) or 'book'
    candidate = base
    n = 2
    while Product.objects.filter(slug=candidate).exists():
        candidate = f'{base}-{n}'
        n += 1
        if n > 200:
            raise PublishError('could not allocate a unique slug')
    return candidate


def _unique_sku(suggested: str, *, fallback_base: str) -> str:
    from plugins.installed.catalog.models import Product

    base = re.sub(r'[^A-Za-z0-9._-]', '', (suggested or '')).upper().strip('-_.')
    if not base:
        base = ('BOOK-' + re.sub(r'[^A-Z0-9]', '', slugify(fallback_base).upper()))[:32]
    candidate = base
    n = 2
    while Product.objects.filter(sku=candidate).exists():
        candidate = f'{base}-{n}'
        n += 1
        if n > 200:
            raise PublishError('could not allocate a unique SKU')
    return candidate


def _coerce_price(amount: Any) -> Decimal:
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise PublishError('price_amount is not a valid number') from None
    if d < 0:
        raise PublishError('price_amount must be >= 0')
    return d


# ── Serializers ───────────────────────────────────────────────────────


def _serialize_product(p) -> dict:
    return {
        'id': str(p.id),
        'slug': p.slug,
        'sku': p.sku,
        'name': p.name,
        'status': p.status,
        'product_type': p.product_type,
        'price_amount': str(getattr(p.price, 'amount', '')) if p.price else '',
        'price_currency': str(getattr(p.price, 'currency', '')) if p.price else '',
        'url': f'/products/{p.slug}/',
    }


def _serialize_category(c) -> dict:
    return {
        'id': str(c.id),
        'slug': c.slug,
        'name': c.name,
        'parent_slug': c.parent.slug if c.parent_id else '',
    }


def _serialize_image(img) -> dict:
    return {
        'id': str(img.id),
        'product_slug': img.product.slug,
        'url': img.image.url if img.image else '',
        'alt_text': img.alt_text or '',
        'is_primary': bool(img.is_primary),
        'sort_order': int(img.sort_order or 0),
    }


def _serialize_variant(v) -> dict:
    return {
        'id': str(v.id),
        'product_slug': v.product.slug,
        'name': v.name,
        'sku': v.sku,
        'size': getattr(v, 'size', '') or '',
        'short_description': getattr(v, 'short_description', '') or '',
        'description': getattr(v, 'description', '') or '',
        'price_amount': str(getattr(v.price, 'amount', '')) if v.price else '',
        'price_currency': str(getattr(v.price, 'currency', '')) if v.price else '',
        'variant_type': getattr(v, 'variant_type', 'physical'),
        'requires_shipping': bool(getattr(v, 'requires_shipping', True)),
        'is_taxable': bool(getattr(v, 'is_taxable', True)),
        'inventory_policy': getattr(v, 'inventory_policy', 'deny'),
        'barcode': getattr(v, 'barcode', '') or '',
        'is_active': bool(v.is_active),
        'sort_order': int(v.sort_order or 0),
    }


# ── Variant field applier ─────────────────────────────────────────────


def _apply_variant_fields(variant, fields: dict, *, allow_sku_collision_check: bool = True) -> None:  # noqa: PLR0912, PLR0915
    """Mutate `variant` in place with whatever fields are present. Skips
    unspecified keys so partial updates work. Raises PublishError on
    invalid input."""
    from djmoney.money import Money

    from plugins.installed.catalog.models import ProductVariant

    if 'name' in fields:
        name = (fields['name'] or '').strip()
        if not name:
            raise PublishError('variant name is required')
        variant.name = name
    if 'sku' in fields:
        sku = (fields['sku'] or '').strip()
        if not sku:
            raise PublishError('variant sku is required')
        if allow_sku_collision_check:
            qs = ProductVariant.objects.filter(sku=sku)
            if variant.pk:
                qs = qs.exclude(pk=variant.pk)
            if qs.exists():
                raise PublishError(f'sku {sku!r} already in use by another variant')
        variant.sku = sku
    if 'price_amount' in fields:
        v = fields['price_amount']
        if v in (None, '', 'null'):
            variant.price = None
        else:
            currency = (
                fields.get('price_currency')
                or str(getattr(variant.price, 'currency', None) or 'USD')
            ).upper()
            variant.price = Money(_coerce_price(v), currency)
    if 'compare_at_amount' in fields:
        v = fields['compare_at_amount']
        if v in (None, '', 'null'):
            variant.compare_at_price = None
        else:
            currency = (
                fields.get('price_currency')
                or str(getattr(variant.price, 'currency', None) or 'USD')
            ).upper()
            variant.compare_at_price = Money(_coerce_price(v), currency)
    if 'variant_type' in fields:
        vt = fields['variant_type']
        if vt not in _VALID_VARIANT_TYPES:
            raise PublishError(f'variant_type must be one of {sorted(_VALID_VARIANT_TYPES)}')
        variant.variant_type = vt
        # Helpful auto: if requires_shipping wasn't explicitly set,
        # default it from variant_type.
        if 'requires_shipping' not in fields:
            variant.requires_shipping = vt == 'physical'
    if 'requires_shipping' in fields:
        variant.requires_shipping = bool(fields['requires_shipping'])
    if 'is_taxable' in fields:
        variant.is_taxable = bool(fields['is_taxable'])
    if 'inventory_policy' in fields:
        ip = fields['inventory_policy']
        if ip not in _VALID_INVENTORY_POLICIES:
            raise PublishError(
                f'inventory_policy must be one of {sorted(_VALID_INVENTORY_POLICIES)}'
            )
        variant.inventory_policy = ip
    if 'barcode' in fields:
        variant.barcode = (fields['barcode'] or '').strip()[:50]
    if 'size' in fields:
        variant.size = (fields['size'] or '').strip()[:50]
    if 'short_description' in fields:
        variant.short_description = (fields['short_description'] or '').strip()
    if 'description' in fields:
        variant.description = (fields['description'] or '').strip()
    if 'is_active' in fields:
        variant.is_active = bool(fields['is_active'])
    if 'sort_order' in fields:
        try:
            variant.sort_order = max(0, int(fields['sort_order']))
        except (TypeError, ValueError):
            raise PublishError('sort_order must be an integer') from None
