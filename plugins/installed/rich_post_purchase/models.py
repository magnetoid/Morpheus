"""Per-customer opt-in state for SMS / WhatsApp / push channels."""
from __future__ import annotations

from morpheus import models


class ChannelPreference(models.Model):
    CHANNEL_CHOICES = (('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('push', 'PWA push'))

    customer = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='+')
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES)
    opted_in_at = models.DateTimeField(auto_now_add=True)
    opted_out_at = models.DateTimeField(null=True, blank=True)
    # Encrypted (AES-GCM) phone number or push endpoint
    encrypted_endpoint = models.TextField(blank=True)

    class Meta:
        unique_together = ('customer', 'channel')
        ordering = ['channel']
