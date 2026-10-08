"""A web story is a side effect of a product save — never a reason for one to fail.

Saving a product with images rebuilds its story, and the story builder asked the
book app for an author line. On a store that runs without the book app
(supernatural, montenegro, Irving Survival) the `plugins_bookproduct` table does
not exist. The query failed and the error was caught — but on Postgres a query
that fails inside a transaction aborts the whole transaction, so the next query
of the caller raised `InFailedSqlTransaction`. Any code that saved a product with
images inside `transaction.atomic()` (a bulk edit, an import, a script) failed on
those stores, while every sqlite test passed: sqlite does not abort a
transaction on a failed statement.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import TestCase

from plugins.installed.webstories import services, signals


def _product(status='active', has_images=True):
    return SimpleNamespace(
        pk=1,
        status=status,
        images=SimpleNamespace(exists=lambda: has_images),
    )


class BookDetailsGateTests(TestCase):
    def test_the_book_app_is_not_read_while_it_is_off(self):
        # A raising stub would be swallowed by the builder's own fail-soft
        # except; assert on the call instead.
        with (
            mock.patch(
                'plugins.registry.app_registry.is_active',
                side_effect=lambda name: name != 'book_product',
            ),
            mock.patch(
                'plugins.installed.book_product.compat.book_attrs',
                return_value={'author': 'A. Writer'},
            ) as book_attrs,
        ):
            self.assertEqual(services._book_metafields(_product()), {})
        book_attrs.assert_not_called()

    def test_the_book_app_is_read_while_it_is_on(self):
        with (
            mock.patch('plugins.registry.app_registry.is_active', return_value=True),
            mock.patch(
                'plugins.installed.book_product.compat.book_attrs',
                return_value={'author': 'A. Writer'},
            ),
        ):
            self.assertEqual(services._book_metafields(_product()), {'author': 'A. Writer'})


class StoryBuildSavepointTests(TestCase):
    """Catching the exception is not enough on Postgres; only a savepoint keeps
    the caller's transaction usable after a failed story query."""

    def _depth_inside_build(self, receiver, **kwargs):
        seen = []
        with mock.patch(
            'plugins.installed.webstories.services.ensure_story',
            side_effect=lambda product: seen.append(len(connection.savepoint_ids)),
        ):
            receiver(**kwargs)
        return seen

    def test_a_product_save_builds_the_story_in_its_own_savepoint(self):
        outer = len(connection.savepoint_ids)
        seen = self._depth_inside_build(
            signals._regenerate_on_product_save, sender=None, instance=_product(), created=False
        )
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0], outer)

    def test_an_image_save_builds_the_story_in_its_own_savepoint(self):
        outer = len(connection.savepoint_ids)
        image = SimpleNamespace(product=_product())
        seen = self._depth_inside_build(
            signals._regenerate_on_image_save, sender=None, instance=image, created=True
        )
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0], outer)

    def test_an_image_delete_builds_the_story_in_its_own_savepoint(self):
        outer = len(connection.savepoint_ids)
        image = SimpleNamespace(product=_product())
        seen = self._depth_inside_build(
            signals._regenerate_on_image_delete, sender=None, instance=image
        )
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0], outer)

    def test_a_failed_story_never_fails_the_save(self):
        with mock.patch(
            'plugins.installed.webstories.services.ensure_story',
            side_effect=RuntimeError('story builder broke'),
        ):
            signals._regenerate_on_product_save(sender=None, instance=_product(), created=False)
        # still usable afterwards
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            self.assertEqual(cur.fetchone()[0], 1)
