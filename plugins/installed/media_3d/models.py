"""3D / AR assets attached to a product.

Two concrete asset URLs (one for Android Scene Viewer, one for iOS
Quick Look) and a `ShoppableVideo` for time-marker product cards.
The viewer template picks the correct one at render time.
"""

from __future__ import annotations

from morpheus import models


class Asset3D(models.Model):
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='asset_3d',
    )
    glb_url = models.URLField(blank=True, help_text='.glb for Android Scene Viewer')
    usdz_url = models.URLField(blank=True, help_text='.usdz for iOS Quick Look')
    poster_url = models.URLField(
        blank=True, help_text='Static poster shown when the device cannot render AR'
    )
    glb_size_bytes = models.PositiveIntegerField(
        default=0, help_text='Set on upload; reader template fast-fails over the budget'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '3D / AR asset'
        verbose_name_plural = '3D / AR assets'

    def __str__(self) -> str:
        return f'3D asset for {self.product.sku or self.product_id}'


class ShoppableVideo(models.Model):
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='shoppable_videos',
    )
    video_url = models.URLField()
    # A list of {time_seconds, product_slug} pairs as JSON.
    # Markers render in the storefront as inline product cards.
    markers_json = models.TextField(default='[]', blank=True)
    poster_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Shoppable video for {self.product.sku or self.product_id}'
