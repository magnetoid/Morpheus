"""Product story blocks — model, template tag, dashboard editor, agent tools."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.product_stories.agent_tools import (
    stories_add_block_tool,
    stories_list_blocks_tool,
)
from plugins.installed.product_stories.models import ProductStoryBlock
from plugins.installed.product_stories.templatetags.product_stories import product_story_blocks


def _product(slug='a-book'):
    return Product.objects.create(
        name='A Book',
        slug=slug,
        sku='BK-1',
        status='active',
        price=Money(Decimal('20.00'), 'USD'),
        short_description='s',
        description='d',
        product_type='simple',
    )


def _staff():
    c = Client()
    c.force_login(
        get_user_model().objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )
    )
    return c


class StoryTagTests(TestCase):
    def test_returns_active_ordered_blocks(self):
        p = _product()
        ProductStoryBlock.objects.create(product=p, order=1, heading='Second')
        ProductStoryBlock.objects.create(product=p, order=0, heading='First')
        ProductStoryBlock.objects.create(product=p, order=2, heading='Hidden', is_active=False)
        out = product_story_blocks('a-book')
        self.assertEqual([b.heading for b in out], ['First', 'Second'])

    def test_unknown_slug_returns_empty(self):
        self.assertEqual(product_story_blocks('nope'), [])


class DashboardEditorTests(TestCase):
    def test_index_requires_staff(self):
        self.assertEqual(Client().get('/dashboard/stories/').status_code, 302)

    def test_add_edit_delete_block(self):
        p = _product()
        c = _staff()
        c.post(
            f'/dashboard/stories/{p.slug}/',
            {
                'action': 'create',
                'heading': 'Why readers love it',
                'layout': 'image_left',
            },
        )
        block = ProductStoryBlock.objects.get(product=p)
        self.assertEqual(block.heading, 'Why readers love it')
        self.assertEqual(block.layout, 'image_left')

        c.post(
            f'/dashboard/stories/{p.slug}/',
            {
                'action': 'update',
                'block_id': str(block.id),
                'heading': 'Updated',
                'layout': 'text',
                'order': '2',
                'is_active': 'on',
            },
        )
        block.refresh_from_db()
        self.assertEqual(block.heading, 'Updated')
        self.assertEqual(block.order, 2)

        c.post(f'/dashboard/stories/{p.slug}/', {'action': 'delete', 'block_id': str(block.id)})
        self.assertFalse(ProductStoryBlock.objects.filter(id=block.id).exists())

    def test_index_lists_products_with_stories(self):
        p = _product()
        ProductStoryBlock.objects.create(product=p, order=0, heading='X')
        r = _staff().get('/dashboard/stories/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'A Book')


class AgentToolTests(TestCase):
    def test_add_then_list(self):
        _product()
        out = stories_add_block_tool.invoke(
            {'slug': 'a-book', 'heading': 'Cosy', 'layout': 'image_full'}
        ).output
        self.assertIn('id', out)
        listed = stories_list_blocks_tool.invoke({'slug': 'a-book'}).output
        self.assertEqual(listed['count'], 1)
        self.assertEqual(listed['blocks'][0]['heading'], 'Cosy')

    def test_add_unknown_product_errors(self):
        out = stories_add_block_tool.invoke({'slug': 'ghost', 'heading': 'X'}).output
        self.assertIn('error', out)
