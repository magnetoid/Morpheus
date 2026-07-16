"""Merchant-editable intro copy for the built-in listing pages.

/products/, /vendors/ and /journal/ own no model of their own, so their intro
prose was hardcoded in the theme and their meta description hardcoded in the
view — a merchant could not change either. They now read the
STOREFRONT_PAGE_INTRO filter, which cms answers from a Block keyed
``<page>_intro``. Going through the bus (rather than importing cms) is what
keeps a disabled cms from 500ing the storefront, so that's pinned too.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.cms.models import Block


class PageIntroFilterTests(TestCase):
    def test_returns_empty_when_no_block_exists(self):
        from plugins.installed.storefront.services import page_intro

        self.assertEqual(page_intro(None, 'products'), {'body': '', 'meta_description': ''})

    def test_reads_the_cms_block_for_the_page(self):
        from plugins.installed.storefront.services import page_intro

        Block.objects.create(
            key='products_intro',
            label='All books — page intro',
            body='Everything we shelve, in one place.',
            metadata={'meta_description': 'The whole shelf.'},
        )
        intro = page_intro(None, 'products')
        self.assertEqual(intro['body'], 'Everything we shelve, in one place.')
        self.assertEqual(intro['meta_description'], 'The whole shelf.')

    def test_inactive_block_is_ignored(self):
        from plugins.installed.storefront.services import page_intro

        Block.objects.create(key='journal_intro', label='j', body='Hidden.', is_active=False)
        self.assertEqual(page_intro(None, 'journal')['body'], '')

    def test_each_page_reads_its_own_block(self):
        from plugins.installed.storefront.services import page_intro

        Block.objects.create(key='vendors_intro', label='v', body='Our presses.')
        self.assertEqual(page_intro(None, 'vendors')['body'], 'Our presses.')
        self.assertEqual(page_intro(None, 'products')['body'], '')


class PageIntroRenderTests(TestCase):
    def test_products_page_renders_the_block_over_house_copy(self):
        Block.objects.create(key='products_intro', label='p', body='Shelf copy from the merchant.')
        resp = self.client.get('/products/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Shelf copy from the merchant.', html)
        self.assertNotIn('The shelf rotates every Tuesday.', html)

    def test_products_page_falls_back_to_house_copy(self):
        resp = self.client.get('/products/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The shelf rotates every Tuesday.', resp.content.decode())

    def test_filtered_plp_keeps_its_own_intro(self):
        """A filtered view is introduced by its own term copy — the page-level
        intro is for the unfiltered shelf only."""
        Block.objects.create(key='products_intro', label='p', body='Unfiltered shelf copy.')
        resp = self.client.get('/products/?q=poetry')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Unfiltered shelf copy.', resp.content.decode())

    def test_journal_index_renders_the_block(self):
        Block.objects.create(key='journal_intro', label='j', body='Dispatches from the desk.')
        resp = self.client.get('/journal/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Dispatches from the desk.', resp.content.decode())

    def test_vendors_directory_renders_the_block(self):
        Block.objects.create(key='vendors_intro', label='v', body='The presses we love.')
        resp = self.client.get('/vendors/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The presses we love.', resp.content.decode())
