"""Catalog GraphQL mutations — staff-only.

Every mutation delegates to ``plugins.installed.catalog.services`` so
the MCP tool layer and the GraphQL layer stay shape-aligned.

Auth: ``info.context.request.user.is_staff`` must be True. Bearer
tokens minted at ``/dashboard/apps/agent_mcp/tokens/`` resolve to a
staff service user (see ``plugins.installed.agent_mcp.auth``) so the
same token can be used from either MCP or GraphQL.
"""

from __future__ import annotations

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
class ProductImageMutationResult:
    id: strawberry.ID
    product_slug: str
    url: str
    alt_text: str
    is_primary: bool
    sort_order: int
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


def _check_scope(info, required: list[str]) -> str:
    """Return '' when the request is authorised for the given scope(s),
    otherwise a human-friendly error string. Session-authenticated
    staff bypass scope checks (no token means no scope restriction).
    Bearer-authed requests must have at least one of the required
    scopes (or the wildcard) on the GraphQL surface."""
    if not _is_staff(info):
        return 'Forbidden — staff only.'
    request = getattr(info.context, 'request', None) or (
        info.context.get('request') if isinstance(info.context, dict) else None
    )
    granted = getattr(request, '_morph_token_scopes_graphql', None)
    if granted is None:
        # No bearer scope set → session auth → bypass scope check.
        return ''
    from plugins.installed.agent_mcp.scopes import has_any

    if not has_any(granted, required):
        return f'token missing scope: needs one of {sorted(required)}'
    return ''


def _err_publish(msg: str) -> PublishDigitalProductResult:
    return PublishDigitalProductResult(
        id=strawberry.ID(''),
        slug='',
        sku='',
        name='',
        url='',
        error=msg,
    )


def _err_product(msg: str) -> ProductMutationResult:
    return ProductMutationResult(
        id=strawberry.ID(''),
        slug='',
        sku='',
        name='',
        status='',
        product_type='',
        price_amount='',
        price_currency='',
        url='',
        error=msg,
    )


def _err_category(msg: str) -> CategoryMutationResult:
    return CategoryMutationResult(
        id=strawberry.ID(''),
        slug='',
        name='',
        parent_slug='',
        error=msg,
    )


def _from_product_dict(d: dict) -> ProductMutationResult:
    return ProductMutationResult(
        id=strawberry.ID(d['id']),
        slug=d['slug'],
        sku=d['sku'],
        name=d['name'],
        status=d['status'],
        product_type=d['product_type'],
        price_amount=d['price_amount'],
        price_currency=d['price_currency'],
        url=d['url'],
        error='',
    )


def _from_category_dict(d: dict) -> CategoryMutationResult:
    return CategoryMutationResult(
        id=strawberry.ID(d['id']),
        slug=d['slug'],
        name=d['name'],
        parent_slug=d['parent_slug'],
        error='',
    )


def _err_image(msg: str) -> ProductImageMutationResult:
    return ProductImageMutationResult(
        id=strawberry.ID(''),
        product_slug='',
        url='',
        alt_text='',
        is_primary=False,
        sort_order=0,
        error=msg,
    )


def _from_image_dict(d: dict) -> ProductImageMutationResult:
    return ProductImageMutationResult(
        id=strawberry.ID(d['id']),
        product_slug=d['product_slug'],
        url=d['url'],
        alt_text=d['alt_text'],
        is_primary=d['is_primary'],
        sort_order=d['sort_order'],
        error='',
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
    product_type: str = 'simple'  # 'simple' | 'variable' | 'digital' | 'bundle'
    status: str = 'draft'  # 'draft' | 'active' | 'archived'
    sku: str | None = None
    slug: str | None = None
    short_description: str | None = None
    description: str | None = None
    category_slug: str | None = None
    cover_image_url: str | None = None
    # Optional scalars — pass any of these to set them on creation.
    weight: str | None = None
    weight_unit: str | None = None
    requires_shipping: bool | None = None
    is_featured: bool | None = None
    is_taxable: bool | None = None
    track_inventory: bool | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    focus_keyword: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    twitter_title: str | None = None
    twitter_description: str | None = None
    twitter_card: str | None = None
    noindex: bool | None = None
    nofollow: bool | None = None


@strawberry.input
class UpdateProductInput:
    """Update a product by slug. Every field is optional — only fields
    explicitly set are touched on the existing record."""

    slug: str
    # Basics
    name: str | None = None
    sku: str | None = None
    status: str | None = None  # 'draft' | 'active' | 'archived'
    product_type: str | None = None  # 'simple' | 'variable' | 'digital' | 'bundle'
    short_description: str | None = None
    description: str | None = None
    # Pricing
    price_amount: str | None = None
    price_currency: str | None = None
    compare_at_amount: str | None = None  # pass '' or 'null' to clear
    cost_amount: str | None = None  # pass '' or 'null' to clear
    # Taxonomy
    category_slug: str | None = None  # pass '' to clear
    # Shipping
    weight: str | None = None
    weight_unit: str | None = None
    requires_shipping: bool | None = None
    # Flags
    is_featured: bool | None = None
    is_taxable: bool | None = None
    track_inventory: bool | None = None
    # SEO
    meta_title: str | None = None
    meta_description: str | None = None
    focus_keyword: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    twitter_title: str | None = None
    twitter_description: str | None = None
    twitter_card: str | None = None
    noindex: bool | None = None
    nofollow: bool | None = None


@strawberry.input
class CreateCategoryInput:
    name: str
    slug: str = ''
    parent_slug: str = ''
    description: str = ''


@strawberry.input
class CreateVariantInput:
    product_slug: str
    name: str
    sku: str
    # Pricing — optional, defaults to inheriting from parent product
    price_amount: str | None = None
    price_currency: str | None = None
    compare_at_amount: str | None = None
    # Shopify-parity fields
    variant_type: str | None = None  # physical | digital | virtual
    requires_shipping: bool | None = None
    is_taxable: bool | None = None
    inventory_policy: str | None = None  # deny | continue
    barcode: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


@strawberry.input
class UpdateVariantInput:
    sku: str
    name: str | None = None
    new_sku: str | None = None
    price_amount: str | None = None
    price_currency: str | None = None
    compare_at_amount: str | None = None
    variant_type: str | None = None
    requires_shipping: bool | None = None
    is_taxable: bool | None = None
    inventory_policy: str | None = None
    barcode: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


@strawberry.type
class VariantMutationResult:
    id: strawberry.ID
    product_slug: str
    name: str
    sku: str
    price_amount: str
    price_currency: str
    variant_type: str
    requires_shipping: bool
    is_taxable: bool
    inventory_policy: str
    barcode: str
    is_active: bool
    sort_order: int
    error: str


def _err_variant(msg: str) -> VariantMutationResult:
    return VariantMutationResult(
        id=strawberry.ID(''),
        product_slug='',
        name='',
        sku='',
        price_amount='',
        price_currency='',
        variant_type='',
        requires_shipping=False,
        is_taxable=False,
        inventory_policy='',
        barcode='',
        is_active=False,
        sort_order=0,
        error=msg,
    )


def _from_variant_dict(d: dict) -> VariantMutationResult:
    return VariantMutationResult(
        id=strawberry.ID(d['id']),
        product_slug=d['product_slug'],
        name=d['name'],
        sku=d['sku'],
        price_amount=d['price_amount'],
        price_currency=d['price_currency'],
        variant_type=d['variant_type'],
        requires_shipping=d['requires_shipping'],
        is_taxable=d['is_taxable'],
        inventory_policy=d['inventory_policy'],
        barcode=d['barcode'],
        is_active=d['is_active'],
        sort_order=d['sort_order'],
        error='',
    )


@strawberry.input
class UpdateDigitalPdfInput:
    slug: str
    pdf_url: str


@strawberry.input
class AddProductImageInput:
    slug: str
    image_url: str
    alt_text: str = ''
    is_primary: bool = False
    sort_order: int = 0


@strawberry.input
class UpdateCategoryInput:
    slug: str
    name: str | None = None
    new_slug: str | None = None
    parent_slug: str | None = None  # pass '' to clear, None to leave alone
    description: str | None = None


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
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_publish(err)
        from plugins.installed.catalog.services import (
            PublishError,
        )
        from plugins.installed.catalog.services import (
            publish_digital_product as _publish,
        )

        try:
            r = _publish(
                title=input.title,
                pdf_url=input.pdf_url,
                price_amount=input.price_amount,
                price_currency=input.price_currency,
                description=input.description,
                short_description=input.short_description,
                author=input.author,
                cover_image_url=input.cover_image_url,
                category_slug=input.category_slug,
                sku=input.sku,
                slug=input.slug,
                status=input.status,
            )
        except PublishError as e:
            return _err_publish(str(e))
        return PublishDigitalProductResult(
            id=strawberry.ID(r['id']),
            slug=r['slug'],
            sku=r['sku'],
            name=r['name'],
            url=r['url'],
            error='',
        )

    # ── Product create / edit / archive / restore / delete ────────────

    @strawberry.mutation(
        description='Create a new product. Generic — for PDF books use publishDigitalProduct. Staff-only.',
    )
    def create_product(
        self,
        info: strawberry.Info,
        input: CreateProductInput,
    ) -> ProductMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_product(err)
        from plugins.installed.catalog.services import PublishError
        from plugins.installed.catalog.services import create_product as _create

        kwargs = {
            k: v
            for k, v in {
                'sku': input.sku,
                'slug': input.slug,
                'short_description': input.short_description,
                'description': input.description,
                'category_slug': input.category_slug,
                'cover_image_url': input.cover_image_url,
                'weight': input.weight,
                'weight_unit': input.weight_unit,
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
                'noindex': input.noindex,
                'nofollow': input.nofollow,
            }.items()
            if v is not None
        }
        try:
            return _from_product_dict(
                _create(
                    name=input.name,
                    price_amount=input.price_amount,
                    price_currency=input.price_currency,
                    product_type=input.product_type,
                    status=input.status,
                    **kwargs,
                )
            )
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(description='Update any field on an existing product. Staff-only.')
    def update_product(
        self,
        info: strawberry.Info,
        input: UpdateProductInput,
    ) -> ProductMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_product(err)
        from plugins.installed.catalog.services import PublishError, update_product

        # strawberry sends None for unset Optional fields; strip those
        # so the service only sees fields the caller actually set.
        kwargs = {
            k: v
            for k, v in {
                'name': input.name,
                'sku': input.sku,
                'status': input.status,
                'product_type': input.product_type,
                'short_description': input.short_description,
                'description': input.description,
                'price_amount': input.price_amount,
                'price_currency': input.price_currency,
                'compare_at_amount': input.compare_at_amount,
                'cost_amount': input.cost_amount,
                'category_slug': input.category_slug,
                'weight': input.weight,
                'weight_unit': input.weight_unit,
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
                'noindex': input.noindex,
                'nofollow': input.nofollow,
            }.items()
            if v is not None
        }
        try:
            return _from_product_dict(update_product(slug=input.slug, **kwargs))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(description='Archive a product (sets status=archived). Staff-only.')
    def archive_product(self, info: strawberry.Info, slug: str) -> ProductMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_product(err)
        from plugins.installed.catalog.services import PublishError, archive_product

        try:
            return _from_product_dict(archive_product(slug=slug))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(description='Restore an archived product. Staff-only.')
    def restore_product(
        self,
        info: strawberry.Info,
        slug: str,
        status: str = 'active',
    ) -> ProductMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_product(err)
        from plugins.installed.catalog.services import PublishError, restore_product

        try:
            return _from_product_dict(restore_product(slug=slug, status=status))
        except PublishError as e:
            return _err_product(str(e))

    @strawberry.mutation(
        description='Hard-delete a product. Prefer archiveProduct unless you really need the row gone. Staff-only.',
    )
    def delete_product(self, info: strawberry.Info, slug: str) -> ProductMutationResult:
        err = _check_scope(info, ['catalog.delete'])
        if err:
            return _err_product(err)
        from plugins.installed.catalog.services import PublishError, delete_product

        try:
            return _from_product_dict(delete_product(slug=slug))
        except PublishError as e:
            return _err_product(str(e))

    # ── Variants (Shopify-parity surface) ─────────────────────────────

    @strawberry.mutation(description='Create a new variant on a product. Staff-only.')
    def create_variant(
        self,
        info: strawberry.Info,
        input: CreateVariantInput,
    ) -> VariantMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_variant(err)
        from plugins.installed.catalog.services import PublishError, create_variant

        kwargs = {
            k: v
            for k, v in {
                'price_amount': input.price_amount,
                'price_currency': input.price_currency,
                'compare_at_amount': input.compare_at_amount,
                'variant_type': input.variant_type,
                'requires_shipping': input.requires_shipping,
                'is_taxable': input.is_taxable,
                'inventory_policy': input.inventory_policy,
                'barcode': input.barcode,
                'is_active': input.is_active,
                'sort_order': input.sort_order,
            }.items()
            if v is not None
        }
        try:
            return _from_variant_dict(
                create_variant(
                    product_slug=input.product_slug,
                    name=input.name,
                    sku=input.sku,
                    **kwargs,
                )
            )
        except PublishError as e:
            return _err_variant(str(e))

    @strawberry.mutation(description='Update an existing variant by SKU. Staff-only.')
    def update_variant(
        self,
        info: strawberry.Info,
        input: UpdateVariantInput,
    ) -> VariantMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_variant(err)
        from plugins.installed.catalog.services import PublishError, update_variant

        kwargs = {
            k: v
            for k, v in {
                'name': input.name,
                'sku': input.new_sku,  # rename target
                'price_amount': input.price_amount,
                'price_currency': input.price_currency,
                'compare_at_amount': input.compare_at_amount,
                'variant_type': input.variant_type,
                'requires_shipping': input.requires_shipping,
                'is_taxable': input.is_taxable,
                'inventory_policy': input.inventory_policy,
                'barcode': input.barcode,
                'is_active': input.is_active,
                'sort_order': input.sort_order,
            }.items()
            if v is not None
        }
        try:
            return _from_variant_dict(update_variant(sku=input.sku, **kwargs))
        except PublishError as e:
            return _err_variant(str(e))

    # ── Digital file + images ─────────────────────────────────────────

    @strawberry.mutation(
        description='Replace the digital_file PDF on an existing product. Staff-only.',
    )
    def update_digital_pdf(
        self,
        info: strawberry.Info,
        input: UpdateDigitalPdfInput,
    ) -> ProductMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_product(err)
        from plugins.installed.catalog.services import PublishError, update_digital_pdf

        try:
            r = update_digital_pdf(slug=input.slug, pdf_url=input.pdf_url)
        except PublishError as e:
            return _err_product(str(e))
        # Service returns extra `digital_file` URL we don't surface here;
        # the basic product summary is what the caller usually wants.
        return _from_product_dict(r)

    @strawberry.mutation(
        description='Download an image from an HTTPS URL and attach it as a ProductImage. Staff-only.',
    )
    def add_product_image(
        self,
        info: strawberry.Info,
        input: AddProductImageInput,
    ) -> ProductImageMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_image(err)
        from plugins.installed.catalog.services import PublishError, add_product_image

        try:
            return _from_image_dict(
                add_product_image(
                    slug=input.slug,
                    image_url=input.image_url,
                    alt_text=input.alt_text,
                    is_primary=input.is_primary,
                    sort_order=input.sort_order,
                )
            )
        except PublishError as e:
            return _err_image(str(e))

    @strawberry.mutation(description='Remove a ProductImage by id. Staff-only.')
    def remove_product_image(
        self,
        info: strawberry.Info,
        image_id: strawberry.ID,
    ) -> ProductImageMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_image(err)
        from plugins.installed.catalog.services import PublishError, remove_product_image

        try:
            return _from_image_dict(remove_product_image(image_id=str(image_id)))
        except PublishError as e:
            return _err_image(str(e))

    @strawberry.mutation(
        description='Promote an image to primary (demotes any other primary on the same product). Staff-only.',
    )
    def set_primary_image(
        self,
        info: strawberry.Info,
        image_id: strawberry.ID,
    ) -> ProductImageMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_image(err)
        from plugins.installed.catalog.services import PublishError, set_primary_image

        try:
            return _from_image_dict(set_primary_image(image_id=str(image_id)))
        except PublishError as e:
            return _err_image(str(e))

    # ── Categories ────────────────────────────────────────────────────

    @strawberry.mutation(description='Create a category. Staff-only.')
    def create_category(
        self,
        info: strawberry.Info,
        input: CreateCategoryInput,
    ) -> CategoryMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_category(err)
        from plugins.installed.catalog.services import PublishError, create_category

        try:
            return _from_category_dict(
                create_category(
                    name=input.name,
                    slug=input.slug,
                    parent_slug=input.parent_slug,
                    description=input.description,
                )
            )
        except PublishError as e:
            return _err_category(str(e))

    @strawberry.mutation(description='Update a category by slug. Staff-only.')
    def update_category(
        self,
        info: strawberry.Info,
        input: UpdateCategoryInput,
    ) -> CategoryMutationResult:
        err = _check_scope(info, ['catalog.write'])
        if err:
            return _err_category(err)
        from plugins.installed.catalog.services import PublishError, update_category

        try:
            return _from_category_dict(
                update_category(
                    slug=input.slug,
                    name=input.name or '',
                    new_slug=input.new_slug or '',
                    parent_slug=input.parent_slug,
                    description=input.description,
                )
            )
        except PublishError as e:
            return _err_category(str(e))

    @strawberry.mutation(
        description='Archive (delete) a category. Detaches products to category=null. Staff-only.',
    )
    def archive_category(self, info: strawberry.Info, slug: str) -> CategoryMutationResult:
        err = _check_scope(info, ['catalog.delete'])
        if err:
            return _err_category(err)
        from plugins.installed.catalog.services import PublishError, archive_category

        try:
            return _from_category_dict(archive_category(slug=slug))
        except PublishError as e:
            return _err_category(str(e))
