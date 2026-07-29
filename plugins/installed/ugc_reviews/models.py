"""UGC review attachments + creator program.

ReviewMedia is 1-N per review (photo or video). CreatorProgram
tracks who has been invited + who has accepted.
"""

from __future__ import annotations

from morpheus.plugin import models


class ReviewMedia(models.Model):
    KIND_CHOICES = (('photo', 'Photo'), ('video', 'Video'))

    review = models.ForeignKey(
        'catalog.Review',
        on_delete=models.CASCADE,
        related_name='media',
    )
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    url = models.URLField()
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0, help_text='For videos.')
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class CreatorInvite(models.Model):
    STATE_CHOICES = (
        ('invited', 'Invited'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    )

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='+',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='+',
    )
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='invited')
    invite_sent_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    stipend_credit_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-invite_sent_at']
        indexes = [models.Index(fields=['customer', '-invite_sent_at'])]
