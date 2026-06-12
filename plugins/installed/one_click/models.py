"""One-click device tokens.

Tokens are AES-GCM ciphertext (key from `settings.ONE_CLICK_KEY`,
32-byte Fernet-style). The plaintext binds {customer, payment
method id, shipping address id, device fingerprint}. We never
store plaintext payment data ourselves — that's the gateway's job
(Stripe PaymentMethod re-use).
"""

from __future__ import annotations

from morpheus import models


class OneClickToken(models.Model):
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='one_click_tokens',
    )
    encrypted_payload = models.TextField(help_text='AES-GCM ciphertext')
    device_label = models.CharField(max_length=120, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['customer', '-created_at'])]
