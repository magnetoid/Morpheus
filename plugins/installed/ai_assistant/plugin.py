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
from morpheus import Plugin, SettingsPanel, events


class AIAssistantPlugin(Plugin):
    name = "ai_assistant"
    label = "AI Signals (embeddings, search, pricing)"
    version = "2.0.0"
    description = (
        "AI signals layer: product embeddings, semantic search, "
        "recommendations, dynamic pricing. The agent runtime now lives in "
        "core.agents + agent_core — see the Agents dashboard."
    )
    has_models = True
    requires = ["catalog", "orders", "customers"]

    def ready(self):
        # GraphQL extensions
        self.register_graphql_extension('plugins.installed.ai_assistant.graphql.queries')
        self.register_graphql_extension('plugins.installed.ai_assistant.graphql.mutations')
        
        # REST/Webhook/Manifest URLs
        self.register_urls('plugins.installed.ai_assistant.urls', prefix='api/')

        # React to store events
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=80)
        self.register_hook(events.PRODUCT_VIEWED, self.on_product_viewed, priority=80)
        self.register_hook(events.CUSTOMER_REGISTERED, self.on_customer_registered, priority=80)
        self.register_hook(events.SEARCH_PERFORMED, self.on_search_performed, priority=80)
        self.register_hook(events.CART_ABANDONED, self.on_cart_abandoned, priority=80)
        self.register_hook(events.PRODUCT_CREATED, self.on_product_created, priority=90)
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=90)

        # Price filter — AI can influence pricing
        self.register_hook(events.PRODUCT_CALCULATE_PRICE, self.on_calculate_price, priority=50)

        # Linda's Pulse — daily proactive insight refresh + event-driven nudges.
        self._register_pulse_schedule()
        self.register_hook(events.PRODUCT_LOW_STOCK, self._pulse_event_nudge, priority=70)
        self.register_hook('return.requested', self._pulse_event_nudge, priority=70)
        self.register_hook(events.CART_ABANDONED, self._pulse_event_nudge, priority=70)

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

    def _pulse_event_nudge(self, **_kwargs) -> None:
        """Trigger a Pulse refresh on key events so the dashboard panel
        catches a low-stock / RMA / abandoned-cart card without waiting
        for the daily cron. Async via Celery; never blocks the hook."""
        try:
            from plugins.installed.ai_assistant.tasks import pulse_daily_refresh
            pulse_daily_refresh.delay()
        except Exception:  # noqa: BLE001
            pass

    def on_order_placed(self, order, **kwargs):
        """Update recommendation model after purchase."""
        from plugins.installed.ai_assistant.tasks import update_recommendations_after_order
        update_recommendations_after_order.delay(str(order.id))

    def on_product_viewed(self, product, customer=None, session_key=None, **kwargs):
        """Record product view for collaborative filtering."""
        from plugins.installed.ai_assistant.tasks import record_product_view
        record_product_view.delay(
            str(product.id),
            str(customer.id) if customer else None,
            session_key,
        )

    def on_customer_registered(self, customer, **kwargs):
        """Initialize memory store for new customer."""
        from plugins.installed.ai_assistant.tasks import initialize_customer_memory
        initialize_customer_memory.delay(str(customer.id))

    def on_search_performed(self, query, results_count=0, customer=None, **kwargs):
        """Log search for intent analysis and improving future results."""
        from plugins.installed.ai_assistant.tasks import log_search_event
        log_search_event.delay(query, results_count, str(customer.id) if customer else None)

    def on_cart_abandoned(self, cart, **kwargs):
        """Generate AI-personalized cart recovery message."""
        from plugins.installed.ai_assistant.tasks import generate_cart_recovery
        generate_cart_recovery.delay(str(cart.id))

    def on_product_created(self, product, **kwargs):
        """If product has no description, auto-generate one. Always (re)embed."""
        if not product.description:
            from plugins.installed.ai_assistant.tasks import generate_product_description
            generate_product_description.delay(str(product.id))
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
                'Failed to enqueue embedding refresh for product %s', product.id,
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
            "type": "object",
            "properties": {
                # ── OpenAI ────────────────────────────────────────────
                "openai_api_key": {
                    "type": "string",
                    "title": "OpenAI · API Key",
                    "description": "Leave blank to use the OPENAI_API_KEY env var.",
                },
                "openai_base_url": {
                    "type": "string",
                    "title": "OpenAI · Base URL",
                    "description": "Override only if proxying. Default: https://api.openai.com/v1",
                },
                "openai_model": {
                    "type": "string",
                    "title": "OpenAI · Default model",
                    "default": "gpt-4o-mini",
                },
                # ── Anthropic ─────────────────────────────────────────
                "anthropic_api_key": {
                    "type": "string",
                    "title": "Anthropic · API Key",
                    "description": "Leave blank to use the ANTHROPIC_API_KEY env var.",
                },
                "anthropic_model": {
                    "type": "string",
                    "title": "Anthropic · Default model",
                    "default": "claude-3-5-sonnet-latest",
                },
                # ── Google Gemini ─────────────────────────────────────
                "gemini_api_key": {
                    "type": "string",
                    "title": "Gemini · API Key",
                    "description": "Google AI Studio key (GEMINI_API_KEY).",
                },
                "gemini_model": {
                    "type": "string",
                    "title": "Gemini · Default model",
                    "default": "gemini-2.0-flash",
                },
                # ── OpenRouter ────────────────────────────────────────
                "openrouter_api_key": {
                    "type": "string",
                    "title": "OpenRouter · API Key",
                    "description": "Single-key access to many model vendors. https://openrouter.ai/keys",
                },
                "openrouter_base_url": {
                    "type": "string",
                    "title": "OpenRouter · Base URL",
                    "default": "https://openrouter.ai/api/v1",
                },
                "openrouter_model": {
                    "type": "string",
                    "title": "OpenRouter · Default model",
                    "description": "Format: vendor/model — e.g. anthropic/claude-3.5-sonnet",
                },
                # ── Ollama (cloud or self-hosted) ─────────────────────
                "ollama_base_url": {
                    "type": "string",
                    "title": "Ollama · Base URL",
                    "description": "Self-hosted: http://localhost:11434 · Cloud: https://ollama.com",
                    "default": "http://localhost:11434",
                },
                "ollama_api_key": {
                    "type": "string",
                    "title": "Ollama · API Key",
                    "description": "Required for Ollama Cloud only.",
                },
                "ollama_model": {
                    "type": "string",
                    "title": "Ollama · Default model",
                    "default": "llama3.2",
                },
                # ── Active provider selector ─────────────────────────
                "ai_provider": {
                    "type": "string",
                    "enum": ["openai", "anthropic", "gemini", "openrouter", "ollama"],
                    "default": "openai",
                    "title": "Active provider",
                    "description": "Which provider the assistant + agent layer call by default.",
                },
                # ── Feature toggles ──────────────────────────────────
                "enable_intent_engine": {"type": "boolean", "default": True, "title": "Enable intent engine"},
                "enable_semantic_search": {"type": "boolean", "default": True, "title": "Enable semantic search"},
                "enable_dynamic_pricing": {"type": "boolean", "default": False, "title": "Enable dynamic pricing"},
                "enable_zero_shot_catalog": {"type": "boolean", "default": True, "title": "Enable zero-shot catalog"},
                "enable_autonomous_operator": {"type": "boolean", "default": False, "title": "Enable autonomous operator"},
                "enable_synthetic_testing": {"type": "boolean", "default": False, "title": "Enable synthetic testing"},
                "agent_purchase_requires_approval": {"type": "boolean", "default": True, "title": "Agent purchases require approval"},
                "memory_confidence_decay_days": {"type": "integer", "default": 90, "title": "Memory confidence decay (days)"},
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='AI providers',
            description='API keys and default models for OpenAI, Anthropic, Gemini, OpenRouter, and Ollama. Pick the active provider with "Active provider".',
            schema=self.get_config_schema(),
            category='ai',
        )
