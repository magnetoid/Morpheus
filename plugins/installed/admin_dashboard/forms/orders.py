"""Order-side forms: refunds, fulfillments, draft orders."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus import forms

from ._helpers import _money


class RefundForm(forms.Form):
    """Issue a refund against an existing order."""

    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    reason = forms.ChoiceField(
        choices=[
            ('customer_request', 'Customer request'),
            ('defective', 'Defective product'),
            ('not_as_described', 'Not as described'),
            ('wrong_item', 'Wrong item sent'),
            ('other', 'Other'),
        ],
        initial='customer_request',
    )
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.order is not None:
            order_total = Decimal(str(self.order.total.amount))
            already_refunded = sum(
                (Decimal(str(r.amount.amount)) for r in self.order.refunds.all()),
                Decimal('0'),
            )
            if amount + already_refunded > order_total:
                raise forms.ValidationError(
                    f'Refund total would exceed order total ({order_total}).'
                )
        return amount

    def save(self) -> Any:
        from plugins.installed.orders.models import Refund

        if self.order is None:
            raise ValueError('RefundForm.save() requires an order.')

        currency = str(getattr(self.order.total, 'currency', 'USD'))
        refund = Refund.objects.create(
            order=self.order,
            amount=_money(self.cleaned_data['amount'], currency),
            reason=self.cleaned_data['reason'],
            notes=self.cleaned_data.get('notes') or '',
            is_processed=False,
        )
        self.order.log_event(
            'REFUND_CREATED',
            message=f'{refund.amount} — {refund.get_reason_display()}',
        )
        # Ask the payments plugin (or any other listener) to issue the
        # actual refund via the gateway. Failures are logged on the order
        # timeline; the local Refund record stays in place either way.
        try:
            from morpheus import hooks

            hooks.fire('refund.requested', refund=refund)
        except Exception:  # noqa: BLE001, S110
            pass
        return refund


class FulfillmentForm(forms.Form):
    """Create a `Fulfillment` row covering the entire order's items.

    A line-by-line partial-fulfillment editor would be the next step up;
    today's form ships the whole order in one Fulfillment record so staff
    can record tracking + carrier without leaving the dashboard.
    """

    status = forms.ChoiceField(
        choices=[
            ('pending', 'Pending'),
            ('in_transit', 'In transit'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('returned', 'Returned'),
        ],
        initial='in_transit',
    )
    tracking_number = forms.CharField(max_length=200, required=False)
    tracking_url = forms.URLField(required=False)
    carrier = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)
    mark_shipped = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Also transition the order to 'shipped'.",
    )

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def save(self):
        from django.utils import timezone

        from plugins.installed.orders.models import Fulfillment, FulfillmentItem

        if self.order is None:
            raise ValueError('FulfillmentForm.save() requires an order.')
        cd = self.cleaned_data
        f = Fulfillment.objects.create(
            order=self.order,
            status=cd['status'],
            tracking_number=cd.get('tracking_number') or '',
            tracking_url=cd.get('tracking_url') or '',
            carrier=cd.get('carrier') or '',
            notes=cd.get('notes') or '',
            shipped_at=timezone.now() if cd['status'] != 'pending' else None,
        )
        # Mirror every order item into the fulfillment so reports match.
        for item in self.order.items.all():
            remaining = max(item.quantity - item.fulfilled_quantity, 0)
            if remaining <= 0:
                continue
            FulfillmentItem.objects.create(
                fulfillment=f,
                order_item=item,
                quantity=remaining,
            )
            item.fulfilled_quantity = item.quantity
            item.save(update_fields=['fulfilled_quantity'])
        return f


class DraftOrderForm(forms.Form):
    """Bare-minimum draft order: pick a customer (or just an email) + a note.

    Lines are added on the draft detail page. Once lines exist staff can
    convert the draft to a real `orders.Order` via the existing flow.
    """

    customer = forms.UUIDField(required=False)
    customer_email = forms.EmailField(required=False)
    note = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cd = super().clean()
        if not cd.get('customer') and not cd.get('customer_email'):
            raise forms.ValidationError(
                'Select an existing customer or enter an email for a guest draft.'
            )
        return cd

    def save(self) -> Any:
        from django.contrib.auth import get_user_model

        from plugins.installed.draft_orders.models import DraftOrder

        User = get_user_model()

        cd = self.cleaned_data
        customer = None
        if cd.get('customer'):
            customer = User.objects.filter(pk=cd['customer']).first()

        draft = DraftOrder.objects.create(
            customer=customer,
            customer_email=(cd.get('customer_email') or (customer.email if customer else '')),
            note=cd.get('note') or '',
        )
        return draft
