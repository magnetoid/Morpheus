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


@staff_member_required
def taxonomies_list(request: HttpRequest) -> HttpResponse:
    from plugins.installed.book_product.compat import distinct_values, product_ids_for
    from plugins.installed.book_product.models import BookTaxonomyTerm

    customized = {(t.taxonomy, t.slug) for t in BookTaxonomyTerm.objects.all()}
    groups = []
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
        groups.append({'key': key, 'label': label, 'terms': terms})
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
