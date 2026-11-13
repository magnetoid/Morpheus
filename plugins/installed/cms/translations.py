"""Which CMS text can be translated (`TRANSLATABLE_CONTENT`).

A page's title, excerpt and body. A page built from sections renders them instead of
its body, and their content is not registered, so such a page stays in the store's
default language (`applies`).
"""

from __future__ import annotations


def _live_pages():
    from django.utils import timezone

    from plugins.installed.cms.models import Page

    return Page.objects.filter(state='published').exclude(publish_at__gt=timezone.now())


def page_path(page) -> str:
    """The page's public path: a journal post's, a route another app claims, or /p/<slug>/."""
    from core.hooks import MorpheusEvents, hook_registry

    if (page.metadata or {}).get('category') == 'journal':
        return f'/journal/{page.slug}/'
    path = hook_registry.filter(MorpheusEvents.CMS_PAGE_PATH, f'/p/{page.slug}/', page=page)
    return path if isinstance(path, str) and path.startswith('/') else f'/p/{page.slug}/'


def _without_sections(page) -> bool:
    return not page.sections.filter(is_visible=True).exists()


def on_translatable_content(value, **kwargs):
    """TRANSLATABLE_CONTENT — published pages and journal posts without sections."""
    from plugins.installed.cms.models import Page

    return [
        *(value or []),
        {
            'key': 'cms.page',
            'model': Page,
            'label': 'Pages',
            'fields': {'title': 'text', 'excerpt': 'text', 'body': 'html'},
            'queryset': lambda: _live_pages().exclude(sections__is_visible=True).distinct(),
            'url': page_path,
            'applies': _without_sections,
        },
    ]


def show(pages):
    """Overlay the page language's reviewed translations on pages."""
    from core.i18n.services import overlay_translation

    return overlay_translation(pages)
