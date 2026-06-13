"""CMS dashboard pages."""

# ruff: noqa: PLC0415, I001, S110 — lazy model imports + fail-soft seo lookups, matching siblings.
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

# Where the Pages list lives (the contribute_dashboard_pages route). The CRUD
# views below redirect here on success.
_PAGES_LIST_URL = '/dashboard/apps/cms/pages/'


def _safe_list(model_path, *, order_by='-updated_at', limit=200):
    try:
        from django.apps import apps

        app_label, model_name = model_path.split('.')
        return list(apps.get_model(app_label, model_name).objects.all().order_by(order_by)[:limit])
    except Exception:  # noqa: BLE001
        return []


def _hardcoded_pages() -> list:
    """Storefront pages that live in CODE, declared by ACTIVE plugins via an
    optional ``contribute_hardcoded_pages()`` method (returns dicts with
    ``title`` + ``url``). Read straight off the plugin registry's active set, so
    a disabled plugin's pages drop out automatically — no cross-plugin imports,
    no core-framework change. They render in the Pages list as locked
    ("managed in code") rows so the list stays the registry of every page."""
    try:
        from plugins.registry import plugin_registry
    except Exception:  # noqa: BLE001
        return []
    out = []
    for plugin in plugin_registry.active_plugins():
        fn = getattr(plugin, 'contribute_hardcoded_pages', None)
        if not callable(fn):
            continue
        try:
            for p in fn() or []:
                url = (p.get('url') or '').strip()
                if not url:
                    continue
                out.append(
                    {
                        'title': p.get('title') or url,
                        'url': url,
                        'owner': getattr(plugin, 'label', None) or plugin.name,
                    }
                )
        except Exception:  # noqa: BLE001, S112 — a bad plugin must not break the list
            continue
    return sorted(out, key=lambda p: p['title'].lower())


@staff_member_required
def pages_list(request):
    rows = _safe_list('cms.Page')
    return render(
        request,
        'cms/dashboard/pages.html',
        {'rows': rows, 'hardcoded': _hardcoded_pages(), 'active_nav': 'cms'},
    )


@staff_member_required
def blocks_list(request):
    rows = _safe_list('cms.Block', order_by='key')
    return render(request, 'cms/dashboard/blocks.html', {'rows': rows, 'active_nav': 'cms'})


@staff_member_required
def menus_list(request):
    rows = _safe_list('cms.Menu', order_by='key')
    return render(request, 'cms/dashboard/menus.html', {'rows': rows, 'active_nav': 'cms'})


@staff_member_required
def forms_list(request):
    rows = _safe_list('cms.Form', order_by='key')
    return render(request, 'cms/dashboard/forms.html', {'rows': rows, 'active_nav': 'cms'})


# ──────────────────────────────────────────────────────────────────────────
# Page CRUD — linked from pages_list, routed via urls_dashboard.py.
# Body is TipTap HTML; Page.save() bleach-sanitises it on write.
# ──────────────────────────────────────────────────────────────────────────


def _parse_publish_at(raw):
    """A datetime-local field value ('YYYY-MM-DDTHH:MM') → aware datetime, or None."""
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _page_seo(page):
    """(title, description) from the page's SeoMeta override, or ('', '')."""
    if page is None or not getattr(page, 'pk', None):
        return '', ''
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.seo.models import SeoMeta

        ct = ContentType.objects.get_for_model(type(page))
        sm = SeoMeta.objects.filter(content_type=ct, object_id=str(page.pk)).first()
        if sm:
            return sm.title or '', sm.description or ''
    except Exception:  # noqa: BLE001 — seo plugin optional
        pass
    return '', ''


def _save_page_seo(page, meta_title, meta_description):
    """Upsert the page's SeoMeta override (seo plugin, generic FK). Only writes
    when there's content or an existing row (no empty clutter). Fail-soft."""
    title = (meta_title or '').strip()[:255]
    description = (meta_description or '').strip()[:500]
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.seo.models import SeoMeta

        ct = ContentType.objects.get_for_model(type(page))
        qs = SeoMeta.objects.filter(content_type=ct, object_id=str(page.pk))
        if title or description or qs.exists():
            SeoMeta.objects.update_or_create(
                content_type=ct,
                object_id=str(page.pk),
                defaults={'title': title, 'description': description, 'auto_filled': False},
            )
    except Exception:  # noqa: BLE001 — seo plugin optional
        pass


def _page_form_context(request, page, *, creating):
    from plugins.installed.cms.models import Page

    seo_title, seo_description = _page_seo(page)
    cover_image = (getattr(page, 'metadata', None) or {}).get('cover', '') if page else ''
    return {
        'page': page,
        'creating': creating,
        'state_choices': Page.STATE_CHOICES,
        'layout_choices': Page.LAYOUT_CHOICES,
        'form_action': request.path,
        'active_nav': 'cms',
        'page_meta_title': seo_title,
        'page_meta_description': seo_description,
        'cover_image': cover_image,
    }


@staff_member_required
@require_http_methods(['GET', 'POST'])
def page_edit(request, page_id=None):  # noqa: PLR0912 — flat validate→save view
    """Create (page_id is None) or edit a CMS Page."""
    from plugins.installed.cms.models import Page

    page = get_object_or_404(Page, pk=page_id) if page_id else None
    creating = page is None

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        slug = slugify(request.POST.get('slug') or title)[:200]
        excerpt = (request.POST.get('excerpt') or '').strip()[:300]
        body = request.POST.get('body') or ''
        state = request.POST.get('state') or 'draft'
        layout = request.POST.get('layout') or 'default'
        publish_at = _parse_publish_at(request.POST.get('publish_at'))

        if state not in {c[0] for c in Page.STATE_CHOICES}:
            state = 'draft'
        if layout not in {c[0] for c in Page.LAYOUT_CHOICES}:
            layout = 'default'

        errors = []
        if not title:
            errors.append('Title is required.')
        if not slug:
            errors.append('A slug is required (letters, numbers, hyphens).')
        else:
            clash = Page.objects.filter(slug=slug)
            if page:
                clash = clash.exclude(pk=page.pk)
            if clash.exists():
                errors.append(f'The slug “{slug}” is already used by another page.')

        if errors:
            for err in errors:
                messages.error(request, err)
            draft = page or Page()
            draft.title, draft.slug, draft.excerpt = title, slug, excerpt
            draft.body, draft.state, draft.layout, draft.publish_at = (
                body,
                state,
                layout,
                publish_at,
            )
            ctx = _page_form_context(request, draft, creating=creating)
            # Carry the POSTed cover + SEO fields into the re-render — the
            # context derives them from saved state, which would silently
            # drop a just-uploaded cover (orphaning the Media asset) on a
            # validation error like a slug clash.
            ctx.update(
                cover_image=(request.POST.get('cover_image') or '').strip()[:600],
                page_meta_title=(request.POST.get('meta_title') or '').strip()[:255],
                page_meta_description=(request.POST.get('meta_description') or '').strip()[:500],
            )
            return render(request, 'cms/dashboard/page_form.html', ctx)

        if page is None:
            page = Page()
            if request.user.is_authenticated:
                page.author = request.user
        page.title, page.slug, page.excerpt = title, slug, excerpt
        page.body, page.state, page.layout, page.publish_at = body, state, layout, publish_at
        # Cover image (journal OG/cover) lives in metadata; preserve the rest
        # (e.g. category='journal').
        cover = (request.POST.get('cover_image') or '').strip()[:600]
        meta = dict(page.metadata or {})
        if cover:
            meta['cover'] = cover
        else:
            meta.pop('cover', None)
        page.metadata = meta
        page.save()
        _save_page_seo(
            page, request.POST.get('meta_title', ''), request.POST.get('meta_description', '')
        )
        messages.success(request, f'Saved “{page.title}”.')
        return redirect(_PAGES_LIST_URL)

    return render(
        request,
        'cms/dashboard/page_form.html',
        _page_form_context(request, page, creating=creating),
    )


@staff_member_required
@require_http_methods(['POST'])
def page_duplicate(request, page_id):
    from plugins.installed.cms.models import Page

    src = get_object_or_404(Page, pk=page_id)
    base = f'{src.slug}-copy'
    slug, n = base, 2
    while Page.objects.filter(slug=slug).exists():
        slug, n = f'{base}-{n}', n + 1
    dup = Page(
        title=f'{src.title} (copy)',
        slug=slug,
        excerpt=src.excerpt,
        body=src.body,
        layout=src.layout,
        state='draft',
        metadata=dict(src.metadata or {}),
        author=request.user if request.user.is_authenticated else None,
    )
    dup.save()
    messages.success(request, f'Duplicated as “{dup.title}” (draft).')
    return redirect(f'/dashboard/cms/pages/{dup.pk}/edit/')


@staff_member_required
@require_http_methods(['POST'])
def page_delete(request, page_id):
    from plugins.installed.cms.models import Page

    page = get_object_or_404(Page, pk=page_id)
    title = page.title
    page.delete()
    messages.success(request, f'Deleted “{title}”.')
    return redirect(_PAGES_LIST_URL)


# ──────────────────────────────────────────────────────────────────────────
# Menu builder — header + mobile nav, editable from the dashboard.
# Wired into the storefront via cms.context_processors.nav_menus; the theme
# renders header_menu / mobile_menu (mega_* kinds drive the Genres/Authors
# panels). menus_list (above) links here.
# ──────────────────────────────────────────────────────────────────────────

_MENUS_LIST_URL = '/dashboard/apps/cms/menus/'


def _bust_menu_cache():
    try:
        from django.core.cache import cache

        cache.delete_many(['storefront:nav_menu:header:v1', 'storefront:nav_menu:mobile:v1'])
    except Exception:  # noqa: BLE001, S110 — cache bust is best-effort
        pass


def _menu_item_action(request, menu, action):
    """Handle the per-item POST actions (add/edit/delete/move) for menu_edit."""
    from plugins.installed.cms.models import MenuItem

    valid_kinds = {c[0] for c in MenuItem.KIND_CHOICES}
    item = menu.items.filter(pk=request.POST.get('item_id')).first()

    if action == 'add_item':
        label = (request.POST.get('item_label') or '').strip()[:120]
        if not label:
            messages.error(request, 'An item needs a label.')
            return
        kind = request.POST.get('item_kind') or MenuItem.KIND_LINK
        last = menu.items.order_by('-order').first()
        MenuItem.objects.create(
            menu=menu,
            label=label,
            url=(request.POST.get('item_url') or '').strip()[:500],
            kind=kind if kind in valid_kinds else MenuItem.KIND_LINK,
            target='_blank' if request.POST.get('item_new_tab') == 'on' else '_self',
            order=(last.order + 10) if last else 10,
        )
        messages.success(request, f'Added “{label}”.')

    elif action == 'edit_item' and item:
        item.label = (request.POST.get('item_label') or '').strip()[:120] or item.label
        kind = request.POST.get('item_kind') or item.kind
        if kind in valid_kinds:
            item.kind = kind
        item.url = (request.POST.get('item_url') or '').strip()[:500]
        item.target = '_blank' if request.POST.get('item_new_tab') == 'on' else '_self'
        item.save()
        messages.success(request, 'Item updated.')

    elif action == 'delete_item' and item:
        item.delete()
        messages.success(request, 'Item removed.')

    elif action == 'move_item' and item:
        siblings = list(menu.items.order_by('order', 'id'))
        idx = siblings.index(item)
        direction = request.POST.get('direction')
        swap = None
        if direction == 'up' and idx > 0:
            swap = siblings[idx - 1]
        elif direction == 'down' and idx < len(siblings) - 1:
            swap = siblings[idx + 1]
        if swap is not None:
            item.order, swap.order = swap.order, item.order
            MenuItem.objects.bulk_update([item, swap], ['order'])


@staff_member_required
def menu_edit(request, menu_id=None):
    """Create (menu_id None) or edit a Menu + its items. POST dispatches on an
    ``action`` field so the whole editor lives behind one route."""
    from plugins.installed.cms.models import Menu, MenuItem

    menu = get_object_or_404(Menu, pk=menu_id) if menu_id else None

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'save_menu':
            key = slugify(request.POST.get('key') or '')[:80]
            label = (request.POST.get('label') or '').strip()[:120]
            if not key or not label:
                messages.error(request, 'Both a key and a label are required.')
                return redirect(request.path)
            clash = Menu.objects.filter(key=key)
            if menu:
                clash = clash.exclude(pk=menu.pk)
            if clash.exists():
                messages.error(request, f'The key “{key}” is already used by another menu.')
                return redirect(request.path)
            menu = menu or Menu()
            menu.key, menu.label = key, label
            menu.is_active = request.POST.get('is_active') == 'on'
            menu.save()
            _bust_menu_cache()
            messages.success(request, f'Saved “{menu.label}”.')
            return redirect(f'/dashboard/cms/menus/{menu.pk}/edit/')

        if menu is None:  # item actions need an existing menu
            return redirect(_MENUS_LIST_URL)
        _menu_item_action(request, menu, action)
        _bust_menu_cache()
        return redirect(f'/dashboard/cms/menus/{menu.pk}/edit/')

    items = list(menu.items.filter(parent__isnull=True).order_by('order', 'id')) if menu else []
    return render(
        request,
        'cms/dashboard/menu_form.html',
        {
            'menu': menu,
            'items': items,
            'kind_choices': MenuItem.KIND_CHOICES,
            'creating': menu is None,
            'active_nav': 'cms',
        },
    )


@staff_member_required
@require_http_methods(['POST'])
def menu_delete(request, menu_id):
    from plugins.installed.cms.models import Menu

    menu = get_object_or_404(Menu, pk=menu_id)
    label = menu.label
    menu.delete()
    _bust_menu_cache()
    messages.success(request, f'Deleted “{label}”.')
    return redirect(_MENUS_LIST_URL)
