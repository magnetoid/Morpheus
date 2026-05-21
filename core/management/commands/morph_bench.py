"""Lightweight latency benchmark for the storefront + dashboard hot paths.

Hits a small list of representative URLs N times, measures TTFB + total
time, and prints a p50/p95/p99 table. Designed to be safe to run
against production — read-only GETs, no auth required for the public
URLs.

This is the baseline for perf regression detection. Run it before and
after a perf-sensitive change; if any p95 line moves by >15% you have
a regression worth investigating.

Usage:
    python manage.py morph_bench --base-url https://dotbooks.store --iterations 30
    python manage.py morph_bench --base-url http://localhost:8000 --iterations 50
    python manage.py morph_bench --target dashboard --iterations 20   # auth-required path
    python manage.py morph_bench --json                                # machine-readable

Output: human-readable table by default; ``--json`` emits one JSON line
per URL with all percentiles so CI can diff between runs.
"""
from __future__ import annotations

import json
import logging
import statistics
import time
from typing import Iterable
from urllib import error, request

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.bench')


_PUBLIC_PATHS = [
    ('home',                  '/'),
    ('plp',                   '/products/'),
    ('pdp',                   '/products/hamlet/'),
    ('category',              '/category/fiction/'),
    ('staff_picks',           '/staff-picks/'),
    ('journal_index',         '/journal/'),
    ('about',                 '/about/'),
    ('llms_txt',              '/llms.txt'),
    ('sitemap',               '/sitemap.xml'),
    ('robots',                '/robots.txt'),
]

_AUTH_PATHS = [
    # Hits the assistant page directly — will 302 to login when not
    # authenticated, but still measures the auth-redirect latency.
    ('dashboard_home',        '/dashboard/'),
    ('dashboard_assistant',   '/dashboard/assistant/'),
    ('dashboard_products',    '/dashboard/products/'),
]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _hit(url: str, *, timeout: float = 10.0) -> tuple[int, float]:
    """Return (status_code, elapsed_seconds). Status -1 on transport error."""
    req = request.Request(url, headers={'User-Agent': 'morph-bench/1.0'})
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            resp.read(1024)  # touch first chunk to measure TTFB-ish
            elapsed = time.perf_counter() - started
            return resp.status, elapsed
    except error.HTTPError as e:
        return e.code, time.perf_counter() - started
    except Exception:  # noqa: BLE001
        return -1, time.perf_counter() - started


class Command(BaseCommand):
    help = 'Latency benchmark across storefront + dashboard hot paths.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url', default='http://localhost:8000',
            help='Base URL to bench against. Default localhost:8000.',
        )
        parser.add_argument(
            '--iterations', type=int, default=20,
            help='Requests per URL. More = tighter percentiles. Default 20.',
        )
        parser.add_argument(
            '--target', choices=('public', 'dashboard', 'all'), default='public',
            help='Which path set to hit. Default `public` (no auth needed).',
        )
        parser.add_argument(
            '--warmup', type=int, default=2,
            help='Discarded warmup hits per URL before measuring. Default 2.',
        )
        parser.add_argument(
            '--json', dest='emit_json', action='store_true',
            help='Emit JSON per URL (machine-readable) instead of the table.',
        )

    def handle(self, *args, **opts):
        base = opts['base_url'].rstrip('/')
        n = max(1, int(opts['iterations']))
        warmup = max(0, int(opts['warmup']))
        target = opts['target']
        as_json = bool(opts['emit_json'])

        paths: list[tuple[str, str]] = []
        if target in ('public', 'all'):
            paths.extend(_PUBLIC_PATHS)
        if target in ('dashboard', 'all'):
            paths.extend(_AUTH_PATHS)

        results = []
        if not as_json:
            self.stdout.write(self.style.SUCCESS(
                f'Benchmarking {base} — {n} iterations per URL (warmup={warmup}, target={target})'
            ))
            self.stdout.write(f'  {"name":<20} {"path":<32} {"p50":>8} {"p95":>8} {"p99":>8} {"max":>8}  status')
            self.stdout.write(f'  {"-" * 20} {"-" * 32} {"-" * 8} {"-" * 8} {"-" * 8} {"-" * 8}  ------')

        for name, path in paths:
            url = base + path
            for _ in range(warmup):
                _hit(url)

            times: list[float] = []
            statuses: list[int] = []
            for _ in range(n):
                status, elapsed = _hit(url)
                times.append(elapsed * 1000)  # ms
                statuses.append(status)

            from collections import Counter
            status_summary = ','.join(
                f'{s}×{c}' for s, c in Counter(statuses).most_common()
            )
            row = {
                'name': name, 'path': path, 'url': url,
                'iterations': n,
                'p50_ms': _percentile(times, 50),
                'p95_ms': _percentile(times, 95),
                'p99_ms': _percentile(times, 99),
                'max_ms': max(times) if times else 0,
                'statuses': dict(Counter(statuses)),
            }
            results.append(row)
            if not as_json:
                self.stdout.write(
                    f'  {name:<20} {path:<32} '
                    f'{row["p50_ms"]:>7.0f}ms {row["p95_ms"]:>7.0f}ms '
                    f'{row["p99_ms"]:>7.0f}ms {row["max_ms"]:>7.0f}ms  {status_summary}'
                )

        if as_json:
            for row in results:
                self.stdout.write(json.dumps(row))
        else:
            self.stdout.write('')
            overall_p95 = _percentile([r['p95_ms'] for r in results], 50)
            self.stdout.write(self.style.SUCCESS(
                f'Median p95 across {len(results)} URLs: {overall_p95:.0f}ms'
            ))
