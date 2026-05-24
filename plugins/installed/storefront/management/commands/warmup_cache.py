"""warmup_cache — hit the top-N storefront URLs after a deploy.

Each fetch primes:
  * the StorefrontCacheMiddleware (origin in-memory cache, if enabled)
  * Cloudflare's edge cache (a 200 with s-maxage populates the closest
    CF datacenter on the request path)
  * the OS page cache for any media files referenced from the HTML

Reads the Caching page toggles:
  * ``post_deploy_warmup`` — if False, the command no-ops with an exit 0
    (so the deploy hook is harmless when warmup is disabled)
  * ``warmup_top_n`` — how many products + categories to fetch
    (default 20, capped at 500 by the panel form)

Usage:
    python manage.py warmup_cache
    python manage.py warmup_cache --force --top-n 50 --base https://dotbooks.store
    python manage.py warmup_cache --dry-run

Designed to be called from the Docker entrypoint after ``migrate`` so
the first real user request lands on a hot cache.
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from typing import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse

logger = logging.getLogger('morpheus.storefront.warmup')


def _config() -> dict:
    try:
        from plugins.registry import plugin_registry
        p = plugin_registry.get('storefront')
        if p is None:
            return {}
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def _urls_to_warm(top_n: int) -> list[str]:
    """Return a deduped list of relative storefront paths to fetch.

    Order matters: home + PLP + top categories first (highest fan-in),
    then top products. Capped at top_n total.
    """
    paths: list[str] = ['/']
    try:
        paths.append(reverse('storefront:product_list'))
    except NoReverseMatch:
        paths.append('/products/')

    try:
        from plugins.installed.catalog.models import Category, Product
        # Featured + most-recent active categories.
        cats = list(
            Category.objects.filter(is_active=True)
            .order_by('sort_order', '-id')
            .values_list('slug', flat=True)[: max(5, top_n // 4)]
        )
        for slug in cats:
            paths.append(f'/category/{slug}/')

        # Featured + most-recent active products.
        slugs = list(
            Product.objects.filter(status='active')
            .order_by('-is_featured', '-updated_at')
            .values_list('slug', flat=True)[:top_n]
        )
        for slug in slugs:
            paths.append(f'/products/{slug}/')
    except Exception:  # noqa: BLE001
        logger.warning('warmup_cache: could not enumerate catalog rows', exc_info=True)

    # Dedupe while preserving order; cap to top_n + housekeeping pages.
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out[: top_n + 2]


def _fetch(url: str, timeout: float, user_agent: str) -> tuple[int, float]:
    req = urllib.request.Request(url, headers={
        'User-Agent': user_agent,
        'Accept': 'text/html,*/*;q=0.8',
        'Accept-Encoding': 'gzip',
    })
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1024)  # touch the body so the origin actually renders
            return resp.status, time.monotonic() - started
    except urllib.error.HTTPError as e:
        return e.code, time.monotonic() - started
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.debug('warmup_cache: fetch %s failed: %s', url, e)
        return 0, time.monotonic() - started


class Command(BaseCommand):
    help = 'Fetch the top-N storefront URLs to prime origin + CF edge caches.'

    def add_arguments(self, parser):
        parser.add_argument('--base', default='', help='Base URL (default: SITE_URL setting or http://localhost:8000)')
        parser.add_argument('--top-n', type=int, default=0, help='Override warmup_top_n config value')
        parser.add_argument('--force', action='store_true', help='Run even if post_deploy_warmup config is off')
        parser.add_argument('--dry-run', action='store_true', help='List URLs without fetching')
        parser.add_argument('--timeout', type=float, default=10.0, help='Per-request timeout in seconds')

    def handle(self, *args, base, top_n, force, dry_run, timeout, **kwargs):
        cfg = _config()
        enabled = bool(cfg.get('post_deploy_warmup', False))
        if not enabled and not force:
            self.stdout.write('warmup_cache: post_deploy_warmup is off — skipping (use --force to override).')
            return

        configured_top_n = int(cfg.get('warmup_top_n') or 20)
        n = top_n or configured_top_n
        n = max(1, min(n, 500))

        if not base:
            base = (getattr(settings, 'SITE_URL', '') or 'http://localhost:8000').rstrip('/')

        paths = _urls_to_warm(n)
        if dry_run:
            self.stdout.write(f'warmup_cache: would fetch {len(paths)} URLs at base {base}:')
            for p in paths:
                self.stdout.write(f'  {base}{p}')
            return

        user_agent = 'MorpheusCacheWarmup/1.0 (+post-deploy)'
        ok = 0
        total_ms = 0.0
        for path in paths:
            url = f'{base}{path}'
            status, elapsed = _fetch(url, timeout=timeout, user_agent=user_agent)
            total_ms += elapsed * 1000.0
            if 200 <= status < 400:
                ok += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ {status} {path}  ({elapsed*1000:.0f}ms)'))
            else:
                self.stdout.write(self.style.WARNING(f'  ✗ {status} {path}  ({elapsed*1000:.0f}ms)'))

        self.stdout.write(
            f'warmup_cache: {ok}/{len(paths)} ok in {total_ms:.0f}ms total '
            f'(avg {total_ms / max(1, len(paths)):.0f}ms)'
        )
