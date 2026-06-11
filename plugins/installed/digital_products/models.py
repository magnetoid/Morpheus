"""digital_products plugin — models."""

from __future__ import annotations

import secrets
import uuid

from morpheus import models


def _new_token() -> str:
    """URL-safe random token. ~256 bits of entropy."""
    return secrets.token_urlsafe(32)


class DownloadToken(models.Model):
    """A signed, expiring, count-limited download link for a digital order line.

    Created automatically by the plugin on ``events.ORDER_PAID``. The
    customer receives the download URL by email; each successful hit on
    the download view increments ``downloads_used`` and refuses past
    ``max_downloads`` or after ``expires_at``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=_new_token,
        help_text='Random URL-safe token used in the public download URL.',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='download_tokens',
    )
    order_item = models.ForeignKey(
        'orders.OrderItem',
        on_delete=models.CASCADE,
        related_name='download_tokens',
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='+',
    )
    expires_at = models.DateTimeField(db_index=True)
    max_downloads = models.PositiveIntegerField(default=5)
    downloads_used = models.PositiveIntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    last_downloaded_ip = models.GenericIPAddressField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'DownloadToken({self.product.name}, {self.downloads_used}/{self.max_downloads})'

    @property
    def is_active(self) -> bool:
        from django.utils import timezone

        if self.revoked_at:
            return False
        if self.downloads_used >= self.max_downloads:
            return False
        return self.expires_at > timezone.now()
