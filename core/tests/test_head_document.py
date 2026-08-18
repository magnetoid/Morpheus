"""The head document's contract: keyed entries, replacement, safe JSON-LD.

These are the invariants the whole SEO pipeline leans on. The one that matters
most is *replacement*: the shell seeds a fallback title and the SEO app supplies
the real one, and the page must end up with exactly one `<title>` — the failure
this design replaces had the theme and a page template each emitting their own
`og:type`, so the PDP shipped two.
"""

from __future__ import annotations

import json

from django.test import SimpleTestCase, TestCase

from core.head import HeadDocument, build_head
from core.hooks import MorpheusEvents, hook_registry
from plugins.registry import app_registry


class HeadDocumentTests(SimpleTestCase):
    def test_setting_the_same_key_replaces_rather_than_appends(self):
        doc = HeadDocument(path='/')
        doc.set_title('Shell fallback', source='shell')
        doc.set_title('Real title', source='seo')
        doc.meta('first', name='description')
        doc.meta('second', name='description')

        html = doc.render()
        self.assertEqual(html.count('<title>'), 1)
        self.assertIn('<title>Real title</title>', html)
        self.assertEqual(html.count('name="description"'), 1)
        self.assertIn('content="second"', html)

    def test_empty_content_removes_an_entry(self):
        """A resolver that decides "no description" must be able to clear the
        shell's fallback, not emit an empty meta."""
        doc = HeadDocument()
        doc.meta('seeded', name='description')
        doc.link('canonical', 'https://example.test/')
        doc.meta('', name='description')
        doc.link('canonical', '')

        html = doc.render()
        self.assertNotIn('description', html)
        self.assertNotIn('canonical', html)

    def test_alternates_do_not_share_a_key(self):
        doc = HeadDocument()
        doc.link('alternate', 'https://example.test/en/', hreflang='en')
        doc.link('alternate', 'https://example.test/fr/', hreflang='fr')
        doc.link('alternate', 'https://example.test/', hreflang='x-default')

        html = doc.render()
        self.assertEqual(html.count('rel="alternate"'), 3)

    def test_jsonld_escapes_script_terminators(self):
        """`</script>` inside a JSON string would end the block early — the one
        escape a JSON-LD serialiser can never skip (stored-XSS regression)."""
        doc = HeadDocument()
        doc.jsonld({'@type': 'Product', 'name': '</script><img src=x onerror=alert(1)>'})

        html = doc.render()
        self.assertNotIn('</script><img', html)
        self.assertIn('\\u003C', html)
        payload = html.split('>', 1)[1].rsplit('</script>', 1)[0]
        self.assertEqual(json.loads(payload)['name'], '</script><img src=x onerror=alert(1)>')

    def test_title_and_attributes_are_html_escaped(self):
        doc = HeadDocument()
        doc.set_title('Bread & "Butter" <b>')
        doc.meta('a "quoted" & <tagged> blurb', name='description')

        html = doc.render()
        self.assertIn('<title>Bread &amp; &quot;Butter&quot; &lt;b&gt;</title>', html)
        self.assertNotIn('<b>', html)
        self.assertIn('&quot;quoted&quot;', html)

    def test_render_order_is_stable(self):
        doc = HeadDocument()
        doc.jsonld({'@type': 'WebSite'})
        doc.link('canonical', 'https://example.test/')
        doc.meta('x', name='robots')
        doc.set_title('T')

        sections = [line.split()[0].lstrip('<') for line in doc.render().splitlines()]
        self.assertEqual(sections[0], 'title>T</title>')
        self.assertEqual(sections[1], 'meta')
        self.assertEqual(sections[2], 'link')
        self.assertTrue(sections[3].startswith('script'))

    def test_as_dict_is_the_headless_representation(self):
        doc = HeadDocument(path='/products/x/', language='en')
        doc.set_title('X')
        doc.meta('desc', name='description')
        doc.link('canonical', 'https://example.test/products/x/')
        doc.jsonld({'@context': 'https://schema.org', '@graph': [{'@type': 'Product'}]})
        doc.note('noindex: none')

        data = doc.as_dict()
        self.assertEqual(data['title'], 'X')
        self.assertEqual(data['path'], '/products/x/')
        self.assertEqual(data['meta'], [{'name': 'description', 'content': 'desc'}])
        self.assertEqual(data['links'][0]['rel'], 'canonical')
        self.assertEqual(data['jsonld'][0]['@graph'][0]['@type'], 'Product')
        self.assertEqual(data['notes'], ['noindex: none'])


class BuildHeadTests(TestCase):
    def test_seeds_the_shell_fallbacks_and_fires_the_filter(self):
        seen = {}

        def handler(value, **kwargs):
            seen['title'] = value.title
            seen['description'] = value.meta_content('description')
            value.set_title('Overridden by a subscriber', source='test')
            value.link('canonical', 'https://example.test/here/')
            return value

        # The seo app subscribes to this event in a running store; deactivate it
        # so this test measures the CORE mechanism (seed → filter → document)
        # rather than the SEO app's output. The bus skips inactive owners.
        app_registry.deactivate('seo')
        hook_registry.register(MorpheusEvents.STOREFRONT_HEAD, handler, priority=1, plugin='')
        try:
            doc = build_head(path='/here/', title='Shell title', description='Shell description')
        finally:
            hook_registry.unregister(MorpheusEvents.STOREFRONT_HEAD, handler)
            app_registry.activate('seo')

        self.assertEqual(seen['title'], 'Shell title')
        self.assertEqual(seen['description'], 'Shell description')
        self.assertEqual(doc.title, 'Overridden by a subscriber')
        self.assertEqual(doc.link_href('canonical'), 'https://example.test/here/')

    def test_without_subscribers_the_shell_fallback_still_renders(self):
        """The disable case: no SEO app, still a valid head with a title."""
        doc = build_head(path='/', title='Just the shop name')
        html = doc.render()
        self.assertEqual(html.count('<title>'), 1)
        self.assertIn('Just the shop name', html)
