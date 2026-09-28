"""
Morpheus CMS — AI Signals plugin (formerly AI Assistant).

Scope today: AI **signals** — embeddings, semantic search,
recommendations, dynamic pricing. The agent layer (chat, tools, runs,
background scheduling, approvals) lives in `core.agents` +
`agent_core` plugin. New agent work belongs there, not here.

This plugin still owns the storefront-side hooks that produce signals
the agent layer consumes (embedding refresh on product create/update,
view recording, search logging).
"""

# Lazy (in-function) task/service imports keep hooks load-order-safe; fail-soft
# hooks intentionally swallow errors. Pre-existing idioms.
# ruff: noqa: PLC0415, S110, I001

from morpheus.core import events
from morpheus.app import Plugin, SettingsPanel


class AIAssistantPlugin(Plugin):
    # Historical name kept stable (referenced everywhere as the
    # provider-config store + plugin key); label clearly says what
    # this plugin does NOT include: Linda lives in core.assistant.
    name = 'ai_assistant'
    label = 'AI signals (embeddings, search, pricing)'
    version = '2.0.0'
    description = (
        'AI signals layer: product embeddings, semantic search, '
        'recommendations, dynamic pricing, AI-providers configuration. '
        "Linda (the merchant assistant) lives in core.assistant — she's "
        "always available regardless of this plugin's state. This panel "
        'is where you wire OpenAI / Anthropic / Packy / Grok / etc. keys.'
    )
    has_models = True
    requires = ['catalog', 'orders', 'customers']

    def ready(self):
        # Enrich the kernel's provider-config registry with dashboard-saved
        # settings. Core (core/agents/llm.py, core/assistant/janus_engine.py)
        # resolves providers through this registry and falls back to an
        # env-only default when this plugin is absent — so the dependency
        # points plugin→core, never the reverse.
        from core.agents.provider_registry import provider_config_registry
        from plugins.installed.ai_assistant.services.config import (
            get_active_provider_name,
            get_provider_config,
        )

        provider_config_registry.register(get_provider_config, get_active_provider_name)

        # RAG — register the knowledge retriever into the core seam. Core's
        # runtime injects retrieved chunks into Linda's prompt; if this plugin
        # is absent/disabled the seam simply returns [] (additive, disable-safe).
        from core.assistant.knowledge import register_retriever
        from plugins.installed.ai_assistant.services.rag import retrieve as _kb_retrieve

        register_retriever(_kb_retrieve)

        # Keep that index fresh: rag.rebuild() is idempotent, so a nightly beat
        # keeps Linda's knowledge tracking the catalog instead of freezing at
        # the last manual `rebuild_knowledge` run (it had no refresh schedule).
        from celery.schedules import crontab

        self.register_celery_tasks('plugins.installed.ai_assistant.tasks')
        self.register_celery_beat(
            'ai_assistant:rebuild_knowledge',
            {
                'task': 'ai_assistant.rebuild_knowledge',
                'schedule': crontab(hour=4, minute=30),
            },
        )

        # GraphQL extensions
        self.register_graphql_extension('plugins.installed.ai_assistant.graphql.queries')
        self.register_graphql_extension('plugins.installed.ai_assistant.graphql.mutations')

        # Pulse refresh/dismiss — same /dashboard/pulse/... paths the
        # dashboard used to own; they 404 when this plugin is disabled.
        self.register_urls(
            'plugins.installed.ai_assistant.urls_dashboard',
            prefix='dashboard/pulse/',
            namespace='ai_assistant_dashboard',
        )

        # React to store events. PRODUCT_VIEWED + SEARCH_PERFORMED are
        # owned by the `analytics` plugin (the canonical persistence
        # path) and the `tracking` plugin (GA4 firing); ai_assistant
        # used to subscribe with stub tasks that only logged — removed.
        # Storefront retrieval surfaces — search ranking + PDP similars flow
        # through these filters instead of direct imports, so both degrade to
        # the plain-catalog behaviour when this plugin is disabled.
        self.register_hook(events.SEARCH_RANKED_IDS, self.on_search_ranked_ids, priority=10)
        self.register_hook(events.SIMILAR_PRODUCTS, self.on_similar_products, priority=10)
        # No free-form agent runs on order / sign-up / abandoned-cart events: each
        # handed the all-scope Worker a vague objective from a background task,
        # used nothing it produced, and timed out at 45 s on every live order.
        self.register_hook(events.PRODUCT_CREATED, self.on_product_created, priority=90)
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=90)

        # Price filter — AI can influence pricing
        self.register_hook(events.PRODUCT_CALCULATE_PRICE, self.on_calculate_price, priority=50)

        # Linda's Pulse — daily proactive insight refresh + event-driven nudges.
        self._register_pulse_schedule()
        self.register_hook(events.PRODUCT_LOW_STOCK, self._pulse_event_nudge, priority=70)
        self.register_hook('return.requested', self._pulse_event_nudge, priority=70)
        self.register_hook(events.CART_ABANDONED, self._pulse_event_nudge, priority=70)
        # Dashboard-home tiles: insights + pulse panels, the provider half
        # of ai_summary, and the connect-a-provider setup step.
        self.register_hook(events.DASHBOARD_HOME_PANELS, self.on_dashboard_panels, priority=30)
        self.register_hook(events.DASHBOARD_SETUP_STEPS, self.on_setup_steps, priority=30)
        # Morpheus Brain: contribute unread merchant insights (→ improvements.insights).
        self.register_hook(events.BRAIN_SIGNALS, self.on_brain_signals, priority=50)

        # Autonomy gate: answer the background-agent scheduler's AUTONOMY_ENABLED
        # filter from the `enable_autonomous_operator` flag (Settings → AI). This
        # is the master switch for PROACTIVE background-agent runs; off by default
        # (autonomy is opt-in). agent_core consults the filter — it never imports
        # this plugin, and with this plugin disabled the filter stays False.
        from core.agents.events import AgentEvents

        self.register_hook(AgentEvents.AUTONOMY_ENABLED, self._autonomy_gate, priority=50)

    def _autonomy_gate(self, value, **_):
        return bool(value or self.get_config_value('enable_autonomous_operator', False))

    def _register_pulse_schedule(self) -> None:
        from django.conf import settings
        from celery.schedules import crontab

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None)
        if schedule is None:
            return
        schedule.setdefault(
            'ai_assistant.pulse_daily_refresh',
            {
                'task': 'plugins.installed.ai_assistant.tasks.pulse_daily_refresh',
                'schedule': crontab(hour=6, minute=0),
            },
        )
        # Dynamic-pricing re-evaluation. The task short-circuits when
        # `enable_dynamic_pricing` is False, so scheduling it is safe
        # even on stores that don't use AI pricing.
        schedule.setdefault(
            'ai_assistant.evaluate_all_product_prices',
            {
                'task': 'plugins.installed.ai_assistant.tasks.evaluate_all_product_prices',
                'schedule': crontab(minute=0),  # hourly
            },
        )

    def on_dashboard_panels(self, value, date_range=None, **kwargs):
        """Fold unread insights, the Pulse top-5, and the provider half of
        ai_summary into the dashboard-home context."""
        from plugins.installed.ai_assistant.models import MerchantInsight  # noqa: PLC0415

        rows = list(MerchantInsight.objects.filter(is_read=False).order_by('-created_at'))
        value['insights'] = rows[:4]

        prio = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        ranked = sorted(rows, key=lambda r: (prio.get(r.priority, 9), -r.created_at.timestamp()))
        value['pulse'] = ranked[:5]

        summary = value.setdefault(
            'ai_summary',
            {
                'agent_count': 0,
                'recent_runs': 0,
                'unread_insights': 0,
                'provider': '',
                'has_keys': False,
            },
        )
        summary['unread_insights'] = len(rows)
        cfg = self.get_config()
        summary['provider'] = cfg.get('ai_provider') or 'openai'
        summary['has_keys'] = any(
            cfg.get(k)
            for k in (
                'openai_api_key',
                'anthropic_api_key',
                'gemini_api_key',
                'openrouter_api_key',
                'grok_api_key',
                'apikey_api_key',
                'packy_api_key',
                'ollama_api_key',
                'deepseek_api_key',
                'hermes_api_key',
                'moonshot_api_key',
            )
        )
        return value

    def on_setup_steps(self, value, **kwargs):
        """Append the connect-an-AI-provider first-run step."""
        from plugins.installed.ai_assistant.services.config import (  # noqa: PLC0415
            get_provider_config,
        )

        try:
            done = bool(get_provider_config().api_key)
        except Exception:  # noqa: BLE001 — config table may not exist yet
            done = False
        value.append(
            {
                'key': 'ai',
                'label': 'Connect an AI provider',
                'hint': 'OpenAI / Anthropic / Gemini / OpenRouter / Ollama.',
                'url': '/dashboard/settings/ai/',
                'done': done,
            }
        )
        return value

    def _pulse_event_nudge(self, **_kwargs) -> None:
        """Trigger a Pulse refresh on key events so the dashboard panel
        catches a low-stock / RMA / abandoned-cart card without waiting
        for the daily cron. Async via Celery; never blocks the hook."""
        try:
            from plugins.installed.ai_assistant.tasks import pulse_daily_refresh

            pulse_daily_refresh.delay()
        except Exception:  # noqa: BLE001
            pass

    def on_brain_signals(self, value, **kwargs):
        """Merge unread merchant insights into the Brain's Improvements panel
        (→ improvements.insights). Defensive read; disable-gated by the bus."""
        from contextlib import suppress  # noqa: PLC0415

        with suppress(Exception):
            from plugins.installed.ai_assistant.models import MerchantInsight  # noqa: PLC0415

            value.setdefault('improvements', {})['insights'] = [
                {
                    'title': i.title,
                    'type': getattr(i, 'insight_type', ''),
                    'priority': getattr(i, 'priority', ''),
                    'impact': getattr(i, 'estimated_impact', ''),
                }
                for i in MerchantInsight.objects.filter(is_read=False).order_by('-created_at')[:10]
            ]
        return value

    def on_search_ranked_ids(self, value, query='', limit=80, **kwargs):
        """SEARCH_RANKED_IDS: hybrid (BM25 + embeddings) ranking for search."""
        from plugins.installed.ai_assistant.services.search import hybrid_search  # noqa: PLC0415

        return [p.pk for p in hybrid_search(query, top_k=limit)]

    def on_similar_products(self, value, product=None, limit=4, **kwargs):
        """SIMILAR_PRODUCTS: content-similar products for the PDP."""
        if product is None:
            return None
        from plugins.installed.ai_assistant.services.recommendations import similar_to  # noqa: PLC0415

        return list(similar_to(product, limit=limit))

    def on_product_created(self, product, **kwargs):
        """(Re)embed for search. Descriptions are written on request from the
        product editor's AI writer, where a person reviews them — never
        autonomously on creation."""
        self._enqueue_embedding(product)

    def on_product_updated(self, product, **kwargs):
        self._enqueue_embedding(product)

    def _enqueue_embedding(self, product) -> None:
        """Best-effort: schedule an embedding refresh; never raise from a hook."""
        try:
            from plugins.installed.ai_assistant.tasks import refresh_product_embedding

            refresh_product_embedding.delay(str(product.id))
        except Exception:  # noqa: BLE001 — task system may be down; degrade gracefully
            import logging

            logging.getLogger('morpheus.ai').warning(
                'Failed to enqueue embedding refresh for product %s',
                product.id,
                exc_info=True,
            )

    def on_calculate_price(self, value, product=None, customer=None, **kwargs):
        """AI dynamic pricing hook — returns adjusted price if strategy active."""
        if not self.get_config_value('enable_dynamic_pricing', False):
            return value
        from plugins.installed.ai_assistant.services.pricing import DynamicPricingService

        return DynamicPricingService.calculate(value, product=product, customer=customer)

    def get_config_schema(self):
        # NB: order of properties drives form-field rendering order in
        # the dashboard. Providers are grouped together at the top, then
        # the active selection, then feature toggles.
        return {
            'type': 'object',
            'properties': {
                # ── OpenAI ────────────────────────────────────────────
                'openai_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'OpenAI · API Key',
                    'description': 'Leave blank to use the OPENAI_API_KEY env var.',
                },
                'openai_base_url': {
                    'type': 'string',
                    'title': 'OpenAI · Base URL',
                    'description': 'Override only if proxying. Default: https://api.openai.com/v1',
                },
                'openai_model': {
                    'type': 'string',
                    'title': 'OpenAI · Default model',
                    'default': 'gpt-4o-mini',
                },
                # ── Anthropic ─────────────────────────────────────────
                'anthropic_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Anthropic · API Key',
                    'description': 'Leave blank to use the ANTHROPIC_API_KEY env var.',
                },
                'anthropic_model': {
                    'type': 'string',
                    'title': 'Anthropic · Default model',
                    'default': 'claude-3-5-sonnet-latest',
                },
                # ── Google Gemini ─────────────────────────────────────
                'gemini_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Gemini · API Key',
                    'description': 'Google AI Studio key (GEMINI_API_KEY).',
                },
                'gemini_model': {
                    'type': 'string',
                    'title': 'Gemini · Default model',
                    'default': 'gemini-2.0-flash',
                },
                # ── OpenRouter ────────────────────────────────────────
                'openrouter_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'OpenRouter · API Key',
                    'description': 'Single-key access to many model vendors. https://openrouter.ai/keys',
                },
                'openrouter_base_url': {
                    'type': 'string',
                    'title': 'OpenRouter · Base URL',
                    'default': 'https://openrouter.ai/api/v1',
                },
                'openrouter_model': {
                    'type': 'string',
                    'title': 'OpenRouter · Default model',
                    'description': 'Format: vendor/model — e.g. anthropic/claude-3.5-sonnet',
                },
                # ── Grok (xAI) ────────────────────────────────────────
                'grok_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Grok · API Key',
                    'description': 'xAI API key. https://console.x.ai',
                },
                'grok_base_url': {
                    'type': 'string',
                    'title': 'Grok · Base URL',
                    'default': 'https://api.x.ai/v1',
                },
                'grok_model': {
                    'type': 'string',
                    'title': 'Grok · Default model',
                    'default': 'grok-4',
                    'description': 'e.g. grok-4 · grok-4-fast-reasoning · grok-3',
                },
                # ── apikey.fun (unified OpenAI-compatible gateway) ────
                'apikey_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'apikey.fun · API Key',
                    'description': 'apikey.fun API key. https://apikey.fun/docs',
                },
                'apikey_base_url': {
                    'type': 'string',
                    'title': 'apikey.fun · Base URL',
                    'default': 'https://api.apikey.fun/v1',
                },
                'apikey_model': {
                    'type': 'string',
                    'title': 'apikey.fun · Default model',
                    'default': 'gpt-4o-mini',
                    'description': 'Any model apikey.fun serves, e.g. gpt-4o · claude-3-5-sonnet.',
                },
                # ── DeepSeek (OpenAI-compatible) ──────────────────────
                'deepseek_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'DeepSeek · API Key',
                    'description': 'DeepSeek API key. https://platform.deepseek.com/api_keys',
                },
                'deepseek_base_url': {
                    'type': 'string',
                    'title': 'DeepSeek · Base URL',
                    'default': 'https://api.deepseek.com',
                },
                'deepseek_model': {
                    'type': 'string',
                    'title': 'DeepSeek · Default model',
                    'default': 'deepseek-chat',
                    'description': 'e.g. deepseek-chat · deepseek-reasoner',
                },
                # ── Packy (www.packyapi.com — Chinese LLM gateway) ────
                'packy_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Packy · API Key',
                    'description': 'packyapi.com key. OpenAI-compatible gateway proxying Claude, GPT, Gemini etc.',
                },
                'packy_base_url': {
                    'type': 'string',
                    'title': 'Packy · Base URL',
                    'default': 'https://www.packyapi.com/v1',
                },
                'packy_model': {
                    'type': 'string',
                    'title': 'Packy · Default model',
                    'default': 'claude-3-5-sonnet-20241022',
                    'description': 'Model group prefix selects upstream — e.g. claude-officially/claude-haiku-4-5-20251001',
                },
                # ── Hermes (NousResearch — native function-calling) ───
                'hermes_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Hermes · API Key',
                    'description': "NousResearch Hermes 3/4. Defaults to the OpenRouter gateway — paste an OpenRouter key, or point Base URL at Nous's own inference API.",
                },
                'hermes_base_url': {
                    'type': 'string',
                    'title': 'Hermes · Base URL',
                    'default': 'https://openrouter.ai/api/v1',
                },
                'hermes_model': {
                    'type': 'string',
                    'title': 'Hermes · Default model',
                    'default': 'nousresearch/hermes-3-llama-3.1-405b',
                    'description': 'e.g. nousresearch/hermes-3-llama-3.1-405b · nousresearch/hermes-4-405b',
                },
                # ── Moonshot AI (Kimi — long-context, agentic) ────────
                'moonshot_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Moonshot (Kimi) · API Key',
                    'description': 'Moonshot AI key. https://platform.moonshot.ai',
                },
                'moonshot_base_url': {
                    'type': 'string',
                    'title': 'Moonshot (Kimi) · Base URL',
                    'default': 'https://api.moonshot.ai/v1',
                    'description': 'Use https://api.moonshot.cn/v1 for the China endpoint.',
                },
                'moonshot_model': {
                    'type': 'string',
                    'title': 'Moonshot (Kimi) · Default model',
                    'default': 'kimi-latest',
                    'description': 'e.g. kimi-latest · kimi-k2-0711-preview · moonshot-v1-128k',
                },
                # ── Ollama (cloud or self-hosted) ─────────────────────
                'ollama_base_url': {
                    'type': 'string',
                    'title': 'Ollama · Base URL',
                    'description': 'Self-hosted: http://localhost:11434 · Cloud: https://ollama.com',
                    'default': 'http://localhost:11434',
                },
                'ollama_api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Ollama · API Key',
                    'description': 'Required for Ollama Cloud only.',
                },
                'ollama_model': {
                    'type': 'string',
                    'title': 'Ollama · Default model',
                    'default': 'llama3.2',
                },
                # ── Active provider selector ─────────────────────────
                'ai_provider': {
                    'type': 'string',
                    'enum': [
                        'openai',
                        'anthropic',
                        'gemini',
                        'openrouter',
                        'grok',
                        'apikey',
                        'deepseek',
                        'packy',
                        'hermes',
                        'moonshot',
                        'ollama',
                    ],
                    'default': 'openai',
                    'title': 'Active provider',
                    'description': 'Which provider the assistant + agent layer call by default.',
                },
                # ── Feature toggles ──────────────────────────────────
                'enable_intent_engine': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable intent engine',
                    'description': (
                        'Lets agents propose authorised actions (browse, checkout, '
                        'subscribe…) through the intent state machine. Off blocks new '
                        'intent proposals; in-flight intents still resolve.'
                    ),
                },
                'enable_semantic_search': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable semantic search',
                    'description': (
                        'Gives Linda the catalog.semantic_search tool — meaning-based '
                        'product retrieval (dense embeddings, keyword fallback). Off '
                        'removes the tool from her catalogue.'
                    ),
                },
                'enable_dynamic_pricing': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable dynamic pricing',
                },
                'enable_zero_shot_catalog': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable zero-shot catalog classification',
                    'description': (
                        'Gives Linda the catalog.classify_product tool: zero-shot '
                        'classification of a product into your categories (or custom '
                        'labels) via the LLM, no training data. Off → the tool is '
                        'absent from the agent catalogue.'
                    ),
                },
                'enable_autonomous_operator': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable autonomous operator',
                    'description': (
                        'Master switch for PROACTIVE background-agent runs. Off → the '
                        'scheduler never auto-runs background agents (manual “run now” '
                        'still works). Turn on only when you want Linda’s background '
                        'agents to act on their schedule.'
                    ),
                },
                'enable_synthetic_testing': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable synthetic testing (coming soon)',
                    'description': (
                        'Not yet implemented — no synthetic-testing service is wired '
                        'behind this toggle. Reserved for automated store smoke tests; '
                        'leave off.'
                    ),
                },
                # NOTE: `agent_purchase_requires_approval` and
                # `memory_confidence_decay_days` were removed (2026-07) —
                # both rendered in Settings but were consumed by NOTHING.
                # A "Recommended on" switch that does nothing is a
                # credibility bug; re-add only together with the code that
                # reads it. (Purchase gating today = the per-tool
                # `confirmed`/hard-gate flow in core/assistant/tools.)
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='AI providers',
            description='API keys and default models for OpenAI, Anthropic, Gemini, OpenRouter, Grok, apikey.fun, DeepSeek, Packy, Hermes (NousResearch), and Ollama. Pick the active provider with "Active provider".',
            schema=self.get_config_schema(),
            category='ai',
        )

    def contribute_agent_tools(self) -> list:
        """Expose AI-signal services to Linda + the agent layer, each behind its
        feature flag (Settings → AI). The services already exist; the flag gates
        whether the tool is registered at all (off → absent from the catalogue)."""
        tools: list = []
        if self.get_config_value('enable_semantic_search'):
            from plugins.installed.ai_assistant.agent_tools import semantic_search_tool

            tools.append(semantic_search_tool)
        if self.get_config_value('enable_zero_shot_catalog'):
            from plugins.installed.ai_assistant.agent_tools import zero_shot_classify_tool

            tools.append(zero_shot_classify_tool)
        return tools
