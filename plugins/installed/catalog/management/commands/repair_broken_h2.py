"""
Repair the broken `<h2>Title\\nbody...</h2>` shape produced by the
first version of ``convert_descriptions_to_html`` (when the LLM
omitted a blank line between ``## Title`` and its body paragraph,
the converter swallowed everything into the heading).

Splits each broken block into ``<h2>Title</h2>\\n<p>body</p>``. Same
for ``<h3>``. Idempotent — already-fine HTML is left alone.

Usage:
    python manage.py repair_broken_h2
    python manage.py repair_broken_h2 --slugs pinocchio,dorian-gray
    python manage.py repair_broken_h2 --dry-run
"""
from __future__ import annotations

import logging
import re

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.catalog')


# Matches <h2>Title\nbody...</h2> where body contains no further HTML
# tags (so we don't accidentally chew through nested markup).
_BROKEN_HEADING = re.compile(
    r'<(h[23])>([^<\n]+)\n([^<]+?)</\1>',
    flags=re.IGNORECASE | re.DOTALL,
)


def _repair(html: str) -> str:
    def _sub(m: re.Match) -> str:
        tag = m.group(1)
        title = m.group(2).strip()
        body = m.group(3).strip()
        return f'<{tag}>{title}</{tag}>\n<p>{body}</p>'
    return _BROKEN_HEADING.sub(_sub, html or '')


class Command(BaseCommand):
    help = 'Split <h2>title\\nbody</h2> blocks left by the old markdown converter.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--slugs', default='')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts) -> None:
        from plugins.installed.catalog.models import Product

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        dry = bool(opts['dry_run'])

        qs = Product.objects.filter(status='active').order_by('name')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        fixed = unchanged = 0
        for product in qs:
            before = product.description or ''
            after = _repair(before)
            if after == before:
                unchanged += 1
                continue
            self.stdout.write(f'→ {product.slug}: {len(before)} → {len(after)} chars')
            if dry:
                continue
            product.description = after
            product.save(update_fields=['description'])
            fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f'done — fixed={fixed} unchanged={unchanged}'
        ))
