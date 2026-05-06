import strawberry
import strawberry_django
from typing import List, Optional
from plugins.installed.orders import models
from core.graphql.types import MoneyType


def _money(value, currency_fallback='USD') -> MoneyType:
    if value is None:
        return MoneyType(amount='0', currency=currency_fallback)
    if hasattr(value, 'amount'):
        return MoneyType(amount=str(value.amount), currency=str(value.currency))
    return MoneyType(amount=str(value), currency=currency_fallback)


@strawberry.type
class CartImageRef:
    url: str
    alt_text: str = ''


@strawberry.type
class CartProductRef:
    """Minimal product fields the cart needs — full ProductType would
    create a circular import between orders and catalog. Shape mirrors
    the catalog ProductType (`primaryImage { url altText }`) so the
    storefront's CART_QUERY works without changes."""
    id: strawberry.ID
    name: str
    slug: str
    primary_image: Optional[CartImageRef] = None


@strawberry.type
class CartVariantRef:
    id: strawberry.ID
    name: str
    sku: str


@strawberry.type
class CartCouponRef:
    code: str
    discount_type: str
    discount_value: str


@strawberry.type
class CartGiftCardRef:
    code: str
    balance: str
    currency: str


@strawberry.type
class CartTotalsType:
    subtotal: MoneyType
    shipping: MoneyType
    tax: MoneyType
    discount: MoneyType
    total: MoneyType
    shipping_rate_id: str = ''
    shipping_rate_name: str = ''


@strawberry_django.type(models.OrderItem)
class OrderItemType:
    id: strawberry.ID
    product_name: str
    variant_name: str
    sku: str
    quantity: int

    @strawberry.field
    def unit_price(self) -> MoneyType:
        return _money(self.unit_price)

    @strawberry.field
    def total_price(self) -> MoneyType:
        return _money(self.total_price)


@strawberry_django.type(models.Order)
class OrderType:
    id: strawberry.ID = strawberry.field(description="Unique order identifier")
    order_number: str = strawberry.field(description="Human readable order number")
    email: str = strawberry.field(description="Customer email")
    status: str = strawberry.field(description="Order status: pending, confirmed, processing, shipped, etc.")

    @strawberry.field
    def subtotal(self) -> MoneyType:
        return _money(self.subtotal)

    @strawberry.field
    def total(self) -> MoneyType:
        return _money(self.total)

    items: List[OrderItemType] = strawberry.field(description="Items purchased in this order")


@strawberry_django.type(models.CartItem)
class CartItemType:
    id: strawberry.ID
    quantity: int

    @strawberry.field
    def unit_price(self) -> MoneyType:
        return _money(self.unit_price)

    @strawberry.field
    def total_price(self) -> MoneyType:
        return _money(self.total_price)

    @strawberry.field
    def product(self) -> Optional[CartProductRef]:
        p = self.product
        if p is None:
            return None
        primary = getattr(p, 'primary_image', None)
        img = None
        if primary and getattr(primary, 'image', None):
            img = CartImageRef(
                url=primary.image.url,
                alt_text=getattr(primary, 'alt_text', '') or '',
            )
        return CartProductRef(id=str(p.id), name=p.name, slug=p.slug, primary_image=img)

    @strawberry.field
    def variant(self) -> Optional[CartVariantRef]:
        v = self.variant
        if v is None:
            return None
        return CartVariantRef(id=str(v.id), name=v.name or '', sku=v.sku or '')


@strawberry_django.type(models.Cart)
class CartType:
    id: strawberry.ID = strawberry.field(description="Cart identifier")
    session_key: str = strawberry.field(description="Session key for anonymous carts")
    items: List[CartItemType] = strawberry.field(description="Items in the cart")

    @strawberry.field
    def item_count(self) -> int:
        return self.item_count

    @strawberry.field
    def subtotal(self) -> MoneyType:
        # Cart.subtotal is a Decimal property (sums line items in Python).
        # Currency comes from the first item; default to USD on empty cart.
        from decimal import Decimal
        currency = 'USD'
        first = self.items.first()
        if first is not None and hasattr(first.unit_price, 'currency'):
            currency = str(first.unit_price.currency)
        return MoneyType(amount=str(self.subtotal or Decimal('0')), currency=currency)

    @strawberry.field
    def coupon(self) -> Optional[CartCouponRef]:
        c = self.coupon
        if c is None:
            return None
        return CartCouponRef(
            code=c.code,
            discount_type=c.discount_type,
            discount_value=str(c.discount_value),
        )

    @strawberry.field
    def gift_card(self) -> Optional[CartGiftCardRef]:
        gc = getattr(self, 'gift_card', None)
        if gc is None:
            return None
        return CartGiftCardRef(
            code=gc.code,
            balance=str(gc.balance.amount),
            currency=str(gc.balance.currency),
        )
