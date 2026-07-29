"""Referrals: customer-unique codes, referrer → referee attribution,
and the credit ledger entries the loyalty plugin actually pays out.

A `ReferralCode` is a customer's per-channel code. A `Referral` is
the attribution row: when the referee places their first qualifying
order, the referrer's code is recorded on the order, and a credit
ledger entry is queued for both sides.
"""

from __future__ import annotations

from morpheus.plugin import models


class ReferralCode(models.Model):
    customer = models.OneToOneField(
        'customers.Customer', on_delete=models.CASCADE, related_name='+'
    )
    code = models.SlugField(max_length=24, unique=True, db_index=True)
    channel = models.CharField(max_length=24, default='default')
    created_at = models.DateTimeField(auto_now_add=True)


class Referral(models.Model):
    STATE_CHOICES = (('pending', 'Pending'), ('credited', 'Credited'), ('reversed', 'Reversed'))

    referrer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    referee = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='+')
    code = models.SlugField(max_length=24)
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    credited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('referee', 'order')
