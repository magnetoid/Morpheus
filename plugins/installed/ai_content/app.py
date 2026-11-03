import logging

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.ai_content')


class AIContentPlugin(Plugin):
    name = 'ai_content'
    label = 'AI Content & Assets Studio'
    version = '1.1.0'
    description = (
        'Carries the store-wide brand-voice config (tone, audience, '
        'guidelines) that every AI generation in the platform reads '
        'from via `services.get_brand_voice()`. The canonical product-'
        'description auto-generation path lives in the ai_assistant '
        "plugin's PRODUCT_CREATED hook (`generate_product_description` "
        'Celery task).'
    )
    has_models = False
    # metafields holds the marks of AI-written text (marks.py).
    requires = ['catalog', 'ai_assistant', 'metafields']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        # Prepend the brand voice to every agent/Linda system prompt. Core
        # fires AGENT_SYSTEM_PROMPT as the last assembly step; while this
        # plugin is disabled the bus skips the handler and the plain prompt
        # flows through (the ADR 0017 inversion of the old core→plugin import).
        self.register_hook(events.AGENT_SYSTEM_PROMPT, self.on_agent_system_prompt, priority=50)

        # Text an AI wrote is marked (EU AI Act Art. 50): stored when a tool says so,
        # set or cleared by the merchant in the product editor, published in the
        # structured data (after the apps that add the page's Product node) and
        # counted in the AI Act report.
        from plugins.installed.ai_content import marks, seo_graph  # noqa: PLC0415

        self.register_hook(events.AI_CONTENT_WRITTEN, marks.on_ai_content_written, priority=50)
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=80)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=80)
        self.register_hook(events.SEO_JSONLD_GRAPH, seo_graph.on_seo_jsonld_graph, priority=90)
        self.register_hook(events.AI_ACT_REPORT, self.on_ai_act_report, priority=50)

    def on_agent_system_prompt(self, value, **kwargs):
        """AGENT_SYSTEM_PROMPT filter — return the prompt with brand voice first."""
        from plugins.installed.ai_content.services import with_brand_voice  # noqa: PLC0415

        return with_brand_voice(value if isinstance(value, str) else '')

    def on_product_form_cards(self, value, product=None, **kwargs):
        """The editor's "Written with AI" card: one box per text field."""
        from plugins.installed.ai_content.marks import PRODUCT_FIELDS, SOURCES, marks_for

        marked = marks_for(product)
        fields = [
            {
                'name': name,
                'label': label,
                'marked': name in marked,
                'source': SOURCES.get(marked.get(name, ''), ''),
            }
            for name, label in PRODUCT_FIELDS
        ]
        value.append(
            {
                'template': 'ai_content/_product_form_card.html',
                'context': {'ai_text': {'fields': fields}},
                'order': 80,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        from plugins.installed.ai_content.marks import save_from_form

        save_from_form(product, post)

    def on_ai_act_report(self, value, since=None, until=None, **kwargs):
        """The AI Act report's section on text marked as written with AI."""
        from collections import Counter

        from plugins.installed.ai_content.marks import report_rows

        rows = report_rows(since=since, until=until)
        value['ai_text'] = rows
        value['summary']['total_ai_text'] = len(rows)
        value['summary']['ai_text_by_field'] = dict(Counter(r['field'] for r in rows))
        value['summary']['ai_text_by_source'] = dict(Counter(r['source'] for r in rows))
        return value

    def contribute_storefront_blocks(self) -> list:
        # Under the description on the product page, and on a booking page (an
        # experience is a catalog Product extended by the booking app).
        return [
            StorefrontBlock(
                slot='pdp_below_long_description',
                template='ai_content/blocks/ai_text_mark.html',
                priority=20,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='listing_below_description',
                template='ai_content/blocks/ai_text_mark.html',
                priority=20,
                context_keys=['product'],
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.ai_content.agent_tools import (  # noqa: PLC0415
            products_ai_written_tool,
        )

        return [products_ai_written_tool]

    def get_config_schema(self):
        """
        Settings rendered into `/dashboard/settings/ai/` (category=ai).

        The brand-voice fields (`brand_name`, `brand_audience`,
        `brand_tone`, `brand_voice_guidelines`) feed every AI
        generation in the platform via `services.get_brand_voice()`,
        so a single store-wide style edit propagates everywhere
        — product descriptions, email rewrites, SEO drafts.
        """
        return {
            'type': 'object',
            'properties': {
                # ── Brand voice — the merchant's style preserved across all AI
                # generation in the platform.
                'brand_name': {
                    'type': 'string',
                    'default': '',
                    'title': 'Brand name',
                    'description': 'How AI-written copy should refer to your store. Leave blank to fall back to the platform store name.',
                },
                'brand_audience': {
                    'type': 'string',
                    'default': '',
                    'title': 'Target audience',
                    'description': "One short line — e.g. 'Independent bookstore shoppers, mid-30s, design-conscious'.",
                },
                'brand_tone': {
                    'type': 'string',
                    'default': 'professional, warm, concrete',
                    'title': 'Tone keywords',
                    'description': "Comma-separated adjectives the AI should hit. e.g. 'playful, irreverent, technical'.",
                },
                'brand_voice_guidelines': {
                    'type': 'string',
                    'default': '',
                    'title': 'Voice guidelines',
                    'description': 'Free-form rules: words to avoid, signature phrases, sentence length, formality. Prepended to every AI prompt as a system message.',
                },
                # ── AI-written text (EU AI Act Art. 50). The page always carries the
                # machine-readable mark; this adds a sentence a shopper reads.
                'label_ai_text': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Say so on the product page',
                    'description': (
                        'Under a description written with AI, show "This product\'s '
                        'description was written with the help of AI." The page and its '
                        'structured data mark that text for search engines either way.'
                    ),
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Brand voice & AI content',
            description=(
                'Store-wide brand voice that every AI generation in the '
                'platform reads from — product descriptions, email '
                'rewrites, SEO drafts. Edit once, propagate everywhere.'
            ),
            schema=self.get_config_schema(),
            category='ai',
        )
