import uuid
from morpheus import models
from djmoney.models.fields import MoneyField


class PaymentGateway(models.Model):
    GATEWAY_TYPES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('manual', 'Manual / Cash'),
        ('plugin', 'Plugin Gateway'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    gateway_type = models.CharField(max_length=20, choices=GATEWAY_TYPES)
    is_active = models.BooleanField(default=True)
    is_test_mode = models.BooleanField(default=True)
    config = models.JSONField(default=dict, help_text='Gateway-specific config (API keys etc.)')
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.name} ({'Test' if self.is_test_mode else 'Live'})"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('partially_refunded', 'Partially Refunded'),
        ('refunded', 'Refunded'),
        ('voided', 'Voided'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')

    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    amount_refunded = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)

    gateway_transaction_id = models.CharField(max_length=255, blank=True)
    gateway_payment_intent_id = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict)

    card_brand = models.CharField(max_length=20, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveSmallIntegerField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.amount} [{self.status}] for Order #{self.order.order_number}"


class StripeWebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    is_processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"{self.event_type} ({self.stripe_event_id})"


class PaymentMethod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='payment_methods', null=True, blank=True)
    provider = models.CharField(max_length=50, default='stripe')
    provider_id = models.CharField(max_length=128, help_text="e.g., pm_123456789")
    is_default = models.BooleanField(default=False)
    last4 = models.CharField(max_length=4, blank=True)
    brand = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.brand} ending in {self.last4}"

class PaymentTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='transactions')
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=50, default='stripe')
    provider_transaction_id = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Tx {self.id} for Order {self.order.order_number} - {self.status}"
