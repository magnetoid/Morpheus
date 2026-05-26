"""Redirect resolution + 404 monitor + auto-suggester.

``resolve_redirect`` runs on every 404 (in middleware); the rest
power the dashboard's "broken links" panel.
"""
from __future__ import annotations

import re

from ._helpers import logger


def resolve_redirect(path: str) -> tuple[str, int] | None:
    """Return (target_path, status_code) for `path`, or None if no alias exists."""
    from django.db import DatabaseError
    from django.utils import timezone

    from plugins.installed.seo.models import Redirect

    try:
        row = Redirect.objects.filter(from_path=path, is_active=True).first()
    except DatabaseError as e:
        logger.warning('seo: redirect lookup db error: %s', e)
        return None
    if row is None:
        return None
    try:
        Redirect.objects.filter(pk=row.pk).update(
            hit_count=row.hit_count + 1,
            last_hit_at=timezone.now(),
        )
    except DatabaseError:
        pass
    return row.to_path, row.status_code


def record_404(*, path: str, referrer: str = '') -> None:
    from plugins.installed.seo.models import NotFoundLog
    from django.db.models import F as _F
    if not path or len(path) > 500:
        return
    try:
        existing = NotFoundLog.objects.filter(path=path).first()
        if existing:
            NotFoundLog.objects.filter(pk=existing.pk).update(hit_count=_F('hit_count') + 1)
        else:
            NotFoundLog.objects.create(path=path, referrer=referrer[:500])
    except Exception:  # noqa: BLE001
        pass


def suggest_redirect(path: str) -> str:
    """Suggest a live URL for a 404 path.

    Strategy:
      1. Extract the most-significant slug segment (the last
         non-empty path component without a file extension).
      2. Fuzzy-match it against the live product slug index using
         ``difflib.get_close_matches``. This catches typos and
         renamings (e.g. ``the-greate-gatsby`` → ``the-great-gatsby``).
      3. Fall back to token-overlap against category slugs.
      4. Last resort: the legacy substring lookup we used to do.
    """
    if not path:
        return ''
    try:
        from plugins.installed.catalog.models import Category, Product
    except Exception:  # noqa: BLE001
        return ''

    import difflib

    segments = [s for s in path.strip('/').split('/') if s]
    if not segments:
        return ''
    target_slug = re.sub(r'\.[a-z0-9]{1,5}$', '', segments[-1].lower())
    target_slug = re.sub(r'[^a-z0-9-]', '', target_slug)
    tokens = [t for t in target_slug.split('-') if t]
    if not target_slug:
        return ''

    try:
        product_slugs = list(
            Product.objects.filter(status='active').values_list('slug', flat=True)
        )
    except Exception:  # noqa: BLE001
        product_slugs = []

    if product_slugs and target_slug:
        close = difflib.get_close_matches(target_slug, product_slugs, n=1, cutoff=0.6)
        if close:
            return f'/products/{close[0]}/'

    # Token-overlap against products: pick the product whose slug
    # shares the most tokens with the 404 path.
    if tokens and product_slugs:
        best_slug, best_score = '', 0
        for slug in product_slugs:
            slug_tokens = set(t for t in slug.split('-') if len(t) >= 3)
            overlap = sum(1 for t in tokens if t in slug_tokens)
            if overlap > best_score:
                best_score, best_slug = overlap, slug
        if best_score >= 2:
            return f'/products/{best_slug}/'

    # Category fallback.
    try:
        cat_slugs = list(Category.objects.values_list('slug', flat=True))
    except Exception:  # noqa: BLE001
        cat_slugs = []
    if cat_slugs and target_slug:
        close = difflib.get_close_matches(target_slug, cat_slugs, n=1, cutoff=0.6)
        if close:
            return f'/products/?category={close[0]}'
        for token in tokens:
            if token in cat_slugs:
                return f'/products/?category={token}'

    # Legacy contains-substring fallback (kept for backward parity).
    try:
        for token in tokens:
            if len(token) < 3:
                continue
            p = Product.objects.filter(slug__icontains=token, status='active').first()
            if p:
                return f'/products/{p.slug}/'
    except Exception:  # noqa: BLE001
        pass
    return ''


def refresh_404_suggestions(*, limit: int = 50) -> int:
    """Fill in suggested_target on the top unresolved 404s."""
    from plugins.installed.seo.models import NotFoundLog
    n = 0
    rows = NotFoundLog.objects.filter(is_resolved=False).order_by('-hit_count')[:limit]
    for row in rows:
        if row.suggested_target:
            continue
        target = suggest_redirect(row.path)
        if target:
            row.suggested_target = target
            row.save(update_fields=['suggested_target'])
            n += 1
    return n
