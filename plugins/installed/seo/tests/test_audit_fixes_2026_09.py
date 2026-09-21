"""Guards for the Sep 2026 Montenegro SEO/AEO audit findings.

Each test here corresponds to a defect a live 346-url crawl found that the
suite was green through — the recurring shape being markup that is *valid* and
therefore invisible when wrong.
"""

from __future__ import annotations

from django.test import TestCase, override_settings

from core.head import HeadDocument


class XDefaultTests(TestCase):
    """`x-default` names the default language, not whichever page you are on."""

    def _alternates(self, path: str) -> dict[str, str]:
        from plugins.installed.seo.head.builder import _apply_alternates

        request = self.client.get(path).wsgi_request
        doc = HeadDocument()
        doc.link('canonical', request.build_absolute_uri(), source='test')
        _apply_alternates(doc, None, request)
        return {
            entry.attrs['hreflang']: entry.attrs['href']
            for entry in doc.entries()
            if entry.section == 'link' and entry.attrs.get('hreflang')
        }

    @override_settings(LANGUAGES=[('en', 'English'), ('sr', 'Srpski')], LANGUAGE_CODE='en')
    def test_both_language_trees_name_the_same_x_default(self):
        english = self._alternates('/')
        serbian = self._alternates('/sr/')

        self.assertIn('en', english)
        self.assertIn('sr', english)
        # The bug: each tree used its OWN canonical, so `/` claimed `/` and
        # `/sr/` claimed `/sr/` — two conflicting defaults for one cluster.
        self.assertEqual(english['x-default'], serbian['x-default'])
        self.assertEqual(english['x-default'], english['en'])

    @override_settings(LANGUAGES=[('en', 'English')], LANGUAGE_CODE='en')
    def test_single_language_store_emits_no_alternates(self):
        self.assertEqual(self._alternates('/'), {})


class XDefaultSelectionTests(TestCase):
    """`_x_default_href` in isolation — no request plumbing."""

    def _pick(self, languages, canonical='https://x.test/here/', code='en'):
        from plugins.installed.seo.head.builder import _x_default_href

        with override_settings(LANGUAGE_CODE=code):
            return _x_default_href(languages, canonical)

    def test_picks_the_default_language(self):
        pairs = [('sr', 'https://x.test/sr/'), ('en', 'https://x.test/')]
        self.assertEqual(self._pick(pairs), 'https://x.test/')

    def test_regional_language_code_falls_back_to_the_base_tag(self):
        pairs = [('en', 'https://x.test/'), ('sr', 'https://x.test/sr/')]
        self.assertEqual(self._pick(pairs, code='en-us'), 'https://x.test/')

    def test_market_only_store_keeps_the_canonical(self):
        # No language axis at all — the canonical IS the default.
        self.assertEqual(self._pick([]), 'https://x.test/here/')


class LlmsTxtTests(TestCase):
    def _render(self, **kwargs) -> str:
        from plugins.installed.seo.services import render_llms_txt

        return render_llms_txt(**kwargs)

    def test_no_double_slashes_in_urls(self):
        body = self._render(full=False)
        offenders = [ln for ln in body.splitlines() if '//' in ln.replace('://', ':')]
        self.assertEqual(offenders, [], f'double-slash urls in llms.txt: {offenders[:3]}')

    def test_no_empty_products_heading(self):
        # A "## Products" heading with no rows tells a crawler the shop is
        # empty. With no active products the section must not open at all.
        body = self._render(full=False)
        self.assertNotIn('## Products', body)

    def test_site_map_does_not_link_a_redirecting_route(self):
        # `/categories/` 301s to `/genres/` wherever the book vertical is on.
        self.assertNotIn('/categories/)', self._render(full=False))

    def test_owners_contribute_their_own_sections(self):
        from morpheus.core import MorpheusEvents, hook_registry

        def _subscriber(value, **kwargs):
            base = kwargs['base']
            self.assertFalse(base.endswith('/'), 'subscribers get a clean base')
            return [*value, {'title': 'Stays', 'lines': [f'- [Villa]({base}/hotels/villa/)']}]

        hook_registry.register(MorpheusEvents.SEO_LLMS_SECTIONS, _subscriber, priority=50)
        try:
            body = self._render(full=False)
        finally:
            hook_registry.unregister(MorpheusEvents.SEO_LLMS_SECTIONS, _subscriber)

        self.assertIn('## Stays', body)
        self.assertIn('/hotels/villa/', body)

    def test_a_broken_subscriber_does_not_take_the_file_down(self):
        from morpheus.core import MorpheusEvents, hook_registry

        def _boom(value, **kwargs):
            raise RuntimeError('subscriber exploded')

        hook_registry.register(MorpheusEvents.SEO_LLMS_SECTIONS, _boom, priority=50)
        try:
            self.assertIn('# ', self._render(full=False))
        finally:
            hook_registry.unregister(MorpheusEvents.SEO_LLMS_SECTIONS, _boom)


class JournalGraphTests(TestCase):
    """What the journal page actually publishes is the GRAPH, not the tags.

    Every theme's `journal_detail.html` passes `word_count`, `author_same_as`
    and `citations` to `{% seo_article_jsonld %}` — and under the head contract
    that tag is shimmed to `''`, so the values a merchant entered never reached
    a single live page. The same seam is where `FAQPage` belongs: a page
    carries one graph, and a second `<script>` would compete with it.
    """

    def _graph(self, *, body: str, metadata: dict | None = None) -> list[dict]:
        from core.seo_page import KIND_ARTICLE, SeoPage
        from plugins.installed.cms.models import Page
        from plugins.installed.cms.services import journal_dict
        from plugins.installed.seo.schema import build_graph

        page = Page.objects.create(
            slug='graph-probe',
            title='Graph probe',
            state='published',
            body=body,
            metadata={'category': 'journal', **(metadata or {})},
        )
        seo_page = SeoPage(
            kind=KIND_ARTICLE,
            obj=page,
            path='/journal/graph-probe/',
            title=page.title,
            context={'entry': journal_dict(page)},
        )
        return (build_graph(seo_page) or {}).get('@graph', [])

    def _node(self, graph, node_type):
        return next((n for n in graph if node_type in str(n.get('@type', ''))), None)

    def test_author_same_as_and_citations_reach_the_graph(self):
        graph = self._graph(
            body='<p>' + 'word ' * 50 + '</p>',
            metadata={
                'author': 'Marko Milosavljevic',
                'author_same_as': ['https://www.wikidata.org/wiki/Q1'],
                'citations': ['https://example.test/source'],
            },
        )
        article = self._node(graph, 'BlogPosting')
        self.assertIsNotNone(article)
        self.assertEqual(article['author']['sameAs'], ['https://www.wikidata.org/wiki/Q1'])
        self.assertEqual(article['wordCount'], 50)

    def test_question_headings_publish_an_faqpage_node(self):
        answer = 'A full sentence that is long enough to count as an answer. '
        graph = self._graph(
            body=(
                f'<h2>Why visit in May?</h2><p>{answer}</p>'
                f'<h2>Best beaches</h2><p>{answer}</p>'
                f'<h2>Is it expensive?</h2><p>{answer}</p>'
            )
        )
        faq = self._node(graph, 'FAQPage')
        self.assertIsNotNone(faq, 'two question headings should publish an FAQPage')
        self.assertEqual(
            [q['name'] for q in faq['mainEntity']],
            ['Why visit in May?', 'Is it expensive?'],
        )
        # Exactly one graph, so the FAQ must be a node in it, not a sibling.
        self.assertEqual(len([n for n in graph if 'FAQPage' in str(n.get('@type', ''))]), 1)

    def test_an_article_without_questions_publishes_no_faqpage(self):
        graph = self._graph(body='<h2>Beaches</h2><p>' + 'word ' * 40 + '</p>')
        self.assertIsNone(self._node(graph, 'FAQPage'))
