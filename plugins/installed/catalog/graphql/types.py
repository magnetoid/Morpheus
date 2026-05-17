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
    id: strawberry.ID = strawberry.field(description="Unique category identifier (UUID)")
    name: str = strawberry.field(description="Category display name")
    slug: str = strawberry.field(description="URL-safe identifier for deep linking")
    description: str = strawberry.field(description="Category description text")
    is_active: bool = strawberry.field(description="Whether this category is active")

    @strawberry.field
    def image(self) -> Optional[ImageType]:
        if not self.image:
            return None
        return ImageType(url=self.image.url, alt_text=self.name)

    @strawberry.field(description="Schema.org JSON-LD structured data for SEO")
    def structured_data(self) -> str:
        import json
        from plugins.installed.seo.services import _structured_data_for
        try:
            return json.dumps(_structured_data_for(self, title=self.name, description=self.description, image=self.image.url if self.image else ''), ensure_ascii=False)
        except Exception:
            return "{}"

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
    id: strawberry.ID = strawberry.field(description="Unique variant identifier (UUID)")
    name: str = strawberry.field(description="Variant name")
    sku: str = strawberry.field(description="Stock Keeping Unit")
    is_active: bool = strawberry.field(description="Whether this variant is active")
    localized_prices: strawberry.scalars.JSON = strawberry.field(description="JSON dict of explicit price overrides per currency")

    @strawberry.field(description="Price of the variant")
    def price(self) -> Optional[MoneyType]:
        if not self.price:
            return None
        return MoneyType(amount=str(self.price.amount), currency=str(self.price.currency))

@strawberry_django.type(models.Product)
class ProductType:
    id: strawberry.ID = strawberry.field(description="Unique product identifier (UUID)")
    name: str = strawberry.field(description="Product display name")
    slug: str = strawberry.field(description="URL-safe identifier for deep linking")
    sku: str = strawberry.field(description="Stock Keeping Unit for simple products")
    product_type: str = strawberry.field(description="simple, variable, digital, bundle")
    status: str = strawberry.field(description="draft, active, archived")
    short_description: str = strawberry.field(description="Short summary description")
    description: str = strawberry.field(description="Full HTML or Markdown description")
    is_featured: bool = strawberry.field(description="Whether this product is featured")
    category: Optional[CategoryType] = strawberry.field(description="Primary category")
    variants: List[ProductVariantType] = strawberry.field(description="Available variants if variable product")
    is_on_sale: bool = strawberry.field(description="Whether the product is currently on sale")
    discount_percentage: int = strawberry.field(description="Discount percentage if on sale")
    average_rating: Optional[float] = strawberry.field(description="Average rating from reviews")

    # Enterprise Localization
    localized_prices: strawberry.scalars.JSON = strawberry.field(description="JSON dict of explicit price overrides per currency")
    localized_translations: strawberry.scalars.JSON = strawberry.field(description="JSON dict of translated strings (name, description) per locale")

    @strawberry.field(description="Primary product image")
    def primary_image(self) -> Optional[ImageType]:
        img = self.primary_image
        if not img or not img.image:
            return None
        return ImageType(
            url=img.image.url,
            alt_text=img.alt_text or self.name,
            is_primary=img.is_primary,
            sort_order=img.sort_order,
            webp_url=(img.webp_image.url if getattr(img, 'webp_image', None) else None),
        )

    @strawberry.field(description="All product images, ordered by sort_order ASC")
    def images(self) -> List[ImageType]:
        images = []
        # Explicit order_by to override Meta.ordering's secondary
        # `-is_primary` key — the storefront's two-image cover relies on
        # sort_order==0 being the front and sort_order==1 the back.
        for img in self.images.order_by('sort_order'):
            if not img.image:
                continue
            images.append(ImageType(
                url=img.image.url,
                alt_text=img.alt_text or self.name,
                is_primary=img.is_primary,
                sort_order=img.sort_order,
                webp_url=(img.webp_image.url if getattr(img, 'webp_image', None) else None),
            ))
        return images

    @strawberry.field(description="Product tags")
    def tags(self) -> List[str]:
        return [t.name for t in self.tags.all()]

    @strawberry.field(description="Approved product reviews")
    def reviews(self) -> List['ReviewType']:
        return list(self.reviews.filter(is_approved=True))

    @strawberry.field(description="Base price of the product")
    def price(self) -> MoneyType:
        return MoneyType(amount=str(self.price.amount), currency=str(self.price.currency))

    @strawberry.field(description="Compare at price (original price before discount)")
    def compare_at_price(self) -> Optional[MoneyType]:
        if not self.compare_at_price:
            return None
        return MoneyType(amount=str(self.compare_at_price.amount), currency=str(self.compare_at_price.currency))

    @strawberry.field(description="Schema.org JSON-LD structured data for SEO")
    def structured_data(self) -> str:
        import json
        from plugins.installed.seo.services import product_jsonld
        try:
            return json.dumps(product_jsonld(self), ensure_ascii=False)
        except Exception:
            return "{}"

    @strawberry.field(
        description=(
            "Agent-readable metadata: structured returns/sizing/availability/"
            "shipping/policies. Designed for AI shopping agents (ChatGPT, MCP, A2A) "
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
