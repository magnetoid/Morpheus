import strawberry

from api.graphql_permissions import get_request, has_scope
from plugins.installed.orders.models import Order
from plugins.installed.payments.services.routing import create_payment_intent_for


@strawberry.type
class PaymentResult:
    success: bool
    client_secret: str | None = None
    transaction_id: str | None = None
    error: str | None = None


@strawberry.type
class PaymentsMutationExtension:
    @strawberry.mutation(description='Create a payment intent for an order')
    def create_payment_intent(
        self, info: strawberry.Info, order_id: str, gateway: str | None = None
    ) -> PaymentResult:
        try:
            # A payment intent (and its client_secret) is order-scoped: only
            # the order's own customer or staff may mint one. Without this,
            # any caller could read the client_secret for an arbitrary order.
            order = Order.objects.get(id=order_id)
            request = get_request(info)
            user = getattr(request, 'user', None) if request else None
            owns = (
                user is not None
                and getattr(user, 'is_authenticated', False)
                and order.customer_id == user.pk
            )
            # Staff reach any order through the orders scope (a token's
            # service user is staff whatever its scopes, so never is_staff).
            if not (owns or has_scope(info, 'orders.write')):
                return PaymentResult(success=False, error='Order not found')
            # Route via the registry. None/unknown/disabled slug -> default
            # (stripe), so the existing Stripe behaviour is the fallback.
            result = create_payment_intent_for(order, gateway)
            return PaymentResult(
                success=result.get('success', False),
                client_secret=result.get('client_secret'),
                transaction_id=str(result.get('transaction_id'))
                if result.get('transaction_id')
                else None,
                error=result.get('error'),
            )
        except Order.DoesNotExist:
            return PaymentResult(success=False, error='Order not found')
