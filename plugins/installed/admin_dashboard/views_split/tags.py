"""Tag descriptions editor for the admin dashboard (catalog.TagProfile).

taggit tags carry no description, so a ``?tag=`` landing page had nothing to show
below its title. This single-page editor lets a merchant write an attractive
display name + description for each tag; the storefront renders it as the tag
page's header. Lives under the Products nav group.
"""

# ruff: noqa: PLC0415, I001
# Inline imports match the views_split convention (avoid app-load-order deps).

from __future__ import annotations

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    messages,
    redirect,
    render,
    staff_member_required,
)


@staff_member_required
def tag_descriptions(request: HttpRequest) -> HttpResponse:
    from django.utils.text import slugify
    from taggit.models import Tag

    from plugins.installed.catalog.models import TagProfile

    if request.method == 'POST':
        saved = 0
        # Inputs are keyed by tag slug: desc__<slug> + name__<slug>.
        for key, value in request.POST.items():
            if not key.startswith('desc__'):
                continue
            slug = slugify(key[len('desc__') :])
            if not slug:
                continue
            name = (request.POST.get(f'name__{slug}') or slug).strip()[:200]
            description = (value or '').strip()
            profile, _ = TagProfile.objects.get_or_create(slug=slug, defaults={'name': name})
            profile.name = name or profile.name
            profile.description = description
            profile.save()
            saved += 1
        messages.success(request, f'Saved descriptions for {saved} tag(s).')
        return redirect('admin_dashboard:tag_descriptions')

    search = (request.GET.get('q') or '').strip()[:80]
    tags = Tag.objects.all().order_by('name')
    if search:
        tags = tags.filter(name__icontains=search)
    profiles = {p.slug: p for p in TagProfile.objects.all()}
    rows = []
    for tag in tags[:300]:
        prof = profiles.get(tag.slug)
        rows.append(
            {
                'slug': tag.slug,
                'name': (prof.name if prof else '') or tag.name,
                'description': prof.description if prof else '',
                'has_copy': bool(prof and prof.description),
            }
        )
    return render(
        request,
        'admin_dashboard/tag_descriptions.html',
        {
            'rows': rows,
            'search': search,
            'active_nav': 'categories',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Tag descriptions'},
            ],
        },
    )
