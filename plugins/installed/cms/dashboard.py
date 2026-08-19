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
        from plugins.registry import app_registry
    except Exception:  # noqa: BLE001
        return []
    out = []
    for plugin in app_registry.active_plugins():
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


def _apply_editorial_metadata(meta: dict, post) -> dict:
    """Fold the page form's metadata-backed controls into ``meta``: the
    cover image, the Publish-to-Journal toggle, author, author profile
    links (sameAs), and cited sources. Author links + sources are stored
    as clean lists so the journal Article JSON-LD reads them safely."""

    def _lines(name):
        return [ln.strip() for ln in (post.get(name) or '').splitlines() if ln.strip()]

    cover = (post.get('cover_image') or '').strip()[:600]
    if cover:
        meta['cover'] = cover
    else:
        meta.pop('cover', None)

    if post.get('is_journal'):
        meta['category'] = 'journal'
    elif meta.get('category') == 'journal':
        meta.pop('category', None)

    author = (post.get('author') or '').strip()[:120]
    if author:
        meta['author'] = author
    else:
        meta.pop('author', None)

    for field in ('author_same_as', 'citations'):
        vals = _lines(field)
        if vals:
            meta[field] = vals
        else:
            meta.pop(field, None)
    return meta


def _meta_list_text(value) -> str:
    """A metadata list (author_same_as / citations) → newline-joined text for
    the textarea. Tolerates a scalar string set via raw JSON."""
    if isinstance(value, (list, tuple)):
        return '\n'.join(str(v) for v in value if v)
    return str(value) if value else ''


def _page_form_context(request, page, *, creating):
    from plugins.installed.cms.models import Page

    meta = (getattr(page, 'metadata', None) or {}) if page else {}
    return {
        'page': page,
        'creating': creating,
        'state_choices': Page.STATE_CHOICES,
        'layout_choices': Page.LAYOUT_CHOICES,
        'form_action': request.path,
        'active_nav': 'cms',
        'cover_image': meta.get('cover', ''),
        # Editorial (journal) controls — Page.metadata backed.
        'is_journal': meta.get('category') == 'journal',
        'page_author': meta.get('author', ''),
        'author_same_as_text': _meta_list_text(meta.get('author_same_as')),
        'citations_text': _meta_list_text(meta.get('citations')),
        'extra_cards': _page_form_cards(request, page),
    }


def _page_form_cards(request, page) -> list[str]:
    """Cards contributed into the page form (PAGE_FORM_CARDS) — the SEO panel
    among them. Rendered here so cms never imports the contributing app; a
    broken card costs its own card, not the editor."""
    from django.template.loader import render_to_string
    from morpheus.core import MorpheusEvents, hook_registry

    out: list[str] = []
    cards = hook_registry.filter(
        MorpheusEvents.PAGE_FORM_CARDS, value=[], page=page, request=request
    )
    for card in sorted(cards or [], key=lambda c: c.get('order', 100)):
        tpl = card.get('template')
        if not tpl:
            continue
        try:
            out.append(
                render_to_string(tpl, {**card.get('context', {}), 'page': page}, request=request)
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.cms').warning(
                'cms: page_form_card render failed (%s)', tpl, exc_info=True
            )
    return out


@staff_member_required
@require_http_methods(['GET', 'POST'])
def page_edit(request, page_id=None):  # noqa: PLR0912, PLR0915 — flat validate→save view
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
            # Carry the POSTed cover + editorial fields into the re-render — the
            # context derives them from state, which would silently drop a
            # just-uploaded cover (orphaning the Media asset) or the journal
            # toggle on a validation error like a slug clash. The SEO panel
            # itself re-prefills from request.POST (takes_context).
            draft.metadata = _apply_editorial_metadata(dict(draft.metadata or {}), request.POST)
            ctx = _page_form_context(request, draft, creating=creating)
            return render(request, 'cms/dashboard/page_form.html', ctx)

        if page is None:
            page = Page()
            if request.user.is_authenticated:
                page.author = request.user
        page.title, page.slug, page.excerpt = title, slug, excerpt
        page.body, page.state, page.layout, page.publish_at = body, state, layout, publish_at
        # Cover image (journal OG/cover) + editorial fields live in metadata.
        page.metadata = _apply_editorial_metadata(dict(page.metadata or {}), request.POST)
        page.save()
        # Let contributors persist their own page-form fields (the SEO panel,
        # among them). Fired rather than imported: cms does not depend on seo,
        # and a disabled seo app should simply have no subscriber.
        from morpheus.core import MorpheusEvents, hook_registry

        hook_registry.fire(
            MorpheusEvents.PAGE_FORM_SAVED,
            page=page,
            post=request.POST,
            files=request.FILES,
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
