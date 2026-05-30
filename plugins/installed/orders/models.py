"""
Morpheus CMS - Orders Models
Cart → Order → Fulfillment pipeline
"""

import secrets
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.utils import timezone
from django_fsm import FSMField, transition
from djmoney.models.fields import MoneyField

from morpheus import models


def _gen_public_token() -> str:
    """Unguessable token for public order-confirmation access.

    Returned to the customer in checkout-redirect URL + email so guest
    checkouts (no account) can re-open their order without logging in.
    Logged-in customers see their own orders by FK; the token is the
    only path for guests.
    """
    return secrets.token_urlsafe(32)


class Cart(models.Model):
    """Session or customer cart."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.CASCADE, null=True, blank=True, related_name='carts'
    )
    session_key = models.CharField(max_length=100, blank=True)
    coupon = models.ForeignKey('marketing.Coupon', on_delete=models.SET_NULL, null=True, blank=True)
    gift_card = models.ForeignKey(
        'gift_cards.GiftCard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='Customer-applied gift card; redeemed against the cart at order time.',
    )
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['customer', '-updated_at']),
        ]

    def __str__(self):
        owner = self.customer.email if self.customer else self.session_key
        return f'Cart({owner})'

    @property
    def subtotal(self):
        # MoneyField stores the amount in the column with the field name itself.
        # Cross-row arithmetic stays Pythonic to avoid currency-mixing bugs.
        return sum(
            (Decimal(item.unit_price.amount) * item.quantity for item in self.items.all()),
            Decimal('0'),
        )

    @property
    def item_count(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.CASCADE, null=True, blank=True
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Must be at least 1; UI sends a delete instead when reaching 0.',
    )
    unit_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product', 'variant')

    def __str__(self):
        return f'{self.quantity}x {self.product.name}'

    @property
    def total_price(self):
        return self.unit_price * self.quantity


class OrderEvent(models.Model):
    """
    Immutable Event Source for Orders. Every state change is recorded here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50, db_index=True)
    previous_state = models.CharField(max_length=50, blank=True)
    new_state = models.CharField(max_length=50, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
        ]


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('partially_fulfilled', 'Partially Fulfilled'),
        ('fulfilled', 'Fulfilled'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    # Unguessable token for public access (guest-checkout confirmation
    # page, email links). Required to view the order without an
    # authenticated session matching `customer`.
    public_token = models.CharField(
        max_length=43, unique=True, default=_gen_public_token, editable=False
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    email = models.EmailField()
    status = FSMField(max_length=25, choices=STATUS_CHOICES, default='pending', protected=True)
    payment_status = models.CharField(max_length=25, default='unpaid')

    # Multi-Tenancy
    channel = models.ForeignKey(
        'core.StoreChannel', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders'
    )

    # Pricing
    subtotal = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    shipping_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    tax_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    discount_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')

    # Addresses (snapshot at order time)
    shipping_address = models.JSONField(default=dict)
    billing_address = models.JSONField(default=dict)

    # Coupon
    coupon_code = models.CharField(max_length=50, blank=True)

    # Shipping
    shipping_method = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=200, blank=True)

    # Notes
    customer_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)

    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    source = models.CharField(max_length=50, default='web')  # web, api, pos, etc.

    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-placed_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['email']),
            models.Index(fields=['channel', 'status']),
            models.Index(fields=['-placed_at']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f'Order #{self.order_number}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        if not self.public_token:
            # Belt-and-suspenders: the field has a default callable, but
            # an explicit blank string can still slip past if a caller
            # overrides it.
            self.public_token = _gen_public_token()
        super().save(*args, **kwargs)

    def _generate_order_number(self):
        # Use secrets (CSPRNG) so order numbers aren't predictable —
        # they're part of the public confirmation URL alongside the
        # public_token guard.
        prefix = 'MRP'
        suffix = ''.join(str(secrets.randbelow(10)) for _ in range(8))
        return f'{prefix}{suffix}'

    def log_event(self, event_type, message='', prev_state=''):
        OrderEvent.objects.create(
            order=self,
            event_type=event_type,
            previous_state=prev_state,
            new_state=self.status,
            message=message,
        )

    @transition(field=status, source='pending', target='confirmed')
    def confirm(self):
        self.log_event('ORDER_CONFIRMED', prev_state='pending')

    @transition(field=status, source='confirmed', target='processing')
    def process(self):
        self.log_event('ORDER_PROCESSING', prev_state='confirmed')

    @transition(
        field=status,
        source=['processing', 'partially_fulfilled'],
        target='fulfilled',
    )
    def fulfill(self):
        self.log_event('ORDER_FULFILLED', prev_state=self.status)

    @transition(
        field=status,
        source=['processing', 'fulfilled', 'partially_fulfilled'],
        target='shipped',
    )
    def ship(self, tracking_number: str = ''):
        if tracking_number:
            self.tracking_number = tracking_number
        self.log_event('ORDER_SHIPPED', message=tracking_number, prev_state=self.status)

    @transition(field=status, source='shipped', target='delivered')
    def deliver(self):
        self.log_event('ORDER_DELIVERED', prev_state='shipped')

    @transition(field=status, source='*', target='cancelled')
    def cancel(self, reason=''):
        prev = self.status
        self.cancelled_at = timezone.now()
        if reason:
            self.staff_notes += f'\nCancelled: {reason}'
        self.log_event('ORDER_CANCELLED', message=reason, prev_state=prev)


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True
    )

    # Snapshot data (in case product changes)
    product_name = models.CharField(max_length=300)
    variant_name = models.CharField(max_length=200, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(blank=True)

    quantity = models.PositiveIntegerField()
    unit_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    total_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')

    # Fulfillment
    fulfilled_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['product_name']

    def __str__(self):
        return f'{self.quantity}x {self.product_name} (Order #{self.order.order_number})'


class Fulfillment(models.Model):
    """Tracks shipment of order items."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('returned', 'Returned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='fulfillments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tracking_number = models.CharField(max_length=200, blank=True)
    tracking_url = models.URLField(blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Fulfillment for Order #{self.order.order_number}'


class FulfillmentItem(models.Model):
    fulfillment = models.ForeignKey(Fulfillment, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.quantity}x {self.order_item.product_name}'


class Refund(models.Model):
    """Order refunds."""

    REASON_CHOICES = [
        ('customer_request', 'Customer Request'),
        ('defective', 'Defective Product'),
        ('not_as_described', 'Not As Described'),
        ('wrong_item', 'Wrong Item Sent'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    reason = models.CharField(max_length=25, choices=REASON_CHOICES, default='other')
    notes = models.TextField(blank=True)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Refund {self.amount} for Order #{self.order.order_number}'


# ReturnRequest model is defined in refunds.py to keep that file self-contained.
# Re-export here so Django's app loader and makemigrations pick it up.
from plugins.installed.orders.refunds import ReturnRequest  # noqa: F401, E402


class StoreCredit(models.Model):
    """Per-customer store-credit balance.

    Balance is a denormalised running total updated by the
    ``StoreCreditService`` when a transaction is appended; the
    ``StoreCreditTxn`` table is the immutable ledger so the running
    total can always be rebuilt. We deliberately keep the balance on
    one row per customer (rather than aggregating on every read) so
    cart price calculation stays O(1) per checkout.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='store_credit',
    )
    balance = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.customer.email}: {self.balance}'


class StoreCreditTxn(models.Model):
    """Immutable ledger of store-credit changes.

    `kind='credit'` adds to the customer's balance (e.g. issued on a
    return refund); `kind='debit'` deducts (e.g. redeemed at checkout).
    `reference` is a free-form pointer to the originating object —
    typically a Refund/ReturnRequest UUID for credits, an Order UUID
    for debits — so the dashboard can render an audit trail.
    """

    KIND_CHOICES = [('credit', 'Credit'), ('debit', 'Debit')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='store_credit_txns',
    )
    kind = models.CharField(max_length=6, choices=KIND_CHOICES, db_index=True)
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    reference = models.CharField(max_length=64, blank=True, db_index=True)
    note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
        ]

    def __str__(self):
        sign = '+' if self.kind == 'credit' else '-'
        return f'{sign}{self.amount} ({self.reference or self.note})'
