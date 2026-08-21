import strawberry

from api.graphql_permissions import PermissionDenied
from core.graphql.types import MoneyType
from plugins.installed.orders.graphql.inputs import AddressInput


@strawberry.type
class ShippingRateQuoteType:
    rate_id: str
    name: str
    amount: MoneyType
    estimated_days_min: int = 0
    estimated_days_max: int = 0
    zone: str = ''


@strawberry.type
class ShippingQueryExtension:
    @strawberry.field(
        description='List available shipping rates for a cart and destination address'
    )
    def shipping_rates(
        self,
        info: strawberry.Info,
        cart_id: strawberry.ID,
        address: 'AddressInput',
    ) -> list[ShippingRateQuoteType]:
        from plugins.installed.orders.graphql._ownership import may_access_cart
        from plugins.installed.orders.models import Cart
        from plugins.installed.shipping.services import list_available_rates

        cart = (
            Cart.objects.prefetch_related('items', 'items__product', 'items__variant')
            .filter(id=cart_id)
            .first()
        )
        if cart is None:
            return []

        # Same ownership seam the orders plugin uses — never a second copy that
        # can drift looser (shipping declares requires=['orders']).
        if not may_access_cart(info, cart):
            raise PermissionDenied('Not allowed to read this cart')

        addr = {
            'country': address.country or '',
            'region': getattr(address, 'state', '') or '',
        }
        rates = list_available_rates(cart=cart, country=addr['country'], region=addr['region'])

        out: list[ShippingRateQuoteType] = []
        for r in rates:
            m = r.get('amount')
            out.append(
                ShippingRateQuoteType(
                    rate_id=str(r.get('rate_id') or ''),
                    name=str(r.get('name') or ''),
                    amount=MoneyType(
                        amount=str(getattr(m, 'amount', '0')),
                        currency=str(getattr(m, 'currency', 'USD')),
                    ),
                    estimated_days_min=int(r.get('estimated_days_min') or 0),
                    estimated_days_max=int(r.get('estimated_days_max') or 0),
                    zone=str(r.get('zone') or ''),
                )
            )
        return out
