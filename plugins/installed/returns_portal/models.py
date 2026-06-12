"""Returns portal: return requests, exchanges, and feedback.

ReturnRequest is the entry. ReturnItem is the line-level state.
Exchange is the chosen replacement (optional). ReturnFeedback is
the "we learned something" box.
"""
from __future__ import annotations

from morpheus import models


class ReturnRequest(models.Model):
    STATE_CHOICES = (
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('refunded', 'Refunded'),
        ('exchanged', 'Exchanged'),
        ('store_credit', 'Store credit issued'),
        ('rejected', 'Rejected'),
    )
    RESOLUTION_CHOICES = (
        ('refund', 'Refund'),
        ('exchange', 'Exchange'),
        ('store_credit', 'Store credit'),
    )

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='+')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default='requested')
    resolution = models.CharField(max_length=12, choices=RESOLUTION_CHOICES, default='exchange')
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class ReturnItem(models.Model):
    request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items')
    line = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='+')
    quantity = models.PositiveIntegerField(default=1)
    # Optional exchange target
    exchange_variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )


class ReturnFeedback(models.Model):
    request = models.OneToOneField(ReturnRequest, on_delete=models.CASCADE, related_name='feedback')
    what_went_wrong = models.TextField(blank=True)
    what_would_have_made_it_right = models.TextField(blank=True)
    nps_score = models.IntegerField(default=0, help_text='0-10')
    # If `feedback_to_crm` is on, the feedback is also routed to the
    # `crm` plugin's lead pipeline as a recovery opportunity.
    routed_to_crm_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
