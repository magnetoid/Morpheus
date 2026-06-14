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
    from django.urls import reverse

    groups = []
    for kind, _singular, label, prefix, root_url in _CURATED:
        model = _curated_model(kind)
        terms = []
        for obj in model.objects.all():
            terms.append(
                {
                    'name': obj.name,
                    'slug': obj.slug,
                    'count': obj.books.count(),
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
        groups.append(
            {
                'key': kind,
                'label': label,
                'terms': terms,
                'is_curated': True,
                'root_url': root_url,
                'add_url': reverse('book_product_dashboard:curated_add', args=[kind]),
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
}


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
    """Edit the landing page for a whole taxonomy kind (e.g. /authors/) —
    its intro blurb, SEO, and hero image. The BookTaxonomyRoot row is created
    only on first save."""
    from plugins.installed.book_product.models import BookTaxonomy, BookTaxonomyRoot

    if taxonomy not in BookTaxonomy.values:
        return HttpResponseRedirect(reverse('book_product_dashboard:taxonomies'))

    label = _LABELS.get(taxonomy, taxonomy)
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
    (HTTP 200) the editor surfaces when the AI provider isn't configured."""
    import json  # noqa: F401

    from django.http import JsonResponse

    from plugins.installed.book_product.compat import (
        distinct_values,
        product_ids_for,
        resolve_slug,
    )
    from plugins.installed.book_product.models import BookTaxonomy
    from plugins.installed.catalog.models import Product

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    if taxonomy not in BookTaxonomy.values and taxonomy not in _CURATED_LABELS:
        return JsonResponse({'error': 'Unknown taxonomy.'}, status=400)

    if taxonomy in _CURATED_LABELS:
        # Curated Genre/Topic — titles come from the M2M, not a string field.
        label = _CURATED_LABELS[taxonomy]
        model = _curated_model(taxonomy)
        if slug:
            obj = model.objects.filter(slug=slug).first()
            if obj is None:
                return JsonResponse({'error': 'Unknown term.'}, status=400)
            name = obj.name
            titles = [t for t in obj.books.values_list('product__name', flat=True)[:12] if t]
            subject = f'the {label} page for "{name}"'
            context_line = f'Books on this page: {", ".join(titles) or "(none yet)"}.'
        else:
            name = f'All {label}s'
            terms = list(model.objects.values_list('name', flat=True)[:15])
            subject = f'the {label} index page, which lists every {label.lower()}'
            context_line = f'{label}s include: {", ".join(terms) or "(none yet)"}.'
    elif slug:
        label = _LABELS.get(taxonomy, taxonomy)
        name = resolve_slug(taxonomy, slug) or slug
        ids = product_ids_for(taxonomy, name)[:12]
        titles = list(Product.objects.filter(id__in=ids).values_list('name', flat=True)[:12])
        subject = f'the {label} page for "{name}"'
        context_line = f'Books on this page: {", ".join(titles) or "(none yet)"}.'
    else:
        label = _LABELS.get(taxonomy, taxonomy)
        name = f'All {label}'
        terms = distinct_values(taxonomy)[:15]
        subject = f'the {label} index page, which lists every {label.lower()} entry'
        context_line = f'{label} include: {", ".join(terms) or "(none yet)"}.'

    mode = request.POST.get('mode', 'generate')
    existing = (request.POST.get('existing') or '').strip()
    if mode == 'rewrite' and existing:
        # Rewrite just the intro the merchant already has — keep their facts,
        # improve the prose. Returns only {description}.
        prompt = (
            f'Rewrite and improve this intro for {subject} on dot books, an '
            'independent online bookshop. Keep it warm, concise (2-3 sentences) '
            'and specific; preserve the facts. Return STRICT JSON {"description": '
            '"..."} and nothing else.\n\nCurrent text:\n' + existing
        )
    else:
        prompt = (
            f'Write storefront copy for {subject} on an independent online bookshop '
            f'called dot books.\n{context_line}\n\n'
            'Return STRICT JSON (no markdown, nothing outside the JSON) with keys:\n'
            '  "description": a warm, specific 2-3 sentence editorial intro (plain text),\n'
            '  "meta_title": an SEO title, max 60 characters,\n'
            '  "meta_description": an SEO meta description, max 155 characters.'
        )
    try:
        from plugins.installed.ai_assistant.services.llm import get_llm

        raw = get_llm().complete(
            prompt,
            system='You write concise, warm, specific bookshop copy. Output JSON only.',
            max_tokens=400,
            temperature=0.7,
        )
    except Exception as e:  # noqa: BLE001 — provider missing/misconfigured
        return JsonResponse({'error': f'AI provider unavailable ({e}).'}, status=200)

    from core.llm_parsing import parse_llm_json

    data = parse_llm_json(raw) if raw else None
    if not isinstance(data, dict):
        data = {'description': (raw or '').strip()[:600]}
    return JsonResponse(
        {
            'description': (data.get('description') or '').strip()[:600],
            'meta_title': (data.get('meta_title') or '').strip()[:200],
            'meta_description': (data.get('meta_description') or '').strip()[:320],
        }
    )
