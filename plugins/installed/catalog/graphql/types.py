import strawberry
from typing import Optional, List
from datetime import datetime
import strawberry_django
from plugins.installed.catalog import models


@strawberry.type
class ImageType:
    url: str
    alt_text: Optional[str] = None
    is_primary: Optional[bool] = None
    sort_order: Optional[int] = None  # 0=front cover, 1=back cover, ≥2=slider
    webp_url: Optional[str] = None  # null when no WebP variant exists yet


@strawberry_django.type(models.Category)
class CategoryType:
    id: strawberry.ID = strawberry.field(description='Unique category identifier (UUID)')
    name: str = strawberry.field(description='Category display name')
    slug: str = strawberry.field(description='URL-safe identifier for deep linking')
    description: str = strawberry.field(description='Category description text')
    is_active: bool = strawberry.field(description='Whether this category is active')

    @strawberry.field
    def image(self) -> Optional[ImageType]:
        if not self.image:
            return None
        return ImageType(url=self.image.url, alt_text=self.name)

    @strawberry.field(description='Schema.org JSON-LD structured data for SEO')
    def structured_data(self) -> str:
        import json
        from plugins.installed.seo.services import _structured_data_for

        try:
            return json.dumps(
                _structured_data_for(
                    self,
                    title=self.name,
                    description=self.description,
                    image=self.image.url if self.image else '',
                ),
                ensure_ascii=False,
            )
        except Exception:
            return '{}'


@strawberry_django.type(models.AttributeGroup)
class AttributeGroupType:
    id: strawberry.ID
    name: str
    slug: str


@strawberry_django.type(models.Attribute)
class AttributeType:
    id: strawberry.ID
    name: str
    slug: str
    input_type: str
    is_variant: bool
    is_filterable: bool


@strawberry_django.type(models.AttributeValue)
class AttributeValueType:
    id: strawberry.ID
    name: str
    slug: str
    value: str


from core.graphql.types import MoneyType


@strawberry_django.type(models.Collection)
class CollectionType:
    id: strawberry.ID
    name: str
    slug: str
    description: str
    is_featured: bool

    @strawberry.field
    def image(self) -> Optional[ImageType]:
        if not self.image:
            return None
        return ImageType(url=self.image.url, alt_text=self.name)


@strawberry_django.type(models.ProductVariant)
class ProductVariantType:
    id: strawberry.ID = strawberry.field(description='Unique variant identifier (UUID)')
    name: str = strawberry.field(description='Variant name')
    sku: str = strawberry.field(description='Stock Keeping Unit')
    size: str = strawberry.field(
        description="Free-text size label (e.g. 'XL', '300 ml'). Independent of the AttributeValue M2M."
    )
    is_active: bool = strawberry.field(description='Whether this variant is active')
    sort_order: int = strawberry.field(description='Display order (lower = first)')
    localized_prices: strawberry.scalars.JSON = strawberry.field(
        description='JSON dict of explicit price overrides per currency'
    )
    # Shopify-parity fields (commit b74aaf9 + migration 0010).
    variant_type: str = strawberry.field(description='physical | digital | virtual')
    requires_shipping: bool = strawberry.field(
        description='When false, checkout skips the shipping step for this variant'
    )
    is_taxable: bool = strawberry.field(description='Per-variant taxability override')
    inventory_policy: str = strawberry.field(description='deny | continue (backorder behaviour)')
    barcode: str = strawberry.field(description='UPC / EAN / ISBN')

    @strawberry.field(
        description="Per-variant one-line description. Falls back to Product.short_description when the variant's own field is blank, so storefronts can render the field unconditionally."
    )
    def short_description(self) -> str:
        own = (getattr(self, 'short_description', '') or '').strip()
        if own:
            return own
        parent = getattr(self, 'product', None)
        return (getattr(parent, 'short_description', '') or '') if parent else ''

    @strawberry.field(
        description='Per-variant long-form description (HTML / Markdown). Falls back to Product.description when blank.'
    )
    def description(self) -> str:
        own = (getattr(self, 'description', '') or '').strip()
        if own:
            return own
        parent = getattr(self, 'product', None)
        return (getattr(parent, 'description', '') or '') if parent else ''

    @strawberry.field(
        description='Price of the variant. Falls back to Product.price when the variant has no override (Shopify-parity behaviour).'
    )
    def price(self) -> Optional[MoneyType]:
        own = self.price
        if own:
            return MoneyType(amount=str(own.amount), currency=str(own.currency))
        parent = getattr(self, 'product', None)
        parent_price = getattr(parent, 'price', None) if parent else None
        if parent_price:
            return MoneyType(amount=str(parent_price.amount), currency=str(parent_price.currency))
        return None

    @strawberry.field(
        description='Compare-at (was-price) for the variant. Falls back to Product.compare_at_price when blank, so the strikethrough renders on per-product sales even if the variant has no override.'
    )
    def compare_at_price(self) -> Optional[MoneyType]:
        own = getattr(self, 'compare_at_price', None)
        if own:
            return MoneyType(amount=str(own.amount), currency=str(own.currency))
        parent = getattr(self, 'product', None)
        parent_cap = getattr(parent, 'compare_at_price', None) if parent else None
        if parent_cap:
            return MoneyType(amount=str(parent_cap.amount), currency=str(parent_cap.currency))
        return None

    @strawberry.field(
        description='True when this specific variant is discounted (compare_at_price > price). Computed per-variant so the picker can badge only the discounted editions.'
    )
    def is_on_sale(self) -> bool:
        try:
            from decimal import Decimal

            own_price = self.price or (getattr(getattr(self, 'product', None), 'price', None))
            own_cap = getattr(self, 'compare_at_price', None) or getattr(
                getattr(self, 'product', None), 'compare_at_price', None
            )
            if not (own_price and own_cap):
                return False
            return Decimal(str(own_cap.amount)) > Decimal(str(own_price.amount))
        except Exception:  # noqa: BLE001
            return False

    @strawberry.field(description='Integer percent off when this variant is on sale, else 0.')
    def discount_percentage(self) -> int:
        try:
            from decimal import Decimal

            own_price = self.price or (getattr(getattr(self, 'product', None), 'price', None))
            own_cap = getattr(self, 'compare_at_price', None) or getattr(
                getattr(self, 'product', None), 'compare_at_price', None
            )
            if not (own_price and own_cap):
                return 0
            p = Decimal(str(own_price.amount))
            c = Decimal(str(own_cap.amount))
            if c <= p:
                return 0
            return int((c - p) / c * 100)
        except Exception:  # noqa: BLE001
            return 0

    @strawberry.field(description='Per-variant digital file URL (overrides Product.digital_file)')
    def digital_file_url(self) -> Optional[str]:
        f = getattr(self, 'digital_file', None)
        if f and getattr(f, 'name', ''):
            try:
                return f.url
            except Exception:  # noqa: BLE001
                return None
        return None

    @strawberry.field(
        description="Per-variant image URL. Falls back to the parent product's primary image when the variant has no image of its own, so the storefront picker always has a thumbnail."
    )
    def image_url(self) -> Optional[str]:
        # variant.image is an FK → ProductImage. Prefer its WebP variant
        # when present (smaller), else the original.
        own = getattr(self, 'image', None)
        if own is not None:
            webp = getattr(own, 'webp_image', None)
            if webp and getattr(webp, 'name', ''):
                try:
                    return webp.url
                except Exception:  # noqa: BLE001
                    pass
            base = getattr(own, 'image', None)
            if base and getattr(base, 'name', ''):
                try:
                    return base.url
                except Exception:  # noqa: BLE001
                    pass
        # Fallback: parent product's primary image.
        parent = getattr(self, 'product', None)
        primary = getattr(parent, 'primary_image', None) if parent else None
        if primary is not None and getattr(primary, 'image', None):
            try:
                return primary.image.url
            except Exception:  # noqa: BLE001
                return None
        return None


@strawberry_django.type(models.Product)
class ProductType:
    id: strawberry.ID = strawberry.field(description='Unique product identifier (UUID)')
    name: str = strawberry.field(description='Product display name')
    slug: str = strawberry.field(description='URL-safe identifier for deep linking')
    sku: str = strawberry.field(description='Stock Keeping Unit for simple products')
    product_type: str = strawberry.field(description='simple, variable, digital, bundle')
    status: str = strawberry.field(description='draft, active, archived')
    short_description: str = strawberry.field(description='Short summary description')
    description: str = strawberry.field(description='Full HTML or Markdown description')
    is_featured: bool = strawberry.field(description='Whether this product is featured')
    category: Optional[CategoryType] = strawberry.field(
        description="Primary category (hierarchical taxonomy — the product's 'shelf')"
    )
    variants: List[ProductVariantType] = strawberry.field(
        description='Available variants if variable product'
    )

    @strawberry.field(
        description="Curated Collections this product is featured in (flat merchandising sets — the 'tables' it's laid out on). Distinct from category."
    )
    def collections(self) -> List[CollectionType]:
        # Real Collection M2M (active only). Model instances → CollectionType.
        return list(self.collections.filter(is_active=True)) if hasattr(self, 'collections') else []

    is_on_sale: bool = strawberry.field(description='Whether the product is currently on sale')
    discount_percentage: int = strawberry.field(description='Discount percentage if on sale')

    @strawberry.field(description='Average rating from reviews')
    def average_rating(self) -> Optional[float]:
        # Prefer the queryset-level annotation (set in queries._REVIEW_ANNOTATIONS)
        # to avoid a per-card aggregate query. Falls back to the model property
        # when the annotation isn't present (e.g. single-Product lookups).
        cached = getattr(self, '_avg_rating', None)
        if cached is not None:
            return float(cached)
        prop = type(self).average_rating  # the underlying model property
        try:
            value = prop.fget(self) if hasattr(prop, 'fget') else self.average_rating
        except Exception:  # noqa: BLE001
            return None
        return float(value) if value is not None else None

    @strawberry.field(description='Number of approved reviews')
    def review_count(self) -> int:
        cached = getattr(self, '_review_count', None)
        if cached is not None:
            return int(cached)
        prop = type(self).review_count
        try:
            value = prop.fget(self) if hasattr(prop, 'fget') else self.review_count
        except Exception:  # noqa: BLE001
            return 0
        return int(value or 0)

    # Enterprise Localization
    localized_prices: strawberry.scalars.JSON = strawberry.field(
        description='JSON dict of explicit price overrides per currency'
    )
    localized_translations: strawberry.scalars.JSON = strawberry.field(
        description='JSON dict of translated strings (name, description) per locale'
    )

    @strawberry.field(description='Primary product image')
    def primary_image(self) -> Optional[ImageType]:
        # Iterate the prefetched cache (ordered by sort_order via Prefetch in
        # queries._PRODUCT_PREFETCH). Falling back to .filter()/.first() would
        # re-query and defeat the prefetch.
        img = None
        for candidate in self.images.all():
            if candidate.is_primary:
                img = candidate
                break
        if img is None:
            img = next(iter(self.images.all()), None)
        if not img or not img.image:
            return None
        return ImageType(
            url=img.image.url,
            alt_text=img.alt_text or self.name,
            is_primary=img.is_primary,
            sort_order=img.sort_order,
            webp_url=(img.webp_image.url if getattr(img, 'webp_image', None) else None),
        )

    @strawberry.field(description='All product images, ordered by sort_order ASC')
    def images(self) -> List[ImageType]:
        images = []
        # Consume the prefetched cache — ordering is established by the
        # Prefetch(queryset=ProductImage.objects.order_by('sort_order')) in
        # queries._PRODUCT_PREFETCH. Calling .order_by() here would re-query
        # and defeat the prefetch.
        for img in self.images.all():
            if not img.image:
                continue
            images.append(
                ImageType(
                    url=img.image.url,
                    alt_text=img.alt_text or self.name,
                    is_primary=img.is_primary,
                    sort_order=img.sort_order,
                    webp_url=(img.webp_image.url if getattr(img, 'webp_image', None) else None),
                )
            )
        return images

    @strawberry.field(description='Product tags')
    def tags(self) -> List[str]:
        return [t.name for t in self.tags.all()]

    @strawberry.field(description='Approved product reviews')
    def reviews(self) -> List['ReviewType']:
        return list(self.reviews.filter(is_approved=True))

    @strawberry.field(
        description="Display price. For Variable products with active variants returns the LOWEST variant.effective_price (so storefronts can render 'From $X' without a per-template min() reduction). For Simple / Digital / Bundle returns the parent price. Always non-null — falls back to Money(0, USD) when there is genuinely no price."
    )
    def price(self) -> MoneyType:
        if getattr(self, 'product_type', '') == 'variable':
            cheapest = None
            for v in self.variants.filter(is_active=True):
                ep = v.effective_price
                if ep is None:
                    continue
                if cheapest is None or ep.amount < cheapest.amount:
                    cheapest = ep
            if cheapest is not None:
                return MoneyType(amount=str(cheapest.amount), currency=str(cheapest.currency))
        own = self.price
        if own:
            return MoneyType(amount=str(own.amount), currency=str(own.currency))
        return MoneyType(amount='0', currency='USD')

    @strawberry.field(
        description="True when the displayed price is the minimum of multiple variants — storefronts should prefix with 'From '. False for Simple / Digital products."
    )
    def price_starts_from(self) -> bool:
        if getattr(self, 'product_type', '') != 'variable':
            return False
        return self.variants.filter(is_active=True).count() > 1

    @strawberry.field(description='Compare at price (original price before discount)')
    def compare_at_price(self) -> Optional[MoneyType]:
        if not self.compare_at_price:
            return None
        return MoneyType(
            amount=str(self.compare_at_price.amount), currency=str(self.compare_at_price.currency)
        )

    @strawberry.field(description='Schema.org JSON-LD structured data for SEO')
    def structured_data(self) -> str:
        import json
        from plugins.installed.seo.services import product_jsonld

        try:
            return json.dumps(product_jsonld(self), ensure_ascii=False)
        except Exception:
            return '{}'

    @strawberry.field(
        description=(
            'Agent-readable metadata: structured returns/sizing/availability/'
            'shipping/policies. Designed for AI shopping agents (ChatGPT, MCP, A2A) '
            "so they don't have to scrape the product page."
        )
    )
    def agent_metadata(self) -> 'AgentProductMetadata':
        from plugins.installed.catalog.graphql.types import AgentProductMetadata

        primary = self.primary_image
        primary_image_url = primary.image.url if primary and primary.image else ''
        return AgentProductMetadata(
            id=str(self.id),
            sku=self.sku or '',
            name=self.name,
            currency=str(self.price.currency) if self.price else 'USD',
            price_amount=str(self.price.amount) if self.price else '0.00',
            in_stock=any(v.is_active for v in self.variants.all()) or self.product_type == 'simple',
            requires_shipping=bool(self.requires_shipping),
            is_digital=self.product_type == 'digital',
            primary_image_url=primary_image_url,
            category_slug=self.category.slug if self.category_id else '',
            tags=[t.name for t in self.tags.all()],
            url_path=f'/p/{self.slug}',
        )


@strawberry.type
class AgentProductMetadata:
    """Stable, machine-friendly view of a product for AI agents."""

    id: strawberry.ID
    sku: str
    name: str
    currency: str
    price_amount: str
    in_stock: bool
    requires_shipping: bool
    is_digital: bool
    primary_image_url: str
    category_slug: str
    tags: List[str]
    url_path: str


@strawberry.type
class ReviewCustomerType:
    full_name: str


@strawberry_django.type(models.Review)
class ReviewType:
    id: strawberry.ID
    rating: int
    title: str
    body: str
    created_at: datetime

    @strawberry.field
    def customer(self) -> ReviewCustomerType:
        return ReviewCustomerType(full_name=self.customer.full_name)
