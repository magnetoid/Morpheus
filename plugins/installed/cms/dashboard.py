"""CMS dashboard pages."""

# ruff: noqa: PLC0415 — model imports are lazy (load-order safe), matching siblings.
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


@staff_member_required
def pages_list(request):
    rows = _safe_list('cms.Page')
    return render(request, 'cms/dashboard/pages.html', {'rows': rows, 'active_nav': 'cms'})


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


def _page_form_context(request, page, *, creating):
    from plugins.installed.cms.models import Page

    return {
        'page': page,
        'creating': creating,
        'state_choices': Page.STATE_CHOICES,
        'layout_choices': Page.LAYOUT_CHOICES,
        'form_action': request.path,
        'active_nav': 'cms',
    }


@staff_member_required
@require_http_methods(['GET', 'POST'])
def page_edit(request, page_id=None):
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
            return render(
                request,
                'cms/dashboard/page_form.html',
                _page_form_context(request, draft, creating=creating),
            )

        if page is None:
            page = Page()
            if request.user.is_authenticated:
                page.author = request.user
        page.title, page.slug, page.excerpt = title, slug, excerpt
        page.body, page.state, page.layout, page.publish_at = body, state, layout, publish_at
        page.save()
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
