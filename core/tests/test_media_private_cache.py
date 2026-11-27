"""A sold file never sits in a shared cache (core/media.py).

A CDN in front of /media/ caches PDF, MP3 and ZIP by their extension, so the
copy a staff member opened would be served to anyone asking for the same path.
Every answer under a private prefix says no shared cache may keep it: the
staff download, and the 404 everyone else gets.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from core.media import serve_media


class PrivateMediaCacheTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        (Path(self.root) / 'digital').mkdir()
        (Path(self.root) / 'digital' / 'book.pdf').write_bytes(b'%PDF-1.4 paid')
        (Path(self.root) / 'cover.jpg').write_bytes(b'jpeg')

    def _get(self, path, *, staff):
        request = RequestFactory().get(f'/media/{path}')
        request.user = SimpleNamespace(is_staff=staff)
        return serve_media(request, path, document_root=self.root)

    def test_the_staff_download_is_never_stored(self):
        response = self._get('digital/book.pdf', staff=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_the_refusal_is_never_stored(self):
        response = self._get('digital/book.pdf', staff=False)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_a_missing_private_file_is_never_stored(self):
        response = self._get('digital/gone.pdf', staff=True)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_public_media_keeps_its_headers(self):
        response = self._get('cover.jpg', staff=False)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header('Cache-Control'))
