"""Order-side forms: refunds, fulfillments, draft orders."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.app import forms

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
    settle = forms.ChoiceField(required=False, choices=[('', '')])

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)
        from plugins.installed.orders.refunds import default_settle
        from plugins.installed.orders.tasks import OFFLINE_GATEWAYS

        offline = (getattr(order, 'payment_gateway', '') or '') in OFFLINE_GATEWAYS
        choices = [
            (
                '',
                'Record it now and pay it back by hand later'
                if offline
                else 'Back to the payment the customer used',
            )
        ]
        if getattr(order, 'customer_id', None):
            choices.append(('store_credit', "Add it to the customer's store credit"))
        choices.append(('external', 'Already paid back outside the store (cash, bank transfer)'))
        self.fields['settle'].choices = choices
        self.fields['settle'].initial = default_settle(order) if order is not None else ''

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

    def save(self, *, actor=None) -> Any:
        # Through RefundService, like every other refund path: it locks the
        # order and reuses an identical pending row, so a double-clicked
        # "Refund" can't create two rows — each with its own gateway
        # idempotency key — and refund the customer twice.
        from plugins.installed.orders.refunds import RefundService

        if self.order is None:
            raise ValueError('RefundForm.save() requires an order.')

        currency = str(getattr(self.order.total, 'currency', 'USD'))
        return RefundService.process(
            order=self.order,
            amount=_money(self.cleaned_data['amount'], currency),
            reason=self.cleaned_data['reason'],
            notes=self.cleaned_data.get('notes') or '',
            actor=actor,
            settle=self.cleaned_data.get('settle') or '',
        )


class FulfillmentForm(forms.Form):
    """One parcel of an order: how many units of each open line go in it, and
    its tracking. Saving goes through ``orders.fulfilment.create_fulfillment``,
    the one path every parcel takes (Linda's tool and the supplier apps too).
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
        help_text='When this parcel completes the order, also mark it shipped.',
    )

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)
        self.lines = []
        from plugins.installed.orders.fulfilment import marks_shipped_default, open_lines

        self.fields['mark_shipped'].initial = marks_shipped_default()
        if order is None:
            return

        for item, remaining in open_lines(order):
            name = f'qty_{item.pk}'
            self.fields[name] = forms.IntegerField(
                min_value=0, max_value=remaining, initial=remaining, required=False
            )
            self.lines.append({'item': item, 'remaining': remaining, 'field': name})

    def bound_lines(self):
        """The open lines with their quantity inputs, for the template."""
        return [dict(line, bound=self[line['field']]) for line in self.lines]

    def clean(self):
        cd = super().clean()
        if self.lines and not any(cd.get(line['field']) for line in self.lines):
            raise forms.ValidationError('Choose at least one unit to ship.')
        return cd

    def save(self):
        from plugins.installed.orders.fulfilment import create_fulfillment

        if self.order is None:
            raise ValueError('FulfillmentForm.save() requires an order.')
        cd = self.cleaned_data
        lines = {str(line['item'].pk): cd.get(line['field']) or 0 for line in self.lines}
        return create_fulfillment(
            self.order,
            lines,
            tracking_number=cd.get('tracking_number') or '',
            tracking_url=cd.get('tracking_url') or '',
            carrier=cd.get('carrier') or '',
            notes=cd.get('notes') or '',
            status=cd['status'],
            mark_shipped=bool(cd.get('mark_shipped')),
        )


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

        from plugins.registry import app_registry

        if not app_registry.is_active('draft_orders'):
            raise ValueError('DraftOrderForm.save() requires the draft_orders app.')
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
