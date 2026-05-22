"""Catalog GraphQL mutations — staff-only.

Every mutation delegates to ``plugins.installed.catalog.services`` so
the MCP tool layer and the GraphQL layer stay shape-aligned.

Auth: ``info.context.request.user.is_staff`` must be True. Bearer
tokens minted at ``/dashboard/apps/agent_mcp/tokens/`` resolve to a
staff service user (see ``plugins.installed.agent_mcp.auth``) so the
same token can be used from either MCP or GraphQL.
"""
from __future__ import annotations

from typing import Optional

import strawberry


# ─── shared types / helpers ─────────────────────────────────────────────


@strawberry.type
class ProductMutationResult:
    id: strawberry.ID
    slug: str
    sku: str
    name: str
    status: str
    product_type: str
    price_amount: str
    price_currency: str
    url: str
    error: str


@strawberry.type
class CategoryMutationResult:
    id: strawberry.ID
    slug: str
    name: str
    parent_slug: str
    error: str


@strawberry.type
class PublishDigitalProductResult:
    id: strawberry.ID
    slug: str
    sku: str
    name: str
    url: str
    error: str


def _is_staff(info) -> bool:
    request = getattr(info.context, 'request', None) or (
        info.context.get('request') if isinstance(info.context, dict) else None
    )
    user = getattr(request, 'user', None) if request else None
    return bool(user and getattr(user, 'is_staff', False))


def _err_publish(msg: str) -> PublishDigitalProductResult:
    return PublishDigitalProductResult(
        id=strawberry.ID(''), slug='', sku='', name='', url='', error=msg,
    )


def _err_product(msg: str) -> ProductMutationResult:
    return ProductMutationResult(
        id=strawberry.ID(''), slug='', sku='', name='', status='',
        product_type='', price_amount='', price_currency='', url='', error=msg,
    )


def _err_category(msg: str) -> CategoryMutationResult:
    return CategoryMutationResult(
        id=strawberry.ID(''), slug='', name='', parent_slug='', error=msg,
    )


def _from_product_dict(d: dict) -> ProductMutationResult:
    return ProductMutationResult(
        id=strawberry.ID(d['id']), slug=d['slug'], sku=d['sku'],
        name=d['name'], status=d['status'], product_type=d['product_type'],
        price_amount=d['price_amount'], price_currency=d['price_currency'],
        url=d['url'], error='',
    )


def _from_category_dict(d: dict) -> CategoryMutationResult:
    return CategoryMutationResult(
        id=strawberry.ID(d['id']), slug=d['slug'], name=d['name'],
        parent_slug=d['parent_slug'], error='',
    )


# ─── inputs ─────────────────────────────────────────────────────────────


@strawberry.input
class PublishDigitalProductInput:
    title: str
    pdf_url: str
    price_amount: str
    price_currency: str = 'USD'
    description: str = ''
    short_description: str = ''
    author: str = ''
    cover_image_url: str = ''
    category_slug: str = ''
    sku: str = ''
    slug: str = ''
    status: str = 'active'


@strawberry.input
class CreateProductInput:
    """Create a new product. Generic — for digital/PDF books prefer
    publishDigitalProduct which downloads + attaches the PDF too."""
    name: str
    price_amount: str
    price_currency: str = 'USD'
    product_type: str = 'simple'          # 'simple' | 'variable' | 'digital' | 'bundle'
    status: str = 'draft'                 # 'draft' | 'active' | 'archived'
    sku: Optional[str] = None
    slug: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    category_slug: Optional[str] = None
    cover_image_url: Optional[str] = None
    # Optional scalars — pass any of these to set them on creation.
    weight: Optional[str] = None
    weight_unit: Optional[str] = None
    requires_shipping: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_taxable: Optional[bool] = None
    track_inventory: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    focus_keyword: Optional[str] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    twitter_card: Optional[str] = None
    noindex: Optional[bool] = None
    nofollow: Optional[bool] = None


@strawberry.input
class UpdateProductInput:
    """Update a product by slug. Every field is optional — only fields
    explicitly set are touched on the existing record."""
    slug: str
    # Basics
    name: Optional[str] = None
    sku: Optional[str] = None
    status: Optional[str] = None              # 'draft' | 'active' | 'archived'
    product_type: Optional[str] = None        # 'simple' | 'variable' | 'digital' | 'bundle'
    short_description: Optional[str] = None
    description: Optional[str] = None
    # Pricing
    price_amount: Optional[str] = None
    price_currency: Optional[str] = None
    compare_at_amount: Optional[str] = None   # pass '' or 'null' to clear
    cost_amount: Optional[str] = None         # pass '' or 'null' to clear
    # Taxonomy
    category_slug: Optional[str] = None       # pass '' to clear
    # Shipping
    weight: Optional[str] = None
    weight_unit: Optional[str] = None
    requires_shipping: Optional[bool] = None
    # Flags
    is_featured: Optional[bool] = None
    is_taxable: Optional[bool] = None
    track_inventory: Optional[bool] = None
    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    focus_keyword: Optional[str] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    twitter_card: Optional[str] = None
    noindex: Optional[bool] = None
    nofollow: Optional[bool] = None


@strawberry.input
class CreateCategoryInput:
    name: str
    slug: str = ''
    parent_slug: str = ''
    description: str = ''


@strawberry.input
class UpdateCategoryInput:
    slug: str
    name: Optional[str] = None
    new_slug: Optional[str] = None
    parent_slug: Optional[str] = None   # pass '' to clear, None to leave alone
    description: Optional[str] = None


# ─── mutation root ──────────────────────────────────────────────────────


@strawberry.type
class CatalogMutationExtension:

    # ── Digital book publishing (commit 1446913, kept) ────────────────

    @strawberry.mutation(
        description='Publish a digital product (PDF book) from URLs. Staff-only.',
    )
    def publish_digital_product(
        self,
        info: strawberry.Info,
        input: PublishDigitalProductInput,
    ) -> PublishDigitalProductResult:
        if not _is_staff(info):
            return _err_publish('Forbidden — staff only.')
        from plugins.installed.catalog.services import (
            PublishError,
            publish_digital_product as _publish,
        )
        try:
            r = _publish(
                title=input.title, pdf_url=input.pdf_url,
                price_amount=input.price_amount,
                price_currency=input.price_currency,
                description=input.description,
                short_description=input.short_description,
                author=input.author,
                cover_image_url=input.cover_image_url,
                category_slug=input.category_slug,
                sku=input.sku, slug=input.slug, status=input.status,
            )
        except PublishError as e:
            return _err_publish(str(e))
        return PublishDigitalProductResult(
            id=strawberry.ID(r['id']), slug=r['slug'], sku=r['sku'],
            name=r['name'], url=r['url'], error='',
        )

    # ── Product create / edit / archive / restore / delete ────────────

    @strawberry.mutation(
        description='Create a new product. Generic — for PDF books use publishDigitalProduct. Staff-only.',
    )
    def create_product(
        self, info: strawberry.Info, input: CreateProductInput,
    ) -> ProductMutationResult:
        if not _is_staff(info):
            return _err_product('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, create_product as _create

        kwargs = {
            k: v for k, v in {
                'sku': input.sku, 'slug': input.slug,
                'short_description': input.short_description,
                'description': input.description,
                'category_slug': input.category_slug,
                'cover_image_url': input.cover_image_url,
                'weight': input.weight, 'weight_unit': input.weight_unit,
                'requires_shipping': input.requires_shipping,
                'is_featured': input.is_featured,
                'is_taxable': input.is_taxable,
                'track_inventory': input.track_inventory,
                'meta_title': input.meta_title,
                'meta_description': input.meta_description,
                'focus_keyword': input.focus_keyword,
                'canonical_url': input.canonical_url,
                'og_title': input.og_title,
                'og_description': input.og_description,
                'twitter_title': input.twitter_title,
                'twitter_description': input.twitter_description,
                'twitter_card': input.twitter_card,
                'noindex': input.noindex, 'nofollow': input.nofollow,
            }.items() if v is not None
        }
        try:
            return _from_product_dict(_create(
                name=input.name,
                price_amount=input.price_amount,
                price_currency=input.price_currency,
                product_type=input.product_type,
                status=input.status,
                **kwargs,
            ))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(description='Update any field on an existing product. Staff-only.')
    def update_product(
        self, info: strawberry.Info, input: UpdateProductInput,
    ) -> ProductMutationResult:
        if not _is_staff(info):
            return _err_product('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, update_product

        # strawberry sends None for unset Optional fields; strip those
        # so the service only sees fields the caller actually set.
        kwargs = {
            k: v for k, v in {
                'name': input.name, 'sku': input.sku, 'status': input.status,
                'product_type': input.product_type,
                'short_description': input.short_description,
                'description': input.description,
                'price_amount': input.price_amount,
                'price_currency': input.price_currency,
                'compare_at_amount': input.compare_at_amount,
                'cost_amount': input.cost_amount,
                'category_slug': input.category_slug,
                'weight': input.weight, 'weight_unit': input.weight_unit,
                'requires_shipping': input.requires_shipping,
                'is_featured': input.is_featured,
                'is_taxable': input.is_taxable,
                'track_inventory': input.track_inventory,
                'meta_title': input.meta_title,
                'meta_description': input.meta_description,
                'focus_keyword': input.focus_keyword,
                'canonical_url': input.canonical_url,
                'og_title': input.og_title,
                'og_description': input.og_description,
                'twitter_title': input.twitter_title,
                'twitter_description': input.twitter_description,
                'twitter_card': input.twitter_card,
                'noindex': input.noindex, 'nofollow': input.nofollow,
            }.items() if v is not None
        }
        try:
            return _from_product_dict(update_product(slug=input.slug, **kwargs))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(description='Archive a product (sets status=archived). Staff-only.')
    def archive_product(self, info: strawberry.Info, slug: str) -> ProductMutationResult:
        if not _is_staff(info):
            return _err_product('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, archive_product
        try:
            return _from_product_dict(archive_product(slug=slug))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(description='Restore an archived product. Staff-only.')
    def restore_product(
        self, info: strawberry.Info, slug: str, status: str = 'active',
    ) -> ProductMutationResult:
        if not _is_staff(info):
            return _err_product('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, restore_product
        try:
            return _from_product_dict(restore_product(slug=slug, status=status))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(
        description='Hard-delete a product. Prefer archiveProduct unless you really need the row gone. Staff-only.',
    )
    def delete_product(self, info: strawberry.Info, slug: str) -> ProductMutationResult:
        if not _is_staff(info):
            return _err_product('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, delete_product
        try:
            return _from_product_dict(delete_product(slug=slug))
        except PublishError as e:
            return _err_product(str(e))

    # ── Categories ────────────────────────────────────────────────────

    @strawberry.mutation(description='Create a category. Staff-only.')
    def create_category(
        self, info: strawberry.Info, input: CreateCategoryInput,
    ) -> CategoryMutationResult:
        if not _is_staff(info):
            return _err_category('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, create_category
        try:
            return _from_category_dict(create_category(
                name=input.name, slug=input.slug,
                parent_slug=input.parent_slug, description=input.description,
            ))
        except PublishError as e:
            return _err_category(str(e))

    @strawberry.mutation(description='Update a category by slug. Staff-only.')
    def update_category(
        self, info: strawberry.Info, input: UpdateCategoryInput,
    ) -> CategoryMutationResult:
        if not _is_staff(info):
            return _err_category('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, update_category
        try:
            return _from_category_dict(update_category(
                slug=input.slug,
                name=input.name or '',
                new_slug=input.new_slug or '',
                parent_slug=input.parent_slug,
                description=input.description,
            ))
        except PublishError as e:
            return _err_category(str(e))

    @strawberry.mutation(
        description='Archive (delete) a category. Detaches products to category=null. Staff-only.',
    )
    def archive_category(self, info: strawberry.Info, slug: str) -> CategoryMutationResult:
        if not _is_staff(info):
            return _err_category('Forbidden — staff only.')
        from plugins.installed.catalog.services import PublishError, archive_category
        try:
            return _from_category_dict(archive_category(slug=slug))
        except PublishError as e:
            return _err_category(str(e))
