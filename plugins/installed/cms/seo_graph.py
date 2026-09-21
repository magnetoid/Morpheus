"""FAQPage for a journal article, built only from headings that are questions.

The Sep 2026 audit called this "the single cheapest AEO gain on the site": 33
long-form articles carry `SpeakableSpecification` and none carries `FAQPage`,
though each has 10–18 H2 sections. Its suggested fix — convert every H2 section
into a Q&A pair — is the `test_offer_claims` mistake in another costume. "Best
beaches for families" is not a question, and publishing it as one asserts the
page answers something it never asked; Google also requires the Q&A to appear
on the page in that form.

So only an H2 that actually ends in '?' becomes a Question, and a page needs two
before it is an FAQ at all. On this corpus that covers a minority of articles by
design. The alternative covers all of them and lies about most.

Goes into the one JSON-LD graph (ADR 0036) rather than a second `<script>` — a
page carries one graph, and under the head contract a template-emitted block is
shimmed to '' anyway.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.cms')


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """`SEO_JSONLD_GRAPH` subscriber: add FAQPage to a journal article."""
    try:
        entry = (getattr(page, 'context', None) or {}).get('entry')
        pairs = (entry or {}).get('faq_pairs') if isinstance(entry, dict) else None
        if not pairs:
            return value
        nodes = value.get('@graph') if isinstance(value, dict) else None
        if nodes is None:
            return value
        url = next(
            (n.get('@id', '').split('#')[0] for n in nodes if n.get('@type') == 'WebPage'), ''
        )
        nodes.append(
            {
                '@type': 'FAQPage',
                '@id': f'{url}#faq' if url else None,
                'mainEntity': [
                    {
                        '@type': 'Question',
                        'name': pair['q'],
                        'acceptedAnswer': {'@type': 'Answer', 'text': pair['a']},
                    }
                    for pair in pairs
                ],
            }
        )
    except Exception as e:  # noqa: BLE001 — an enricher must never lose the graph
        logger.warning('cms: FAQPage enrichment failed: %s', e, exc_info=True)
    return value
