"""TagProfile + tag-page rendering tests.

Tags have no description of their own (taggit), so TagProfile supplies the
editorial copy the ``?tag=`` landing page renders below its title.
"""

from __future__ import annotations

from django.test import Client, TestCase

from plugins.installed.catalog.models import TagProfile


class TagProfileModelTests(TestCase):
    def test_for_tag_resolves_by_slug_and_by_name(self):
        p = TagProfile.objects.create(
            slug='science-fiction', name='Science Fiction', description='Ray guns and big ideas.'
        )
        self.assertEqual(TagProfile.for_tag('science-fiction'), p)  # slug form
        self.assertEqual(TagProfile.for_tag('Science Fiction'), p)  # name → slugify → same
        self.assertIsNone(TagProfile.for_tag('nonexistent'))
        self.assertIsNone(TagProfile.for_tag(''))


class TagPageRenderTests(TestCase):
    def test_tag_page_shows_title_and_description(self):
        # The tag header renders from TagProfile independent of matching products
        # (we don't tag a product here — taggit's integer object_id overflows on
        # SQLite for UUID-PK products; that association path runs on Postgres/prod).
        TagProfile.objects.create(
            slug='science-fiction', name='Science Fiction', description='Ray guns and big ideas.'
        )
        resp = Client().get('/products/?tag=science-fiction')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ray guns and big ideas.')  # description renders below title
        self.assertContains(resp, 'Science Fiction')  # tag name renders as the title
