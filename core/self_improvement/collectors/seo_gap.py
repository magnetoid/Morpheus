"""seo_gap collector — daily SEO debt scan.

Queries `catalog.Product` and `cms.Page` for SEO fields the merchant
hasn't filled in (meta_description, og_title, og_image, image
alt_text). Each gap becomes one signal — the analyzer rolls them up
into a single recommendation per class ("Add alt text to 47 product
images" rather than 47 individual rows).

Daily cadence (03:30 UTC, per the plan's beat schedule). The scan is
cheap — three indexed counts + a sampled detail pull for the top-N
offenders.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from core.self_improvement.collectors.base import Collector, Signal
from core.self_improvement.services import fingerprint_for

logger = logging.getLogger('morpheus.self_improvement.seo_gap')

SOURCE = 'seo_gap'

# Top-N offenders to surface per gap class. Above this, the analyzer
# is told "and N more" rather than carrying N rows in the signal.
SAMPLE_CAP = 200


class SeoGapCollector(Collector):
    name = SOURCE

    def run(self) -> Iterable[Signal]:
        Product = self._product_model()
        Page = self._page_model()
        ProductImage = self._product_image_model()

        if Product is not None:
            yield from self._product_missing_meta(Product)
            yield from self._product_missing_og(Product)
        if ProductImage is not None:
            yield from self._image_missing_alt(ProductImage)
        if Page is not None:
            yield from self._page_missing_meta(Page)

    # ------------------------------------------------------------------

    def _product_missing_meta(self, Product) -> Iterable[Signal]:
        qs = (
            self._active(Product).filter(meta_description='').values_list('pk', 'slug')[:SAMPLE_CAP]
        )
        for pk, slug in qs:
            yield Signal(
                source=SOURCE,
                fingerprint=fingerprint_for(SOURCE, 'product_meta_description', pk),
                severity=45,
                payload={
                    'gap': 'product_meta_description',
                    'product_pk': str(pk),
                    'slug': slug or '',
                },
            )

    def _product_missing_og(self, Product) -> Iterable[Signal]:
        qs = self._active(Product).filter(og_title='').values_list('pk', 'slug')[:SAMPLE_CAP]
        for pk, slug in qs:
            yield Signal(
                source=SOURCE,
                fingerprint=fingerprint_for(SOURCE, 'product_og_title', pk),
                severity=35,
                payload={
                    'gap': 'product_og_title',
                    'product_pk': str(pk),
                    'slug': slug or '',
                },
            )

    def _image_missing_alt(self, ProductImage) -> Iterable[Signal]:
        qs = ProductImage.objects.filter(alt_text='').values_list('pk', 'product_id')[:SAMPLE_CAP]
        for pk, product_id in qs:
            yield Signal(
                source=SOURCE,
                fingerprint=fingerprint_for(SOURCE, 'product_image_alt', pk),
                severity=50,
                payload={
                    'gap': 'product_image_alt',
                    'image_pk': str(pk),
                    'product_pk': str(product_id) if product_id else '',
                },
            )

    def _page_missing_meta(self, Page) -> Iterable[Signal]:
        qs = Page.objects.filter(meta_description='').values_list('pk', 'slug')[:SAMPLE_CAP]
        for pk, slug in qs:
            yield Signal(
                source=SOURCE,
                fingerprint=fingerprint_for(SOURCE, 'cms_page_meta_description', pk),
                severity=40,
                payload={
                    'gap': 'cms_page_meta_description',
                    'page_pk': str(pk),
                    'slug': slug or '',
                },
            )

    @staticmethod
    def _active(Product):
        """Narrow to live products. Status field name varies by codebase
        version, so we feature-detect — falls back to the full queryset."""
        try:
            return Product.objects.filter(status='active')
        except Exception:  # noqa: BLE001 — fall back to unfiltered if status missing
            return Product.objects.all()

    @staticmethod
    def _product_model():
        from django.apps import apps  # noqa: PLC0415

        try:
            return apps.get_model('catalog', 'Product')
        except LookupError:
            return None

    @staticmethod
    def _product_image_model():
        from django.apps import apps  # noqa: PLC0415

        try:
            return apps.get_model('catalog', 'ProductImage')
        except LookupError:
            return None

    @staticmethod
    def _page_model():
        from django.apps import apps  # noqa: PLC0415

        try:
            return apps.get_model('cms', 'Page')
        except LookupError:
            return None
