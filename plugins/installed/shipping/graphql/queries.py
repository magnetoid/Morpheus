import strawberry

from api.graphql_permissions import PermissionDenied, has_scope
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
        from plugins.installed.orders.models import Cart
        from plugins.installed.shipping.services import list_available_rates

        request = (
            info.context.get('request')
            if isinstance(info.context, dict)
            else getattr(info.context, 'request', None)
        )
        cart = (
            Cart.objects.prefetch_related('items', 'items__product', 'items__variant')
            .filter(id=cart_id)
            .first()
        )
        if cart is None:
            return []

        if cart.customer_id is not None:
            user = getattr(request, 'user', None) if request else None
            if (  # noqa: SIM102
                not user
                or not getattr(user, 'is_authenticated', False)
                or user.pk != cart.customer_id
            ):  # noqa: SIM102
                if not has_scope(info, 'read:carts'):
                    raise PermissionDenied('Not allowed to read this cart')
        elif request is not None and getattr(request, 'session', None) is not None:
            if cart.session_key and cart.session_key != request.session.session_key:  # noqa: SIM102
                if not has_scope(info, 'read:carts'):
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
