"""Linda's vendor tools: list the store's vendors and change one (owner, 2026-10-19).

`vendors.update` saves through the dashboard's VendorForm, so the dashboard and
Linda refuse the same things; it writes, so the edge asks the merchant first.
"""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='vendors.list',
    description=(
        "List the store's vendors: name, web address (slug), whether each is active, and "
        'how many active products it has. Pass a query to match a name or address, or '
        'active to see only active (true) or inactive (false) vendors.'
    ),
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {'type': 'string', 'description': 'Part of a name or web address.'},
            'active': {'type': 'boolean'},
        },
    },
)
def vendors_list_tool(*, query: str = '', active: bool | None = None) -> ToolResult:
    from django.db.models import Count, Q

    from plugins.installed.catalog.models import Vendor

    qs = Vendor.objects.annotate(
        active_products=Count('products', filter=Q(products__status='active'))
    ).order_by('name')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(slug__icontains=query))
    if active is not None:
        qs = qs.filter(is_active=bool(active))
    vendors = [
        {
            'id': str(v.pk),
            'name': v.name,
            'slug': v.slug,
            'is_active': v.is_active,
            'active_products': v.active_products,
        }
        for v in qs[:200]
    ]
    return ToolResult(
        output={'vendors': vendors, 'count': len(vendors)}, display=f'{len(vendors)} vendors.'
    )


@tool(
    name='vendors.update',
    description=(
        "Change a vendor's name, web address (slug), description or whether it is active. "
        'A new web address keeps the old one working: it redirects to the new one. Name the '
        'vendor by its web address or id from vendors.list.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'vendor': {'type': 'string', 'description': "The vendor's web address or id."},
            'name': {'type': 'string'},
            'slug': {'type': 'string', 'description': 'A new web address.'},
            'description': {'type': 'string'},
            'is_active': {'type': 'boolean'},
        },
        'required': ['vendor'],
    },
    requires_approval=True,
)
def vendors_update_tool(
    *,
    vendor: str,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> ToolResult:
    from django.core.exceptions import ValidationError

    from plugins.installed.catalog.models import Vendor
    from plugins.installed.marketplace.forms import VendorForm

    row = Vendor.objects.filter(slug=vendor).first()
    if row is None:
        try:
            row = Vendor.objects.filter(pk=vendor).first()
        except (ValidationError, ValueError):
            row = None
    if row is None:
        raise ToolError(f'No vendor has the address or id {vendor!r}.')
    data = {
        'name': row.name if name is None else name,
        'slug': row.slug if slug is None else slug,
        'description': row.description if description is None else description,
    }
    if row.is_active if is_active is None else bool(is_active):
        data['is_active'] = 'on'
    form = VendorForm(data=data, files={}, instance=row)
    if not form.is_valid():
        raise ToolError(' '.join(str(error) for errors in form.errors.values() for error in errors))
    form.save()
    return ToolResult(
        output={'vendor': row.slug, 'name': row.name, 'is_active': row.is_active},
        display=f'Saved {row.name}.',
    )
