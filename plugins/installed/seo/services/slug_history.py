"""Public paths for objects, and the 301s that keep old ones alive.

Renaming a product renames its URL. Every link pointing at the old one, every
ranking it had, and every bookmark break at once — and nothing in the dashboard
says so. This module records the change and mints the redirect, which is the
difference between renaming a page and losing it.

`URL_TEMPLATES` is the one place that knows what an object's public path looks
like. It is a map rather than `reverse()` on purpose: these run inside signal
handlers, which can fire during `apps.ready()` before the URL conf has finished
loading, and a `NoReverseMatch` there would break the merchant's save.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.seo')

# model label → storefront path template. Keep in step with the storefront's
# own routes; a wrong template mints a redirect from a URL that never existed,
# which is harmless but useless.
URL_TEMPLATES = {
    'catalog.product': '/products/{slug}/',
    'catalog.category': '/category/{slug}/',
    'catalog.collection': '/collection/{slug}/',
    'cms.page': '/journal/{slug}/',
}


def public_path_for(obj, *, slug: str | None = None) -> str:
    """The storefront path for ``obj``, or '' when the object has no public URL."""
    if obj is None:
        return ''
    label = f'{obj._meta.app_label}.{obj._meta.model_name}'
    template = URL_TEMPLATES.get(label)
    if not template:
        return ''
    value = slug if slug is not None else (getattr(obj, 'slug', '') or '')
    if not value:
        return ''
    return template.format(slug=value)


def record_slug_change(obj, *, old_slug: str, new_slug: str) -> None:
    """Store the old path and, unless the merchant turned it off, 301 it.

    The history row is written even when auto-redirects are disabled: it costs
    one row, and it is what lets the 404 suggester answer "this URL used to be
    that product" later with certainty instead of a fuzzy guess.
    """
    from plugins.installed.seo.models import SlugHistory

    old_path = public_path_for(obj, slug=old_slug)
    new_path = public_path_for(obj, slug=new_slug)
    if not old_path or not new_path or old_path == new_path:
        return

    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(type(obj))
    SlugHistory.objects.get_or_create(
        content_type=ct,
        object_id=str(obj.pk),
        old_path=old_path,
        defaults={'new_path': new_path},
    )
    # An older redirect pointing at the path we just vacated would now be a
    # chain (A→B, B→C). Repoint it in the same breath, so the merchant never
    # accumulates hops they did not create.
    _repoint_existing(old_path, new_path)

    if not _auto_redirect_enabled():
        return
    _mint_redirect(old_path, new_path)


def _mint_redirect(old_path: str, new_path: str) -> None:
    from plugins.installed.seo.models import Redirect

    existing = Redirect.objects.filter(from_path=old_path, match_type=Redirect.MATCH_EXACT).first()
    if existing is not None:
        # Never overwrite a rule a human wrote: they may have deliberately sent
        # the old URL somewhere other than the renamed page.
        if existing.source != 'auto_slug':
            return
        existing.to_path = new_path
        existing.is_active = True
        existing.save()
        return
    Redirect.objects.create(
        from_path=old_path,
        to_path=new_path,
        status_code=301,
        match_type=Redirect.MATCH_EXACT,
        source='auto_slug',
        note='Created automatically when the slug changed.',
    )


def _repoint_existing(old_path: str, new_path: str) -> None:
    from plugins.installed.seo.models import Redirect
    from plugins.installed.seo.services.redirects import invalidate_redirect_cache

    moved = (
        Redirect.objects.filter(to_path=old_path, source='auto_slug')
        .exclude(from_path=new_path)
        .update(to_path=new_path)
    )
    # A queryset update skips post_save, so the resolver would keep serving the
    # old target from its cached ruleset until the TTL lapsed. Bulk is the right
    # call here (a much-renamed product can have many rows); the explicit
    # invalidation is what makes it safe.
    if moved:
        invalidate_redirect_cache()


def _auto_redirect_enabled() -> bool:
    from ._helpers import site_settings

    try:
        return bool(getattr(site_settings(), 'auto_redirect_on_slug_change', True))
    except Exception:  # noqa: BLE001 — unmigrated DB during a deploy
        return True
