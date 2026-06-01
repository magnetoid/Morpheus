import strawberry
from plugins.installed.payments.services.routing import create_payment_intent_for
from plugins.installed.orders.models import Order

@strawberry.type
class PaymentResult:
    success: bool
    client_secret: str | None = None
    transaction_id: str | None = None
    error: str | None = None

@strawberry.type
class PaymentsMutationExtension:
    @strawberry.mutation(description="Create a payment intent for an order")
    def create_payment_intent(self, order_id: str, gateway: str | None = None) -> PaymentResult:
        try:
            order = Order.objects.get(id=order_id)
            # Route via the registry. None/unknown/disabled slug -> default
            # (stripe), so the existing Stripe behaviour is the fallback.
            result = create_payment_intent_for(order, gateway)
            return PaymentResult(
                success=result.get('success', False),
                client_secret=result.get('client_secret'),
                transaction_id=str(result.get('transaction_id')) if result.get('transaction_id') else None,
                error=result.get('error')
            )
        except Order.DoesNotExist:
            return PaymentResult(success=False, error="Order not found")
