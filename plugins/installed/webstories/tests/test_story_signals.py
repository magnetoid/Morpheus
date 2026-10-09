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
        seen = []
        with (
            mock.patch.object(signals, '_live_product', return_value=_product()),
            mock.patch(
                'plugins.installed.webstories.services.ensure_story',
                side_effect=lambda product: seen.append(len(connection.savepoint_ids)),
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            signals._regenerate_on_image_delete(sender=None, instance=SimpleNamespace(product_id=1))
            self.assertEqual(seen, [])  # nothing is built before the commit
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0], outer)

    def test_an_image_deleted_from_a_product_not_on_sale_builds_nothing(self):
        image = SimpleNamespace(product_id=1)
        with (
            mock.patch.object(signals, '_live_product', return_value=None),
            mock.patch('plugins.installed.webstories.services.ensure_story') as build,
            self.captureOnCommitCallbacks(execute=True),
        ):
            signals._regenerate_on_image_delete(sender=None, instance=image)
        build.assert_not_called()

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


_PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000d49444154789c63f8cfc0f01f0005000201a5f1a4d8'
    '0000000049454e44ae426082'
)


class ProductDeleteTests(TestCase):
    """Deleting a product deletes its images first. The image-delete receiver
    used to rebuild the story right there, for the product being deleted; the
    new story row then pointed at a product gone by commit, and Postgres
    rejected the whole delete on its deferred foreign key. Found on
    beta.irvingsurvival.com (2026-10-09) deleting a draft product with one photo."""

    def setUp(self):
        import tempfile

        from django.test import override_settings

        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        media = override_settings(MEDIA_ROOT=self._media.name)
        media.enable()
        self.addCleanup(media.disable)

    def _product_with_image(self, status):
        from django.apps import apps
        from django.core.files.uploadedfile import SimpleUploadedFile
        from djmoney.money import Money

        product_model = apps.get_model('catalog', 'Product')
        image_model = apps.get_model('catalog', 'ProductImage')
        product = product_model.objects.create(
            name='Lamp',
            slug=f'lamp-{status}',
            sku=f'LAMP-{status}',
            price=Money(5, 'USD'),
            status=status,
        )
        image_model.objects.create(
            product=product, image=SimpleUploadedFile('lamp.png', _PNG, content_type='image/png')
        )
        return product

    def test_a_product_with_images_can_be_deleted(self):
        from plugins.installed.webstories.models import WebStory

        for status in ('active', 'draft'):
            with self.subTest(status=status):
                product = self._product_with_image(status)
                pk = product.pk
                with self.captureOnCommitCallbacks(execute=True):
                    product.delete()
                self.assertFalse(WebStory.objects.filter(product_id=pk).exists())
                # What Postgres checks at commit: no row may point at the
                # deleted product.
                connection.check_constraints()

    def test_deleting_one_image_of_a_live_product_rebuilds_its_story(self):
        product = self._product_with_image('active')
        image = product.images.first()
        with (
            mock.patch('plugins.installed.webstories.services.ensure_story') as build,
            self.captureOnCommitCallbacks(execute=True),
        ):
            image.delete()
        build.assert_called_once()
        self.assertEqual(build.call_args.args[0].pk, product.pk)
