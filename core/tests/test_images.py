"""Store-wide image frame settings.

The bug these guard: the *shape* an image is shown in was hardcoded as a book
cover (`2 / 3`) in six dashboard frames and every theme card, because the first
store on this platform sold books. `catalog/image_pipeline.py` never reshapes
anything — Pillow's `thumbnail()` preserves the source ratio — so the frame was
the whole story, and the two settings that looked like they controlled it
(`grid_image_*`, `og_image_*`) had zero consumers in the entire tree.
"""

from __future__ import annotations

import json
import pathlib
import re

from django.template import Context, Template
from django.test import TestCase

from core import images


def _set(**values):
    """Write the catalog plugin's image config, the way the panel does."""
    from plugins.registry import app_registry

    plugin = app_registry.get('catalog')
    for key, value in values.items():
        plugin.set_config(key, value)
    plugin.invalidate_config_cache()


class ResolverTests(TestCase):
    def test_default_is_square_not_a_book_cover(self):
        self.assertEqual(images.aspect_ratio_key(), 'square')
        self.assertEqual(images.aspect_ratio_css(), '1 / 1')
        self.assertEqual(images.fit_mode(), 'cover')

    def test_a_chosen_shape_is_returned(self):
        _set(image_aspect_ratio='wide', image_fit='contain')
        self.assertEqual(images.aspect_ratio_css(), '16 / 9')
        self.assertEqual(images.fit_mode(), 'contain')

    def test_garbage_falls_back_rather_than_breaking_a_page(self):
        _set(image_aspect_ratio='banana', image_fit='sideways')
        self.assertEqual(images.aspect_ratio_key(), images.DEFAULT_ASPECT_RATIO)
        self.assertEqual(images.fit_mode(), images.DEFAULT_FIT)

    def test_original_imposes_no_ratio(self):
        _set(image_aspect_ratio='original')
        self.assertEqual(images.aspect_ratio_css(), 'auto')
        self.assertIsNone(images.aspect_ratio_float())

    def test_ratio_float_matches_the_css(self):
        _set(image_aspect_ratio='landscape')
        self.assertAlmostEqual(images.aspect_ratio_float(), 1.5, places=3)

    def test_quality_is_clamped_to_a_usable_band(self):
        _set(image_quality=5)
        self.assertEqual(images.quality(), images.MIN_QUALITY)
        _set(image_quality=999)
        self.assertEqual(images.quality(), images.MAX_QUALITY)
        _set(image_quality='not a number')
        self.assertEqual(images.quality(), images.DEFAULT_QUALITY)


class ExplicitChoiceTests(TestCase):
    """An unconfigured store must not be reshaped without being asked."""

    def test_unconfigured_returns_none(self):
        self.assertIsNone(images.configured_display_settings())

    def test_a_choice_is_published(self):
        _set(image_aspect_ratio='portrait')
        self.assertEqual(images.configured_display_settings()['ratio'], '2 / 3')


class FrameStyleTagTests(TestCase):
    def _render(self) -> str:
        return Template('{% load morph %}{% image_frame_style %}').render(Context({}))

    def test_emits_nothing_until_the_merchant_chooses(self):
        # dot_books' portrait frames are correct for a bookshop; publishing the
        # platform default would silently restyle it on deploy.
        self.assertEqual(self._render().strip(), '')

    def test_emits_both_custom_properties_once_chosen(self):
        _set(image_aspect_ratio='tall', image_fit='contain')
        out = self._render()
        self.assertIn('--img-ratio:3 / 4', out)
        self.assertIn('--img-fit:contain', out)


class NoDeadSettingsTests(TestCase):
    """Every key the Images panel offers must have a consumer.

    This panel shipped four that did not: `grid_image_width/height` (superseded
    by the on-demand `/img/<fmt>/<w>/` resizer) and `og_image_width/height`
    (nothing on this platform generates an og:image — `SeoMeta.og_image` is a
    URL the merchant supplies). A merchant could set all four and change
    nothing, including the grid shape they were trying to fix.
    """

    def test_every_image_setting_is_read_somewhere(self):
        from plugins.installed.catalog.app import CatalogPlugin

        root = pathlib.Path(__file__).resolve().parents[2]
        searchable = [
            p
            for d in ('core', 'plugins', 'themes', 'api', 'morph')
            for p in (root / d).rglob('*')
            if p.suffix in {'.py', '.html'} and 'catalog/app.py' not in str(p)
        ]
        haystack = '\n'.join(p.read_text(errors='ignore') for p in searchable)

        orphans = [
            key for key in CatalogPlugin().get_config_schema()['properties'] if key not in haystack
        ]
        self.assertEqual(
            orphans,
            [],
            f'Image settings with no consumer anywhere: {orphans}. '
            'Wire the consumer in the same change, or drop the field.',
        )


class DashboardFrameTests(TestCase):
    """No dashboard frame may hardcode a vertical's aspect ratio."""

    def test_no_hardcoded_book_cover_frames(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        shell = root / 'plugins' / 'installed' / 'admin_dashboard' / 'templates'
        offenders = []
        for template in shell.rglob('*.html'):
            markup = template.read_text(errors='ignore')
            # A literal ratio that is not behind `var(--img-ratio, …)`.
            for match in re.finditer(r'aspect-ratio:\s*([^;<}]+)', markup):
                if 'var(--img-ratio' not in match.group(1):
                    offenders.append(f'{template.name}: {match.group(1).strip()}')
            if re.search(r'class="[^"]*\bh-10 w-7\b', markup):
                offenders.append(f'{template.name}: h-10 w-7 (a 28x40 book cover)')
        self.assertEqual(offenders, [], f'hardcoded image frames in the shell: {offenders}')


class CropTests(TestCase):
    def test_centre_crop_reshapes_only_when_needed(self):
        from PIL import Image as PILImage

        from plugins.installed.catalog.image_pipeline import _crop_to_ratio

        wide = PILImage.new('RGB', (400, 200))
        self.assertEqual(_crop_to_ratio(wide, 1.0).size, (200, 200))

        tall = PILImage.new('RGB', (200, 400))
        self.assertEqual(_crop_to_ratio(tall, 1.0).size, (200, 200))

        square = PILImage.new('RGB', (300, 300))
        self.assertEqual(_crop_to_ratio(square, 1.0).size, (300, 300))

        # `original` (ratio None) must never crop.
        self.assertEqual(_crop_to_ratio(wide, None).size, (400, 200))

    def test_crop_is_off_unless_asked_for(self):
        self.assertFalse(images.crop_to_ratio())
        _set(crop_to_aspect_ratio=True)
        self.assertTrue(images.crop_to_ratio())


class SchemaShapeTests(TestCase):
    def test_panel_offers_the_documented_choices(self):
        from plugins.installed.catalog.app import CatalogPlugin

        props = CatalogPlugin().get_config_schema()['properties']
        self.assertEqual(props['image_aspect_ratio']['enum'], list(images.ASPECT_RATIOS))
        self.assertEqual(props['image_fit']['enum'], list(images.FIT_MODES))
        self.assertEqual(props['image_aspect_ratio']['default'], 'square')
        # The four dead keys are gone and must not come back.
        for dead in ('grid_image_width', 'grid_image_height', 'og_image_width', 'og_image_height'):
            self.assertNotIn(dead, props)

    def test_schema_is_json_serialisable(self):
        from plugins.installed.catalog.app import CatalogPlugin

        json.dumps(CatalogPlugin().get_config_schema())
