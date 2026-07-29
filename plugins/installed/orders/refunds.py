"""Refund + RMA (Return Merchandise Authorization) services and models.

Models live in `models.py` historically; the new `ReturnRequest` is added
here via a separate migration to keep this PR's scope tight.

Flow:
1. Customer or agent submits a `ReturnRequest` for line items they want
   to return. State: `requested`.
2. Merchant (or AccountManager agent) approves → `approved` + RMA number.
3. Items physically arrive → `received`.
4. Refund is created via `RefundService.process_for_return(...)` →
   Stripe refund call → state moves to `refunded`. Fires
   `PAYMENT_REFUNDED` + `return.refunded` events.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from djmoney.models.fields import MoneyField
from djmoney.money import Money

from morpheus.core import hook_registry

logger = logging.getLogger('morpheus.orders.refunds')


class ReturnRequest(models.Model):
    """Customer- or staff-initiated return."""

    STATE_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('received', 'Received'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    REASON_CHOICES = [
        ('defective', 'Defective'),
        ('wrong_item', 'Wrong item'),
        ('not_as_described', 'Not as described'),
        ('changed_mind', 'Changed mind'),
        ('damaged_in_transit', 'Damaged in transit'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='return_requests',
    )
    rma_number = models.CharField(max_length=32, unique=True, blank=True)
    state = models.CharField(
        max_length=12, choices=STATE_CHOICES, default='requested', db_index=True
    )
    reason = models.CharField(max_length=25, choices=REASON_CHOICES, default='other')
    customer_note = models.TextField(blank=True)
    staff_note = models.TextField(blank=True)
    items = models.JSONField(
        default=list,
        help_text='List of {order_item_id, quantity} for items being returned.',
    )
    refund_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
        help_text='Computed at approval time; used by RefundService.',
    )
    refund = models.ForeignKey(
        'orders.Refund',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='returns',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_returns',
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_returns',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'state']),
        ]

    def __str__(self) -> str:
        return f'RMA {self.rma_number or self.id} ({self.state})'

    def save(self, *args, **kwargs):
        if not self.rma_number:
            # RMA-YYMMDDxxxx — short and human-readable
            self.rma_number = f'RMA-{timezone.now().strftime("%y%m%d")}{str(self.id)[:6].upper()}'
        super().save(*args, **kwargs)


class RefundService:
    """Process refunds against the underlying payment provider."""

    @classmethod
    @transaction.atomic
    def process(
        cls,
        *,
        order,
        amount: Money,
        reason: str = 'customer_request',
        notes: str = '',
        actor=None,
    ) -> Refund:  # noqa: F821
        """Create a Refund row and call the provider. Idempotent on
        ``(order, amount, reason)`` — retries reuse the same Refund row
        (which carries a deterministic Stripe idempotency_key) so the
        provider can never be billed twice."""
        from plugins.installed.orders.models import Refund

        # Guard against over-refunding: the sum of already-processed refunds
        # plus this one must not exceed what was charged (order.total). The
        # dashboard form enforces this, but the returns portal / agent / MCP
        # paths reach process() directly and used to bypass any cap.
        already = sum(
            (r.amount.amount for r in order.refunds.filter(is_processed=True)),
            Decimal('0'),
        )
        ceiling = Decimal(order.total.amount)
        if already + Decimal(amount.amount) > ceiling:
            remaining = ceiling - already
            raise ValueError(
                f'Refund of {amount} exceeds the remaining refundable balance '
                f'({remaining} {amount.currency}) on order {order.order_number}.'
            )

        # Dedup regardless of `is_processed` — if a previous attempt
        # crashed mid-flight it'll be a row with `is_processed=False`,
        # and we want to RESUME it, not create a sibling.
        #
        # `notes` is part of the key so two genuinely-DISTINCT refunds of the
        # same value don't collide and silently move no money (deep-debug #8):
        # the returns flow stamps a unique `notes=f'RMA {rma_number}'` per RMA
        # (rma_number is unique), so two equal-priced returns resolve to two
        # refunds. A true retry passes identical (order, amount, reason, notes)
        # and still resumes the same row. Callers wanting guaranteed idempotency
        # for equal-value goodwill refunds should pass a distinguishing `notes`.
        refund = (
            Refund.objects.select_for_update()
            .filter(order=order, amount=amount, reason=reason, notes=notes)
            .first()
        )
        if refund is None:
            refund = Refund.objects.create(
                order=order,
                amount=amount,
                reason=reason,
                notes=notes,
            )
        elif refund.is_processed:
            return refund

        # Drive the ACTUAL provider refund through the payments plugin — the
        # same 'refund.requested' path the dashboard uses. This used to call a
        # broken inline `_provider_refund` that filtered payments by statuses
        # the model never uses and read a `stripe_charge_id` nothing writes, so
        # it always short-circuited to success-without-a-call: the customer got
        # a "refunded" email while zero money moved. The payments handler now
        # marks is_processed on gateway success and fires PAYMENT_REFUNDED (the
        # refund email / affiliate clawback / conversion pixel) — exactly once,
        # only when money actually moved.
        hook_registry.fire('refund.requested', refund=refund, actor=actor)
        refund.refresh_from_db()
        if not refund.is_processed:
            logger.warning(
                'orders: refund %s recorded but no gateway refund completed '
                '(COD/manual order, or gateway failure) — left for reconciliation',
                refund.id,
            )
        return refund


class ReturnService:
    """Lifecycle of a `ReturnRequest`."""

    @classmethod
    def create_request(
        cls,
        *,
        order,
        items: list[dict],
        reason: str = 'other',
        customer_note: str = '',
        requested_by=None,
    ) -> ReturnRequest:
        rr = ReturnRequest.objects.create(
            order=order,
            reason=reason,
            items=items,
            customer_note=customer_note,
            requested_by=requested_by,
        )
        hook_registry.fire('return.requested', return_request=rr, order=order)
        # Fan-out to the staff notifications center so the dashboard bell
        # shows it on the next page load. Optional plugin — fail-soft.
        try:
            from plugins.installed.notifications_center.services import notify_all_staff

            notify_all_staff(
                kind='returns.requested',
                title=f'Return requested — {rr.rma_number}',
                body=f'Order #{order.order_number} · reason: {rr.get_reason_display()}',
                action_url=f'/dashboard/returns/{rr.id}/',
                icon='undo-2',
            )
        except Exception:  # noqa: BLE001, S110
            pass
        return rr

    @classmethod
    def approve(
        cls, rr: ReturnRequest, *, decided_by=None, refund_amount: Money | None = None
    ) -> ReturnRequest:
        if rr.state != 'requested':
            raise ValueError(f'Cannot approve from state {rr.state}')
        if refund_amount is None:
            refund_amount = cls._compute_refund(rr)
        rr.state = 'approved'
        rr.decided_by = decided_by
        rr.refund_amount = refund_amount
        rr.save(update_fields=['state', 'decided_by', 'refund_amount', 'updated_at'])
        hook_registry.fire('return.approved', return_request=rr)
        return rr

    @classmethod
    def reject(cls, rr: ReturnRequest, *, decided_by=None, staff_note: str = '') -> ReturnRequest:
        if rr.state != 'requested':
            raise ValueError(f'Cannot reject from state {rr.state}')
        rr.state = 'rejected'
        rr.decided_by = decided_by
        rr.staff_note = staff_note
        rr.save(update_fields=['state', 'decided_by', 'staff_note', 'updated_at'])
        hook_registry.fire('return.rejected', return_request=rr)
        return rr

    @classmethod
    @transaction.atomic
    def mark_received_and_refund(
        cls,
        rr: ReturnRequest,
        *,
        actor=None,
        as_store_credit: bool = False,
    ) -> ReturnRequest:
        """Close out a return.

        ``as_store_credit=True`` issues the refund amount as store credit
        (no money moves through the gateway) instead of a monetary refund.
        Customer keeps the value in-store for a future order — better for
        merchants when the return reason is ``changed_mind``.

        Locks the ReturnRequest row via select_for_update so two staff
        members approving the same return concurrently can't both pass
        the state check and both fire a refund. The second caller waits
        for the lock, then sees state='refunded' and refuses.
        """
        # Re-fetch the row with a row-level lock so concurrent staff
        # actions on the same RMA serialise on the database, not on
        # whoever clicks first in the UI.
        rr = ReturnRequest.objects.select_for_update().get(pk=rr.pk)
        if rr.state not in ('approved', 'received'):
            raise ValueError(f'Cannot refund from state {rr.state}')
        if rr.state == 'approved':
            rr.state = 'received'
            rr.save(update_fields=['state', 'updated_at'])
        amount = rr.refund_amount
        if amount is None or amount.amount <= 0:
            amount = cls._compute_refund(rr)

        if as_store_credit:
            from plugins.installed.orders import store_credit

            customer = rr.order.customer
            if customer is None:
                raise ValueError('Cannot issue store credit on a guest order; do a money refund.')
            store_credit.issue(
                customer,
                amount=amount,
                reference=str(rr.id),
                note=f'Store credit from return {rr.rma_number}',
                created_by=actor,
            )
            rr.state = 'refunded'
            rr.save(update_fields=['state', 'updated_at'])
            hook_registry.fire(
                'return.refunded', return_request=rr, refund=None, store_credit=amount
            )
            return rr

        refund = RefundService.process(
            order=rr.order,
            amount=amount,
            reason='customer_request',
            notes=f'RMA {rr.rma_number}',
            actor=actor,
        )
        rr.refund = refund
        rr.state = 'refunded'
        rr.save(update_fields=['refund', 'state', 'updated_at'])
        hook_registry.fire('return.refunded', return_request=rr, refund=refund)
        return rr

    @staticmethod
    def _compute_refund(rr: ReturnRequest) -> Money:
        from plugins.installed.orders.models import OrderItem

        order = rr.order
        items_by_id = {str(it.id): it for it in OrderItem.objects.filter(order=order)}
        currency = str(order.total.currency)
        gross = Decimal('0')
        for entry in rr.items or []:
            oi = items_by_id.get(str(entry.get('order_item_id', '')))
            if not oi:
                continue
            qty = min(int(entry.get('quantity', 0) or 0), oi.quantity)
            currency = str(oi.unit_price.currency)
            gross += Decimal(oi.unit_price.amount) * qty

        # OrderItem stores only the pre-discount list price, but coupon /
        # gift-card / loyalty discounts live on Order.discount_total. Summing
        # line prices over-refunds every discounted order — store credit is
        # over-issued and a full money refund is blocked by the over-refund
        # ceiling in process(). Prorate the order-level discount onto the
        # returned lines by their share of the subtotal.
        subtotal = Decimal(order.subtotal.amount)
        discount = Decimal(order.discount_total.amount)
        if subtotal > 0 and discount > 0:
            gross -= discount * (gross / subtotal)

        # Safety ceiling: never exceed what's still refundable on the order
        # (order.total − already-processed refunds), regardless of proration
        # rounding. This also bounds the store-credit branch, which applies no
        # ceiling of its own.
        already = sum(
            (r.amount.amount for r in order.refunds.filter(is_processed=True)),
            Decimal('0'),
        )
        remaining = Decimal(order.total.amount) - already
        refundable = min(gross, remaining)
        if refundable < 0:
            refundable = Decimal('0')
        return Money(refundable.quantize(Decimal('0.01')), currency)
