"""The guide reader (plugins/app_help.py): format, location, cache."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from plugins import app_help

GUIDE = """---
summary: Shoppers rate products; you approve or hide what they write.
---

## What it's for

Reviews show on [the product page](section:products).

## Common tasks

- Approve a review on [](page:reviews).
"""


class ParseTests(SimpleTestCase):
    def test_front_matter_body_and_headings(self):
        g = app_help.parse('reviews', GUIDE)
        self.assertEqual(g.summary, 'Shoppers rate products; you approve or hide what they write.')
        self.assertEqual(g.keys, ('summary',))
        self.assertEqual(g.headings, ("What it's for", 'Common tasks'))
        self.assertTrue(g.body.startswith("## What it's for"))

    def test_windows_line_endings_and_a_bom_read_the_same(self):
        plain = app_help.parse('reviews', GUIDE)
        self.assertEqual(app_help.parse('reviews', GUIDE.replace('\n', '\r\n')), plain)
        self.assertEqual(app_help.parse('reviews', '\ufeff' + GUIDE), plain)

    def test_no_front_matter_means_no_summary(self):
        g = app_help.parse('reviews', "## What it's for\n\nText.\n")
        self.assertEqual((g.summary, g.keys), ('', ()))

    def test_markers_are_listed_with_their_text(self):
        self.assertEqual(
            app_help.markers(app_help.parse('reviews', GUIDE).body),
            [('the product page', 'section', 'products'), ('', 'page', 'reviews')],
        )


class LocationTests(TestCase):
    def test_every_app_folder_is_listed(self):
        apps = app_help.tree_apps()
        self.assertIn('reviews', apps)
        self.assertIn('demo_data', apps)  # opt-in: in the tree, not installed in CI
        tree = Path(settings.BASE_DIR) / 'plugins' / 'installed'
        self.assertEqual(len(apps), len(list(tree.glob('*/app.py'))))

    def test_an_installed_app_lives_in_its_manifests_folder(self):
        self.assertEqual(
            app_help.app_dir('reviews'),
            Path(settings.BASE_DIR) / 'plugins' / 'installed' / 'reviews',
        )

    def test_an_app_the_store_does_not_install_is_found_in_the_tree(self):
        self.assertEqual(
            app_help.app_dir('demo_data'),
            Path(settings.BASE_DIR) / 'plugins' / 'installed' / 'demo_data',
        )

    def test_no_such_app_has_no_folder(self):
        for name in ('no_such_app', '../etc', '', 'REVIEWS'):
            with self.subTest(name=name):
                self.assertIsNone(app_help.app_dir(name))

    def test_a_manifest_is_loaded_for_an_app_not_installed(self):
        from plugins.registry import app_registry

        self.assertEqual(app_help.load_manifest('demo_data').name, 'demo_data')
        self.assertIs(app_help.load_manifest('reviews'), app_registry.get('reviews'))
        self.assertIsNone(app_help.load_manifest('no_such_app'))


class GuideTests(SimpleTestCase):
    def setUp(self):
        app_help.forget()
        self.addCleanup(app_help.forget)

    def test_a_guide_is_read_from_the_apps_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'help.md').write_text(GUIDE, encoding='utf-8')
            with mock.patch.object(app_help, 'app_dir', return_value=Path(tmp)):
                self.assertEqual(
                    app_help.summary('reviews'),
                    'Shoppers rate products; you approve or hide what they write.',
                )

    def test_an_app_without_a_guide_reads_as_none(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(app_help, 'app_dir', return_value=Path(tmp)),
        ):
            self.assertIsNone(app_help.guide('reviews'))
            self.assertEqual(app_help.summary('reviews'), '')
