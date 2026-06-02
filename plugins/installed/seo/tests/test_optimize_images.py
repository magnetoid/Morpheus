"""optimize_images batch warmer — generates idempotent WebP variants
into the same cache layout the /img/ view serves from.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from plugins.installed.media.models import MediaAsset
from plugins.installed.seo.services.images import variant_cache_abs


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (1000, 600), (120, 80, 40)).save(buf, 'PNG')
    return buf.getvalue()


class OptimizeImagesCommandTests(TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._tmp)
        self._override.enable()
        upload = SimpleUploadedFile('pic.png', _png_bytes(), content_type='image/png')
        self.asset = MediaAsset.from_upload(uploaded_file=upload)

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_generates_webp_variant_idempotently(self):
        # 1200 is NOT in the upload auto-warm set (400/800), so it starts absent.
        rel = self.asset.file.name
        cache_abs = variant_cache_abs(rel, 1200, 'webp')
        self.assertFalse(os.path.isfile(cache_abs))

        call_command('optimize_images', '--widths', '1200')
        self.assertTrue(os.path.isfile(cache_abs))

        # Idempotent — a second pass regenerates nothing.
        mtime = os.path.getmtime(cache_abs)
        call_command('optimize_images', '--widths', '1200')
        self.assertEqual(os.path.getmtime(cache_abs), mtime)

    def test_dry_run_writes_nothing(self):
        # 1600 is not auto-warmed on upload, so dry-run must leave it absent.
        rel = self.asset.file.name
        cache_abs = variant_cache_abs(rel, 1600, 'webp')
        call_command('optimize_images', '--widths', '1600', '--dry-run')
        self.assertFalse(os.path.isfile(cache_abs))

    def test_upload_warms_default_webp_variants(self):
        # from_upload pre-generates webp at the default widths (400, 800) so
        # the first storefront render is instant.
        rel = self.asset.file.name
        self.assertTrue(os.path.isfile(variant_cache_abs(rel, 400, 'webp')))
        self.assertTrue(os.path.isfile(variant_cache_abs(rel, 800, 'webp')))
