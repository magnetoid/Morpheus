"""The universal media uploader: one look, one script, every image field.

The product page's uploader (drag anywhere, a tile per image with a preview,
an "Add" tile, a quick X to remove) is the dashboard's media uploader. A
category's image was a bare file input. Now any form's image field renders the
same component in its form-bound mode (``_media_field.html``, ``data-mode=
"field"``): the chosen file rides along with the form's own Save, so it works
on a create form too and never reloads the page over unsaved edits, and X
removes the image through Django's own clear checkbox.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from plugins.installed.catalog.models import Category

_MEDIA = tempfile.mkdtemp(prefix='media-field-tests-')


def _png(name='tile.png') -> SimpleUploadedFile:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (200, 120, 90)).save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=_MEDIA)
class CategoryImageUploaderTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, _MEDIA, ignore_errors=True)

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@example.com', password='x', is_staff=True
        )
        self.client.force_login(self.staff)
        self.category = Category.objects.create(name='Water', slug='water')
        self.url = reverse(
            'admin_dashboard:category_edit', kwargs={'category_id': self.category.id}
        )

    def _post(self, **extra):
        data = {
            'name': 'Water',
            'slug': 'water',
            'parent': '',
            'description': '',
            'is_active': 'on',
            'sort_order': '0',
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def test_the_form_renders_the_universal_uploader(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn('data-media-uploader', body)
        self.assertIn('data-mode="field"', body)
        self.assertIn('class="muploader-grid"', body)
        self.assertIn('data-add-tile', body)
        self.assertRegex(body, r'<input type="file" name="image"[^>]*data-file-input')
        self.assertIn('name="image-clear"', body)

    def test_the_current_image_shows_as_a_tile(self):
        self.category.image = _png('current.png')
        self.category.save()
        body = self.client.get(self.url).content.decode()
        tile = body.split('data-field-tile', 1)[1].split('</div>', 2)
        self.assertIn(self.category.image.url, ''.join(tile))
        self.assertIn('Replace image', body)

    def test_an_image_chosen_in_the_uploader_is_saved_with_the_form(self):
        response = self._post(image=_png('new.png'))
        self.assertEqual(response.status_code, 302, getattr(response, 'content', b'')[:400])
        self.category.refresh_from_db()
        self.assertTrue(self.category.image.name.startswith('categories/new'))

    def test_the_remove_button_clears_the_image(self):
        self.category.image = _png('old.png')
        self.category.save()
        response = self._post(**{'image-clear': 'on'})
        self.assertEqual(response.status_code, 302)
        self.category.refresh_from_db()
        self.assertFalse(self.category.image)


class SharedComponentTests(TestCase):
    """One stylesheet and one script serve both modes, so they cannot drift."""

    def _static(self, name: str) -> str:
        path = (
            Path(settings.BASE_DIR)
            / 'plugins/installed/admin_dashboard/static/admin_dashboard'
            / name
        )
        return path.read_text(encoding='utf-8')

    def test_the_styles_live_in_one_stylesheet_the_dashboard_loads(self):
        templates = (
            Path(settings.BASE_DIR) / 'plugins/installed/admin_dashboard/templates/admin_dashboard'
        )
        css = self._static('media-uploader.css')
        self.assertIn('.muploader-tile', css)
        self.assertIn('media-uploader.css', (templates / 'base.html').read_text(encoding='utf-8'))
        for partial in ('_media_uploader.html', '_media_field.html'):
            with self.subTest(partial=partial):
                self.assertNotIn('<style>', (templates / partial).read_text(encoding='utf-8'))

    def test_the_script_knows_the_field_mode(self):
        js = self._static('media-uploader.js')
        self.assertIn("dataset.mode === 'field'", js)
        self.assertIn('DataTransfer', js)

    def test_the_script_binds_after_a_boosted_swap(self):
        # The dashboard body is hx-boost: a page reached by a link or
        # re-rendered after a Save never fires DOMContentLoaded.
        self.assertIn("addEventListener('htmx:afterSwap'", self._static('media-uploader.js'))


class GalleryCounterTests(TestCase):
    def test_the_gallery_counts_what_it_holds(self):
        from django.template.loader import render_to_string

        class _Img:
            def __init__(self, i):
                self.id = f'00000000-0000-0000-0000-00000000000{i}'
                self.alt_text = ''
                self.image = None

        class _Product:
            id = '11111111-1111-1111-1111-111111111111'

        html = render_to_string(
            'admin_dashboard/_media_uploader.html',
            {'product': _Product(), 'images': [_Img(1), _Img(2), _Img(3)], 'videos': []},
        )
        self.assertRegex(html, r'<span data-media-count>3</span>/15')
