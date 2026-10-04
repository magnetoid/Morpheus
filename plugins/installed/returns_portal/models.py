"""Returns portal: retention-layer extensions of the canonical return.

The return itself is ``orders.ReturnRequest`` (rma_number, state machine,
refund wiring — see plugins/installed/orders/refunds.py). This plugin adds
the retention surface on top: which resolution the customer picked
(exchange and store credit retain more revenue than a refund), the
exchange targets, and the "we learned something" feedback box. One concept,
one owner — these models extend the canonical row, they never redefine it.
"""

from __future__ import annotations

from morpheus.app import models


class ReturnResolution(models.Model):
    """The customer's chosen outcome for a canonical return request."""

    RESOLUTION_CHOICES = (
        ('refund', 'Refund'),
        ('exchange', 'Exchange'),
        ('store_credit', 'Store credit'),
    )

    request = models.OneToOneField(
        'orders.ReturnRequest',
        on_delete=models.CASCADE,
        related_name='portal_resolution',
    )
    resolution = models.CharField(max_length=12, choices=RESOLUTION_CHOICES, default='exchange')
    # Mirrors the shape of orders.ReturnRequest.items:
    # [{order_item_id, exchange_variant_id}] — only for resolution='exchange'.
    exchange_choices = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.resolution} for RMA {self.request.rma_number}'


class ReturnFeedback(models.Model):
    """The "we learned something" box, attached to the canonical return."""

    request = models.OneToOneField(
        'orders.ReturnRequest',
        on_delete=models.CASCADE,
        related_name='portal_feedback',
    )
    what_went_wrong = models.TextField(blank=True)
    what_would_have_made_it_right = models.TextField(blank=True)
    nps_score = models.IntegerField(default=0, help_text='0-10')
    # The feedback is also routed to the `crm` plugin's lead pipeline as a
    # recovery opportunity; this records when.
    routed_to_crm_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Feedback for RMA {self.request.rma_number}'
