"""seo_gap collector — daily SEO debt scan.

Queries `catalog.Product`, `catalog.ProductImage` and `cms.Page` for the
SEO copy the merchant hasn't written. Each gap becomes one signal — the
analyzer rolls them up into a single recommendation per class ("Add alt
text to 47 product images" rather than 47 individual rows), and the
`meta_description` / `alt_text` healers repair them.

**A gap is what the page actually RENDERS empty, not what one column
holds.** Both of this collector's first two rules got that wrong (see
`core/self_improvement/tests/test_collectors.py::SeoGapCollectorTests`):

  * `cms.Page` has no `meta_description` column — it never has. Filtering
    on one raised FieldError, so every nightly run from 2026-06-01 to
    v0.69.0 died before collecting a single page gap (107 of 107 failed)
    and the collector showed permanently red. A page's description
    resolves from the seo overlay, then `excerpt`
    (`seo/pages/resolve.py:_description_from_object`).
  * A blank `Product.og_title` is NOT a gap: `og:title` renders from the
    page title when it's blank (`seo/services/_helpers.py:to_html`). That
    rule reported 648 of 861 live products as SEO debt no healer could
    ever repair.

Product/page descriptions live in two places — the native column and the
`seo.SeoMeta` overlay, which wins at render time (`resolve_meta`) — so a
blank column with a filled overlay is not a gap either.

Daily cadence (03:30 UTC, per the plan's beat schedule). The scan is
cheap — indexed counts plus one overlay lookup per model.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

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
        if ProductImage is not None:
            yield from self._image_missing_alt(ProductImage)
        if Page is not None:
            yield from self._page_missing_meta(Page)

    # ------------------------------------------------------------------

    def _product_missing_meta(self, Product) -> Iterable[Signal]:
        described = self._overlay_described(Product)
        rows = self._active(Product).filter(meta_description='').values_list('pk', 'slug')
        for pk, slug in self._sample(rows, skip=described):
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
        described = self._overlay_described(Page)
        rows = Page.objects.filter(excerpt='').values_list('pk', 'slug')
        for pk, slug in self._sample(rows, skip=described):
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

    # ------------------------------------------------------------------

    @staticmethod
    def _sample(rows, *, skip: set[str]) -> Iterator[tuple]:
        """Up to SAMPLE_CAP rows whose pk isn't in `skip`.

        Filtered here rather than in SQL because the overlay is a generic
        relation (`object_id` is a CharField, so it can't be joined), and
        applied BEFORE the cap so a run of covered rows can't eat the sample.
        """
        taken = 0
        for row in rows.iterator():
            if str(row[0]) in skip:
                continue
            yield row
            taken += 1
            if taken >= SAMPLE_CAP:
                return

    @staticmethod
    def _overlay_described(Model) -> set[str]:
        """`object_id`s of this model carrying a non-empty `SeoMeta.description`.

        The overlay wins at render (`seo.services.meta.resolve_meta`), so
        those pages do have a description whatever the native column says.
        Empty set when the seo app isn't installed — then the native column
        is the only source and every blank is a real gap.
        """
        from django.apps import apps  # noqa: PLC0415

        try:
            SeoMeta = apps.get_model('seo', 'SeoMeta')
        except LookupError:
            return set()
        from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

        ct = ContentType.objects.get_for_model(Model)
        return set(
            SeoMeta.objects.filter(content_type=ct)
            .exclude(description='')
            .values_list('object_id', flat=True)
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
