"""CMS storefront views — page resolver + form submission."""

from __future__ import annotations

from morpheus.app.views import (
    Http404,
    csrf_protect,
    get_object_or_404,
    messages,
    redirect,
    render,
    require_http_methods,
)


def page_view(request, slug: str):
    from morpheus.core import MorpheusEvents, hook_registry
    from plugins.installed.cms.services import get_live_page

    page = get_live_page(slug)
    if page is None:
        raise Http404
    meta = page.metadata or {}
    default_path = f'/p/{slug}/'
    # `/sr` on a Serbian request: a redirect that drops it sends the visitor
    # back to English, and tells a crawler the two trees are one page.
    prefix = request.path[: -len(default_path)] if request.path.endswith(default_path) else ''
    # Journal posts have a canonical /journal/<slug>/ route with full Article
    # treatment (BlogPosting JSON-LD + article:* OG). Serving the same content
    # at the generic /p/<slug>/ URL is a duplicate page that would advertise
    # og:type=article with no backing article metadata — 301 it to the
    # canonical route instead.
    if meta.get('category') == 'journal':
        return redirect(f'{prefix}/journal/{slug}/', permanent=True)
    # A page another app renders at a route of its own (storefront's /shipping/
    # and /returns/) has ONE url: dotbooks served its shipping policy at both
    # /shipping/ and /p/shipping/ under one title.
    claimed = hook_registry.filter(MorpheusEvents.CMS_PAGE_PATH, default_path, page=page)
    if isinstance(claimed, str) and claimed.startswith('/') and claimed != default_path:
        return redirect(f'{prefix}{claimed}', permanent=True)

    # Staff admin-bar deep-link: edit this page in the dashboard.
    active_edit_url = ''
    if request.user.is_authenticated and request.user.is_staff:
        from django.urls import reverse

        active_edit_url = reverse('cms_dashboard:page_edit', kwargs={'page_id': page.pk})

    # SEO wiring: pass the Page as seo_object so resolve_meta layers the
    # merchant's saved SeoMeta (title/description/canonical/robots/OG) and
    # visual schema blocks — without this every single page rendered the
    # site-default <title>. seo_title/description/image are the fallbacks
    # used only when the SeoMeta row leaves a field blank.
    from morpheus.core import absolutize

    cover = absolutize(
        (meta.get('cover') or meta.get('image') or meta.get('og_image') or '').strip()
    )
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': page.title, 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'cms/page.html',
        {
            'page': page,
            'seo_object': page,
            'seo_title': page.title,
            'seo_description': page.excerpt or '',
            'seo_image': cover,
            'seo_og_type': 'website',
            'breadcrumb_items': breadcrumb_items,
            'active_edit_url': active_edit_url,
            'active_edit_label': 'Edit page',
        },
    )


@csrf_protect
@require_http_methods(['POST'])
def form_submit(request, key: str):
    from plugins.installed.cms.models import Form
    from plugins.installed.cms.services import submit_form

    form = get_object_or_404(Form, key=key, is_active=True)
    submit_form(form=form, payload=dict(request.POST.items()), request=request)
    messages.success(request, form.success_message)
    return redirect(request.META.get('HTTP_REFERER', '/'))
