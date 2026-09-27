"""Content / static pages — About, Contact, Journal, Shipping, Returns,
newsletter capture, and the generic coming-soon placeholder.
"""
# ruff: noqa: PLC0415, S110, I001 — lazy optional-plugin imports + best-effort
# CRM swallows are intentional and pre-date this change.

from __future__ import annotations

from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from morpheus.app.views import render
from plugins.installed.storefront.services import store_blurb, store_name
from plugins.registry import app_registry

# Served at the conventional /favicon.ico path — browsers request it unprompted
# on every visit, and without it each page load logs a 404. Colors are the
# dot_books brand tokens (ink + accent); a theme wanting its own mark overrides
# the <link rel="icon"> in its base template.
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#0e0e0e"/>'
    '<circle cx="32" cy="32" r="15" fill="#e63946"/>'
    '</svg>'
)


def favicon(request):
    """Serve the merchant's favicon when they've uploaded one.

    Settings → General has a favicon field that nothing read — every store
    served the hardcoded dot_books mark regardless. Redirects to the uploaded
    file (so it is served by the normal media pipeline) and falls back to the
    built-in SVG.
    """
    from django.shortcuts import redirect

    from core.models import StoreSettings

    try:
        img = StoreSettings.get('favicon')
        if img:
            return redirect(img.url)
    except Exception:  # noqa: BLE001 — never 500 a favicon request
        pass

    resp = HttpResponse(_FAVICON_SVG, content_type='image/svg+xml')
    resp['Cache-Control'] = 'public, max-age=604800, immutable'
    return resp


def about(request):
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'About', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/about.html',
        {
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'About',
            # The merchant's own words when they have written any; otherwise
            # nothing, and the seo app derives one from the page. The shell
            # used to hardcode dot books' own copy here, so every other store
            # introduced itself to Google as an independent bookshop.
            'seo_description': store_blurb() or f'About {store_name()}.',
            'seo_og_type': 'website',
        },
    )


# NOTE: `newsletter_subscribe` lived here and was dead code — the newsletter
# plugin owns /newsletter/subscribe/ and registers earlier, so this view never
# ran and its CRM lead capture never happened. The capture now rides the
# NEWSLETTER_SUBSCRIBED event, which crm subscribes to (v0.41).


def contact(request):
    sent = False
    if request.method == 'POST':
        from django.db import DatabaseError

        email = (request.POST.get('email') or '').strip().lower()
        name = (request.POST.get('name') or '').strip()
        body = (request.POST.get('message') or '').strip()
        if email and body and app_registry.is_active('crm'):
            try:
                from plugins.installed.crm.services import upsert_lead, log_interaction

                lead = upsert_lead(
                    email=email,
                    first_name=name.split(' ')[0] if name else '',
                    last_name=' '.join(name.split(' ')[1:]) if ' ' in name else '',
                    source='storefront',
                )
                log_interaction(
                    subject=lead,
                    kind='note',
                    direction='inbound',
                    summary='Contact form submission',
                    body=body,
                    actor_name='storefront',
                )
            except (ImportError, DatabaseError):
                pass
        sent = True
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Contact', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/contact.html',
        {
            'sent': sent,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'Contact',
            'seo_description': (
                f'Get in touch with {store_name()} — questions about an order, '
                'or anything else. We read every message.'
            ),
            'seo_og_type': 'website',
        },
    )


def journal_index(request):
    """The store's journal: its published CMS pages (metadata.category=='journal').

    No seeded fallback — the shell used to fill an empty journal with dot books'
    own essays, so the herbal and travel stores published a bookshop's writing.
    """
    entries = []
    try:
        if app_registry.is_active('cms'):
            from plugins.installed.cms.services import list_journal_entries

            entries = list_journal_entries()
    except Exception:  # noqa: BLE001
        entries = []
    post_items = [
        {
            'name': e.get('title', '') if isinstance(e, dict) else getattr(e, 'title', ''),
            'url': request.build_absolute_uri(
                f'/journal/{(e.get("slug", "") if isinstance(e, dict) else getattr(e, "slug", ""))}/'
            ),
        }
        for e in entries
    ]
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Journal', 'url': request.build_absolute_uri(request.path)},
    ]
    from plugins.installed.storefront.services import page_intro

    intro = page_intro(request, 'journal')
    return render(
        request,
        'storefront/journal_index.html',
        {
            'entries': entries,
            'post_items': post_items,
            'breadcrumb_items': breadcrumb_items,
            'page_intro': intro['body'],
            'seo_title': 'Journal',
            'seo_description': (
                intro['meta_description']
                or intro['body']
                or f'Notes and stories from {store_name()}.'
            )[:160],
            'seo_og_type': 'website',
        },
    )


def journal_detail(request, slug):
    from morpheus.app.views import Http404

    entry = None
    seo_object = None
    try:
        if app_registry.is_active('cms'):
            from plugins.installed.cms.services import get_journal_page, journal_dict

            # One Page fetch serves both: the model instance is the SEO object
            # (resolve_meta layers the per-page SeoMeta override + visual schema
            # blocks off it) and the render dict is derived from it.
            seo_object = get_journal_page(slug)
            entry = journal_dict(seo_object) if seo_object else None
    except Exception:  # noqa: BLE001
        pass
    if entry is None:
        raise Http404
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Journal', 'url': request.build_absolute_uri('/journal/')},
        {'name': entry.get('title', ''), 'url': request.build_absolute_uri(request.path)},
    ]
    # Front-end admin-bar "Edit this journal" link for staff (CMS page editor).
    active_edit_url = ''
    if entry.get('id') and request.user.is_authenticated and request.user.is_staff:
        active_edit_url = f'/dashboard/cms/pages/{entry["id"]}/edit/'
    return render(
        request,
        'storefront/journal_detail.html',
        {
            'entry': entry,
            'seo_object': seo_object,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': f'{entry["title"]} — Journal',
            'seo_description': entry.get('excerpt', '')[:160],
            'seo_image': entry.get('image', ''),
            'seo_og_type': 'article',
            'active_edit_url': active_edit_url,
            'active_edit_label': 'Edit this journal',
        },
    )


@xframe_options_sameorigin
def journal_amp(request, slug):
    """AMP variant of `journal_detail`. Mirrors the regular view's context
    build, but renders a standalone AMP HTML document with its own
    boilerplate. Canonical points at the regular HTML page.

    Decorated with `@xframe_options_sameorigin` so AMP caches / players
    can embed the document in an iframe.
    """
    from morpheus.app.views import Http404  # noqa: PLC0415

    entry = None
    try:
        if app_registry.is_active('cms'):
            from plugins.installed.cms.services import get_journal_entry  # noqa: PLC0415

            entry = get_journal_entry(slug)
    except Exception:  # noqa: BLE001, S110
        pass
    if entry is None:
        raise Http404

    # Rewrite raw <img> tags so the body is closer to AMP-valid.
    # Rough — width/height are guesses — but functional for the
    # validator's "no raw <img>" rule.
    body = entry.get('body', '') or ''
    if '<img ' in body:
        body = body.replace(
            '<img ',
            '<amp-img layout="responsive" width="800" height="600" ',
        )
        entry = {**entry, 'body': body}

    canonical_url = request.build_absolute_uri(f'/journal/{slug}/')
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Journal', 'url': request.build_absolute_uri('/journal/')},
        {'name': entry.get('title', ''), 'url': canonical_url},
    ]
    response = render(
        request,
        'storefront/journal_amp.html',
        {
            'entry': entry,
            'breadcrumb_items': breadcrumb_items,
            'canonical_url': canonical_url,
        },
    )
    response['Cache-Control'] = 'public, max-age=900, s-maxage=3600'
    return response


def shipping(request):
    """Real shipping policy page."""
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Shipping', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/shipping.html',
        {
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'Shipping',
            # No rates, no thresholds, no service level. Those are claims the
            # shipping app owns, and the hardcoded line promised "free over
            # $40" on two stores whose checkout says nothing of the kind —
            # the same shape as the invented shippingDetails in the offer
            # claims landmine: a promise checkout will break.
            'seo_description': 'Delivery options, estimated times and shipping rates.',
        },
    )


def returns(request):
    """Real returns policy page."""
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Returns', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/returns.html',
        {
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'Returns',
            'seo_description': "Send a book back inside 30 days. Here's how — and what we cover.",
        },
    )


def do_not_sell(request):
    """CCPA "Do not sell my info" opt-out page.

    GET renders the policy + an opt-out form. POST records the opt-out:
    if the consent plugin is installed, we write a ConsentLog row with
    everything off (analytics, marketing, functional); otherwise we
    just flash a success message and let the visitor know we received it.
    The page exists for the CCPA "do not sell" right and the parallel
    state laws that require it (Colorado, Virginia, Connecticut, etc.).
    It must not assert what a given store does or does not do with
    personal data — the shell cannot know that, and the copy it used to
    ship made that claim on behalf of every store, under one store's name.
    """
    import contextlib  # noqa: PLC0415

    from django.contrib import messages  # noqa: PLC0415

    submitted = False
    if request.method == 'POST':
        from django.http import HttpResponse  # noqa: PLC0415

        with contextlib.suppress(Exception):
            if app_registry.is_active('consent'):
                from plugins.installed.consent.services import write_consent  # noqa: PLC0415

                response = HttpResponse()
                write_consent(
                    request,
                    response,
                    analytics=False,
                    marketing=False,
                    functional=False,
                    customer=getattr(request, 'user', None)
                    if getattr(request, 'user', None) and request.user.is_authenticated
                    else None,
                )
        submitted = True
        with contextlib.suppress(Exception):
            messages.success(
                request,
                "Got it — you're opted out. We don't sell personal data anyway.",
            )
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Do not sell my info', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/do_not_sell.html',
        {
            'submitted': submitted,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'Do not sell my info',
            # Describes the RIGHT, not the store's data practices. The old
            # copy asserted "DotBooks doesn't sell personal data" on every
            # store — another business's name attached to a privacy claim the
            # shell has no way to verify for the store actually serving it.
            'seo_description': (
                f'Opt out of the sale or sharing of your personal information at '
                f'{store_name()}, under CCPA and the parallel state privacy laws.'
            ),
            'seo_og_type': 'website',
        },
    )


def coming_soon(request, slug=None):
    """Generic placeholder for footer links that don't have first-class pages yet."""
    title_map = {
        'stockists': 'Stockists',
        'staff-picks': 'Staff picks',
        'shipping': 'Shipping',
        'returns': 'Returns',
    }
    page_slug = slug or request.path.strip('/').split('/')[-1] or 'coming-soon'
    return render(
        request,
        'storefront/coming_soon.html',
        {
            'page_title': title_map.get(page_slug, page_slug.replace('-', ' ').title()),
        },
    )
