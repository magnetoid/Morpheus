"""Content / static pages — About, Contact, Journal, Shipping, Returns,
newsletter capture, and the generic coming-soon placeholder.
"""
# ruff: noqa: PLC0415, S110, I001 — lazy optional-plugin imports + best-effort
# CRM swallows are intentional and pre-date this change.

from __future__ import annotations

from django.views.decorators.clickjacking import xframe_options_sameorigin

from morpheus.views import render

# Hardcoded journal entries — TODO: extract to a CMS plugin with editable posts.
_JOURNAL_ENTRIES = [
    {
        'slug': 'a-short-note-on-patience',
        'title': 'A short note on patience and the long sentence',
        'date_label': 'April · 4 min read',
        'excerpt': 'On Cusk, on Sebald, on the way a long paragraph teaches you how to wait.',
        'body': (
            "There's a particular pleasure in a sentence that takes a breath you didn't know "
            'you had to give it. Cusk does this. Sebald does this. The reader is asked to slow '
            'down — to hold a thought in suspension — and in that suspension something settles. '
            'We carry a few of these books on the shelf this season because we believe in the '
            'case for the long take.'
        ),
        'is_html': False,
    },
    {
        'slug': 'why-we-dont-carry-books-we-havent-read',
        'title': "Why we don't carry books we haven't read",
        'date_label': 'April · 3 min read',
        'excerpt': "A diary of how the shelf gets curated, and why it's a small one on purpose.",
        'body': (
            'Every title in the shop has been read by at least one of us before it makes it to '
            "the shelf. That's both a constraint and a promise. The constraint: the shop will "
            'always be small. The promise: if a book is here, it earned the spot. We trade '
            'breadth for trust.'
        ),
        'is_html': False,
    },
    {
        'slug': 'the-case-for-the-small-press',
        'title': 'The case for the small press, made in numbers',
        'date_label': 'April · 6 min read',
        'excerpt': "Three years of receipts, and what they say about who's actually publishing the work that lasts.",
        'body': (
            'Pull three years of receipts and the picture is unambiguous: the books that customers '
            'come back to, the books they recommend to a friend, the books they buy a second copy '
            "of — they're disproportionately from independent presses. Not because indie is "
            'automatically better, but because the editors there have time to be wrong on purpose.'
        ),
        'is_html': False,
    },
]


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
            'seo_title': 'About — dot books',
            'seo_description': 'dot books is an independent bookshop, run by readers, for readers. We stock titles from independent presses around the world.',
            'seo_og_type': 'website',
        },
    )


def newsletter_subscribe(request):
    """Capture a footer newsletter signup as a CRM Lead.
    JSON when called via fetch; HTML thanks page otherwise."""
    from django.http import HttpResponseNotAllowed, JsonResponse

    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    email = (request.POST.get('email') or '').strip().lower()
    is_xhr = request.headers.get(
        'X-Requested-With', ''
    ).lower() == 'fetch' or 'application/json' in request.headers.get('Accept', '')

    if not email or '@' not in email:
        if is_xhr:
            return JsonResponse({'ok': False, 'error': 'Please enter a valid email.'}, status=400)
        return render(
            request,
            'storefront/newsletter_thanks.html',
            {
                'email': '',
                'error': 'Please enter a valid email.',
            },
        )

    try:
        from plugins.installed.crm.services import upsert_lead

        upsert_lead(email=email, source='newsletter')
    except Exception:  # noqa: BLE001 — CRM is optional
        pass

    if is_xhr:
        return JsonResponse({'ok': True, 'email': email})
    return render(request, 'storefront/newsletter_thanks.html', {'email': email, 'error': ''})


def contact(request):
    sent = False
    if request.method == 'POST':
        from plugins.installed.crm.services import upsert_lead, log_interaction
        from django.db import DatabaseError

        email = (request.POST.get('email') or '').strip().lower()
        name = (request.POST.get('name') or '').strip()
        body = (request.POST.get('message') or '').strip()
        if email and body:
            try:
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
            'seo_title': 'Contact — dot books',
            'seo_description': 'Get in touch with dot books. Recommendations, suggestions, and help with orders — we read every message.',
            'seo_og_type': 'website',
        },
    )


def journal_index(request):
    """Prefer CMS pages (metadata.category=='journal'); fall back to seeded entries."""
    try:
        from plugins.installed.cms.services import list_journal_entries

        cms_entries = list_journal_entries()
    except Exception:  # noqa: BLE001
        cms_entries = []
    entries = cms_entries or _JOURNAL_ENTRIES
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
            'seo_title': 'Journal — dot books',
            'seo_description': (
                intro['meta_description']
                or intro['body']
                or "Notes, essays, short pieces from the booksellers. Updated when there's something to say."
            )[:160],
            'seo_og_type': 'website',
        },
    )


def journal_detail(request, slug):
    from morpheus.views import Http404

    entry = None
    seo_object = None
    try:
        from plugins.installed.cms.services import get_journal_page, journal_dict

        # One Page fetch serves both: the model instance is the SEO object
        # (resolve_meta layers the per-page SeoMeta override + visual schema
        # blocks off it) and the render dict is derived from it. None for the
        # seeded fallback entries (they degrade to the fallbacks).
        seo_object = get_journal_page(slug)
        entry = journal_dict(seo_object) if seo_object else None
    except Exception:  # noqa: BLE001
        pass
    if entry is None:
        entry = next((e for e in _JOURNAL_ENTRIES if e['slug'] == slug), None)
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
            'seo_title': f'{entry["title"]} — Journal — dot books',
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
    from morpheus.views import Http404  # noqa: PLC0415

    entry = None
    try:
        from plugins.installed.cms.services import get_journal_entry  # noqa: PLC0415

        entry = get_journal_entry(slug)
    except Exception:  # noqa: BLE001, S110
        pass
    if entry is None:
        entry = next((e for e in _JOURNAL_ENTRIES if e['slug'] == slug), None)
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
            'seo_title': 'Shipping — dot books',
            'seo_description': 'How dot books ships your order — tracked, signed-for, free over $40. Domestic + international rates.',
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
            'seo_title': 'Returns — dot books',
            'seo_description': "Send a book back inside 30 days. Here's how — and what we cover.",
        },
    )


def do_not_sell(request):
    """CCPA "Do not sell my info" opt-out page.

    GET renders the policy + an opt-out form. POST records the opt-out:
    if the consent plugin is installed, we write a ConsentLog row with
    everything off (analytics, marketing, functional); otherwise we
    just flash a success message and let the visitor know we received it.
    DotBooks does not sell personal data — this page exists for the
    CCPA "do not sell" right and for the parallel state laws that
    require it (Colorado, Virginia, Connecticut, etc.).
    """
    import contextlib  # noqa: PLC0415

    from django.contrib import messages  # noqa: PLC0415

    submitted = False
    if request.method == 'POST':
        from django.http import HttpResponse  # noqa: PLC0415

        with contextlib.suppress(Exception):
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
            'seo_title': 'Do not sell my info — dot books',
            'seo_description': (
                "DotBooks doesn't sell personal data. If you'd like to opt out anyway "
                'under CCPA, this is the page.'
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
