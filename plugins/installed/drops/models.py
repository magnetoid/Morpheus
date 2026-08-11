"""Drops + waitlist.

A `Drop` is a scheduled release of a product. `DropTicket` is the
queue position / raffle entry. `Waitlist` is the post-sellout
"email me when back" list.

The `inventory` plugin owns allocation; this plugin only schedules
when the allocation *opens* and the queue ordering.
"""

from __future__ import annotations

from morpheus.app import models


class Drop(models.Model):
    STATE_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('closed', 'Closed'),
    )
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='+')
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='scheduled')
    initial_stock = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at']
        indexes = [models.Index(fields=['state', 'starts_at'])]


class DropTicket(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name='tickets')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    position = models.PositiveIntegerField(default=0)
    raffle_seed = models.CharField(
        max_length=64,
        blank=True,
        help_text='For raffle drops: a deterministic seed for fair ordering.',
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    won_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['position']
        unique_together = ('drop', 'customer')


class Waitlist(models.Model):
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='+')
    joined_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('customer', 'product')
        ordering = ['joined_at']
