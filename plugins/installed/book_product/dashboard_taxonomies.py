"""Dashboard: Book taxonomies — per-term SEO editing.

Lists the book taxonomies (Authors, Publishers, Series, Imprints) and their
terms (derived from BookProduct values), and lets staff edit each term's
landing-page SEO + intro blurb + image — the same way Categories/Collections
are edited. A BookTaxonomyTerm row is created only when a term is customized.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify

_TAXONOMIES = [
    ('author', 'Authors', '/author/'),
    ('publisher', 'Publishers', '/publisher/'),
    ('series', 'Series', '/series/'),
    ('imprint', 'Imprints', '/imprint/'),
]
_LABELS = {k: label for k, label, _ in _TAXONOMIES}
_URL_PREFIX = {k: prefix for k, _, prefix in _TAXONOMIES}
# Curated taxonomies (real models, unlike the auto-discovered ones above): same
# dashboard UX as authors/publishers, plus add/delete since they're hand-managed.
_CURATED = [
    ('genre', 'Genre', 'Genres', '/genre/', '/genres/'),
    ('topic', 'Topic', 'Topics', '/topic/', '/topics/'),
]
_CURATED_LABELS = {k: singular for k, singular, *_ in _CURATED}


def _curated_model(kind):
    from plugins.installed.book_product.models import Genre, Topic

    return {'genre': Genre, 'topic': Topic}.get(kind)


def _curated_groups():
    from django.db.models import Count, Q
    from django.urls import reverse

    from plugins.installed.book_product.tasks import MAX_BATCH, missing_copy_queryset

    groups = []
    for kind, _singular, label, prefix, root_url in _CURATED:
        model = _curated_model(kind)
        terms = []
        # Annotate the book count in one query — `obj.books.count()` per row was
        # a query per term, i.e. ~1500 of them on the Topics group alone.
        rows = model.objects.annotate(
            _books=Count('books', filter=Q(books__product__status='active'))
        )
        for obj in rows:
            terms.append(
                {
                    'name': obj.name,
                    'slug': obj.slug,
                    'count': obj._books,
                    'has_seo': bool(obj.description or obj.meta_title or obj.meta_description),
                    'page_url': f'{prefix}{obj.slug}/',
                    'edit_url': reverse(
                        'book_product_dashboard:curated_edit', args=[kind, obj.slug]
                    ),
                    'delete_url': reverse(
                        'book_product_dashboard:curated_delete', args=[kind, obj.slug]
                    ),
                }
            )
        # Counted with the backfill's OWN predicate, so the button can never
        # promise work the task won't do.
        missing = missing_copy_queryset(kind).count()
        groups.append(
            {
                'key': kind,
                'label': label,
                'terms': terms,
                'is_curated': True,
                'root_url': root_url,
                # Curated kinds get a landing-page editor too — their index
                # intro lives in BookTaxonomyRoot exactly like /authors/.
                'root_edit_url': reverse('book_product_dashboard:taxonomy_root_edit', args=[kind]),
                'add_url': reverse('book_product_dashboard:curated_add', args=[kind]),
                'backfill_url': reverse('book_product_dashboard:curated_backfill', args=[kind]),
                # Terms that carry books but have no intro — the backfill's
                # workload. `batch` is what ONE run actually writes (the task
                # caps each run); the button states that number rather than the
                # full backlog, so a 1500-term kind doesn't promise 1500.
                'missing_copy': missing,
                'backfill_batch': min(missing, MAX_BATCH),
            }
        )
    return groups


# Storefront listing page (the whole taxonomy kind) per key. Author details
# live in the storefront app at /author/<slug>/, so its index is /authors/.
_ROOT_URL = {
    'author': '/authors/',
    'publisher': '/publishers/',
    'series': '/series/',
    'imprint': '/imprints/',
    'genre': '/genres/',
    'topic': '/topics/',
}
# Plural, page-facing label per root kind — the curated ones carry theirs in
# _CURATED (singular is used for term editing, plural titles the index page).
_ROOT_LABELS = {**_LABELS, **{k: plural for k, _singular, plural, *_ in _CURATED}}


@staff_member_required
def taxonomies_list(request: HttpRequest) -> HttpResponse:
    from plugins.installed.book_product.compat import distinct_values, product_ids_for
    from plugins.installed.book_product.models import BookTaxonomyTerm

    customized = {(t.taxonomy, t.slug) for t in BookTaxonomyTerm.objects.all()}
    # Curated taxonomies (Genre, Topic) lead — they're the browse axis now.
    groups = _curated_groups()
    for key, label, url_prefix in _TAXONOMIES:
        terms = []
        for name in distinct_values(key):
            slug = slugify(name)
            terms.append(
                {
                    'name': name,
                    'slug': slug,
                    'count': len(product_ids_for(key, name)),
                    'has_seo': (key, slug) in customized,
                    'page_url': f'{url_prefix}{slug}/',
                    'edit_url': reverse('book_product_dashboard:taxonomy_edit', args=[key, slug]),
                }
            )
        groups.append(
            {
                'key': key,
                'label': label,
                'terms': terms,
                'root_url': _ROOT_URL.get(key, '/'),
                'root_edit_url': reverse('book_product_dashboard:taxonomy_root_edit', args=[key]),
            }
        )
    return render(
        request,
        'book_product/dashboard/taxonomies_list.html',
        {
            'groups': groups,
            'active_nav': 'book_taxonomies',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Book taxonomies'},
            ],
        },
    )


@staff_member_required
def taxonomy_edit(request: HttpRequest, taxonomy: str, slug: str) -> HttpResponse:
    from plugins.installed.book_product.compat import resolve_slug
    from plugins.installed.book_product.models import BookTaxonomy, BookTaxonomyTerm

    if taxonomy not in BookTaxonomy.values:
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))

    name = resolve_slug(taxonomy, slug) or slug
    term = BookTaxonomyTerm.objects.filter(taxonomy=taxonomy, slug=slug).first()

    if request.method == 'POST':
        term, _ = BookTaxonomyTerm.objects.get_or_create(
            taxonomy=taxonomy, slug=slug, defaults={'name': name}
        )
        term.name = (request.POST.get('name') or name).strip()
        term.description = (request.POST.get('description') or '').strip()
        term.meta_title = (request.POST.get('meta_title') or '').strip()
        term.meta_description = (request.POST.get('meta_description') or '').strip()
        if request.FILES.get('image'):
            term.image = request.FILES['image']
        term.save()
        messages.success(request, f'{_LABELS.get(taxonomy, taxonomy)} term saved.')
        return HttpResponseRedirect(
            reverse('book_product_dashboard:taxonomy_edit', args=[taxonomy, slug])
        )

    return render(
        request,
        'book_product/dashboard/taxonomy_form.html',
        {
            'taxonomy': taxonomy,
            'taxonomy_label': _LABELS.get(taxonomy, taxonomy),
            'slug': slug,
            'name': name,
            'term': term,
            'page_url': f'{_URL_PREFIX.get(taxonomy, "/")}{slug}/',
            'active_nav': 'book_taxonomies',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Book taxonomies', 'url': reverse('book_product_dashboard:taxonomies')},
                {'label': name[:50]},
            ],
        },
    )


@staff_member_required
def taxonomy_root_edit(request: HttpRequest, taxonomy: str) -> HttpResponse:
    """Edit the landing page for a whole taxonomy kind (e.g. /authors/,
    /genres/) — its intro blurb, SEO, and hero image. The BookTaxonomyRoot row
    is created only on first save. Validates against BookRootTaxonomy (the
    six kinds with an index page), NOT BookTaxonomy (the four that can have
    term overlays) — gating on the latter is what made /genres/ + /topics/
    uneditable."""
    from plugins.installed.book_product.models import BookRootTaxonomy, BookTaxonomyRoot

    if taxonomy not in BookRootTaxonomy.values:
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))

    label = _ROOT_LABELS.get(taxonomy, taxonomy)
    root = BookTaxonomyRoot.objects.filter(taxonomy=taxonomy).first()

    if request.method == 'POST':
        root, _ = BookTaxonomyRoot.objects.get_or_create(taxonomy=taxonomy)
        root.description = (request.POST.get('description') or '').strip()
        root.meta_title = (request.POST.get('meta_title') or '').strip()
        root.meta_description = (request.POST.get('meta_description') or '').strip()
        if request.FILES.get('image'):
            root.image = request.FILES['image']
        root.save()
        messages.success(request, f'{label} landing page saved.')
        return HttpResponseRedirect(
            reverse('book_product_dashboard:taxonomy_root_edit', args=[taxonomy])
        )

    return render(
        request,
        'book_product/dashboard/taxonomy_root_form.html',
        {
            'taxonomy': taxonomy,
            'taxonomy_label': label,
            'root': root,
            'page_url': _ROOT_URL.get(taxonomy, '/'),
            'active_nav': 'book_taxonomies',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Book taxonomies', 'url': reverse('book_product_dashboard:taxonomies')},
                {'label': f'{label} landing page'},
            ],
        },
    )


def _curated_breadcrumb(label, extra):
    return [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Products', 'url': '/dashboard/products/'},
        {'label': 'Book taxonomies', 'url': reverse('book_product_dashboard:taxonomies')},
        {'label': extra},
    ]


@staff_member_required
def curated_add(request: HttpRequest, kind: str) -> HttpResponse:
    """Create a curated Genre/Topic (curated taxonomies need a create path that
    auto-discovered authors/publishers don't)."""
    model = _curated_model(kind)
    if model is None or request.method != 'POST':
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    name = (request.POST.get('name') or '').strip()
    if not name:
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    obj, created = model.objects.get_or_create(slug=slugify(name), defaults={'name': name})
    messages.success(
        request, f'{_CURATED_LABELS[kind]} "{obj.name}" {"added" if created else "already exists"}.'
    )
    return HttpResponseRedirect(
        reverse('book_product_dashboard:curated_edit', args=[kind, obj.slug])
    )


@staff_member_required
def curated_edit(request: HttpRequest, kind: str, slug: str) -> HttpResponse:
    """Edit a Genre/Topic landing page — name, intro, SEO, image. Same UX as a
    book-taxonomy term, but writes the model row directly (it carries its own SEO)."""
    model = _curated_model(kind)
    if model is None:
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    obj = model.objects.filter(slug=slug).first()
    if obj is None:
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    label = _CURATED_LABELS[kind]
    prefix = '/genre/' if kind == 'genre' else '/topic/'

    if request.method == 'POST':
        obj.name = (request.POST.get('name') or obj.name).strip()
        obj.description = (request.POST.get('description') or '').strip()
        obj.meta_title = (request.POST.get('meta_title') or '').strip()
        obj.meta_description = (request.POST.get('meta_description') or '').strip()
        if request.FILES.get('image'):
            obj.image = request.FILES['image']
        obj.save()
        messages.success(request, f'{label} "{obj.name}" saved.')
        return HttpResponseRedirect(
            reverse('book_product_dashboard:curated_edit', args=[kind, obj.slug])
        )

    return render(
        request,
        'book_product/dashboard/taxonomy_form.html',
        {
            'taxonomy': kind,
            'taxonomy_label': label,
            'slug': obj.slug,
            'name': obj.name,
            'term': obj,
            'page_url': f'{prefix}{obj.slug}/',
            'delete_url': reverse('book_product_dashboard:curated_delete', args=[kind, obj.slug]),
            'active_nav': 'book_taxonomies',
            'breadcrumb_trail': _curated_breadcrumb(label, obj.name[:50]),
        },
    )


@staff_member_required
def curated_backfill(request: HttpRequest, kind: str) -> HttpResponse:
    """Queue the bulk copy backfill for a curated kind (Genres/Topics).

    Hand-writing ~1500 topic intros isn't realistic and the per-page Generate
    button is one-at-a-time, so this enqueues a batch — most-stocked terms
    first. Runs on the worker: each term is an LLM call, far past a request's
    budget. The list page's SEO pill shows progress on refresh.
    """
    if _curated_model(kind) is None or request.method != 'POST':
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    try:
        limit = int(request.POST.get('limit') or 25)
    except (TypeError, ValueError):
        limit = 25

    from django.core.cache import cache

    from plugins.installed.book_product.tasks import (
        BACKFILL_LOCK_SECS,
        MAX_BATCH,
        backfill_taxonomy_copy,
    )

    limit = max(1, min(limit, MAX_BATCH))
    # One run per kind at a time. Every term is a paid LLM call, and the button
    # sits on a page that invites a re-click while the first batch is still
    # working — without this, refresh-and-click queues overlapping runs that
    # bill for the same pages twice.
    lock = f'book_product:backfill:{kind}'
    if not cache.add(lock, '1', BACKFILL_LOCK_SECS):
        messages.info(
            request,
            f'A {_CURATED_LABELS[kind].lower()} copy run is already working. '
            'Give it a minute and refresh — the SEO column fills in as pages land.',
        )
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    try:
        backfill_taxonomy_copy.delay(kind, limit)
    except Exception as e:  # noqa: BLE001 — no broker (dev without Redis)
        cache.delete(lock)  # nothing queued — don't hold the lock for nothing
        messages.error(request, f"Couldn't queue the copy backfill: {e}")
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))
    messages.success(
        request,
        f'Writing intro copy for up to {limit} {_CURATED_LABELS[kind].lower()} '
        'pages in the background, most-stocked first. Refresh in a minute to '
        'see them land.',
    )
    return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))


@staff_member_required
def curated_delete(request: HttpRequest, kind: str, slug: str) -> HttpResponse:
    model = _curated_model(kind)
    if model is not None and request.method == 'POST':
        model.objects.filter(slug=slug).delete()
        messages.success(request, f'{_CURATED_LABELS[kind]} deleted. Books keep their other tags.')
    return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))


@staff_member_required
def taxonomy_generate(request: HttpRequest, taxonomy: str, slug: str = '') -> HttpResponse:
    """AI-generate the intro + SEO for a taxonomy page — a term when `slug` is
    given, otherwise the root/index page. Returns JSON
    {description, meta_title, meta_description}. Fail-soft: a {error} payload
    (HTTP 200) the editor surfaces when the AI provider isn't configured.

    The prompt lives in services_copy so this button and the bulk backfill
    task write identical copy."""
    from django.http import JsonResponse

    from plugins.installed.book_product.services_copy import (
        CopyGenerationError,
        generate_copy,
    )

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    try:
        payload = generate_copy(
            taxonomy,
            slug,
            mode=request.POST.get('mode', 'generate'),
            existing=(request.POST.get('existing') or '').strip(),
        )
    except LookupError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except CopyGenerationError as e:
        return JsonResponse({'error': f'AI provider unavailable ({e}).'}, status=200)
    return JsonResponse(payload)
