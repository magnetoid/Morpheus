"""Static files get hashed names, and a file the manifest lacks never fails a page.

STATICFILES_STORAGE was ignored since Django 5.1, so files were served under fixed
names with a 4-hour cache and a CDN kept the old CSS for hours after a deploy.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.staticfiles import HashedStaticFilesStorage


class HashedStorageTests(SimpleTestCase):
    def _storage(self):
        root = Path(tempfile.mkdtemp())
        (root / 'staticfiles.json').write_text(
            json.dumps({'version': '1.1', 'paths': {'theme/site.css': 'theme/site.abc123.css'}})
        )
        return HashedStaticFilesStorage(location=str(root), base_url='/static/')

    def test_a_collected_file_gets_its_hashed_name(self):
        self.assertEqual(self._storage().url('theme/site.css'), '/static/theme/site.abc123.css')

    def test_a_missing_file_falls_back_to_its_plain_name(self):
        with self.assertLogs('morpheus.static', level='WARNING'):
            self.assertEqual(self._storage().url('theme/gone.css'), '/static/theme/gone.css')

    def test_production_uses_it_and_settings_say_so_in_the_current_form(self):
        self.assertFalse(hasattr(settings, 'STATICFILES_STORAGE'))
        self.assertIn('staticfiles', settings.STORAGES)
