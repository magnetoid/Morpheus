import stripe
from django.conf import settings
from plugins.installed.payments.models import PaymentTransaction
from plugins.registry import plugin_registry

class PaymentService:
    """
    Law 5: Business Logic Lives in Services
    Handles interactions with Stripe and internal transaction records.
    """
    
    @classmethod
    def get_stripe_api_key(cls):
        plugin = plugin_registry.get('payments')
        if plugin:
            return plugin.get_config_value('stripe_secret_key', settings.STRIPE_SECRET_KEY)
        return settings.STRIPE_SECRET_KEY

    @classmethod
    def create_payment_intent(cls, order):
        """
        Creates a Stripe PaymentIntent for a given Order.
        """
        stripe.api_key = cls.get_stripe_api_key()
        
        # Calculate amount in cents
        amount_cents = int(order.total.amount * 100)
        
        try:
            # idempotency_key prevents duplicate intents on retry — if Stripe
            # has already seen the same key + amount, it returns the original
            # intent instead of charging twice.
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=order.total.currency.code.lower(),
                metadata={'order_id': str(order.id), 'order_number': order.order_number},
                idempotency_key=f'pi-{order.id}-{amount_cents}',
            )
            
            # Record the pending transaction
            tx = PaymentTransaction.objects.create(
                order=order,
                amount=order.total,
                status=PaymentTransaction.Status.PENDING,
                provider='stripe',
                provider_transaction_id=intent.id
            )
            
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "transaction_id": tx.id
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    @classmethod
    def process_webhook(cls, payload, sig_header):
        """
        Processes a Stripe webhook to update transaction statuses.
        """
        plugin = plugin_registry.get('payments')
        webhook_secret = plugin.get_config_value('stripe_webhook_secret', settings.STRIPE_WEBHOOK_SECRET)
        stripe.api_key = cls.get_stripe_api_key()
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            raise Exception("Invalid payload") from e
        except stripe.error.SignatureVerificationError as e:
            raise Exception("Invalid signature") from e

        # Handle the event
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            cls._mark_transaction_success(payment_intent.id)
        elif event.type == 'payment_intent.payment_failed':
            payment_intent = event.data.object
            cls._mark_transaction_failed(payment_intent.id, payment_intent.last_payment_error.message)
            
        return True

    @classmethod
    def _mark_transaction_success(cls, intent_id):
        """Idempotent — the `select_for_update` + status check guarantees
        ORDER_PAID fires exactly once per payment, even if Stripe retries
        the webhook concurrently (it does, aggressively)."""
        from django.db import transaction as db_tx
        from core.hooks import hook_registry, MorpheusEvents

        with db_tx.atomic():
            tx = (
                PaymentTransaction.objects
                .select_for_update()
                .filter(provider_transaction_id=intent_id)
                .first()
            )
            if not tx or tx.status == PaymentTransaction.Status.SUCCEEDED:
                return  # already processed — webhook retry, ignore

            tx.status = PaymentTransaction.Status.SUCCEEDED
            tx.save(update_fields=['status'])

            # Advance both Order columns. Status was previously left at
            # 'pending' so the dashboard kept showing paid orders as
            # unpaid; flip to 'confirmed' so the order list, fulfillment
            # queue, and analytics all see the correct state.
            order = tx.order
            order.payment_status = 'paid'
            if order.status in ('pending', 'draft'):
                order.status = 'confirmed'
                order.save(update_fields=['payment_status', 'status'])
            else:
                order.save(update_fields=['payment_status'])

        # Fire AFTER the transaction commits so subscribers see the new
        # row state and don't have to worry about partial writes.
        hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)

    @classmethod
    def _mark_transaction_failed(cls, intent_id, error_msg):
        tx = PaymentTransaction.objects.filter(provider_transaction_id=intent_id).first()
        if tx:
            tx.status = PaymentTransaction.Status.FAILED
            tx.error_message = error_msg
            tx.save()
