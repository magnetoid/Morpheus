"""Agentic Commerce Protocol (ACP) — agent-driven checkout.

Lets AI agents (ChatGPT Instant Checkout et al.) discover our catalog and
build a priced, conformant ``CheckoutSession`` against our own ``Cart``. We
are the *server*; the agent calls us. Grounded in the real ACP
``2026-04-17`` OpenAPI (``openapi.agentic_checkout.yaml`` + ``openapi.feed.yaml``).

Phase 1 (this plugin, shipped OFF by default):
  * ``/.well-known/acp.json`` discovery manifest.
  * the ACP product feed (read-only, reuses ``google_shopping`` mapping).
  * ``createCheckoutSession`` / ``getCheckoutSession`` /
    ``updateCheckoutSession`` / ``cancelCheckoutSession`` backed by ``Cart``.
  * Bearer/scope auth (``acp.checkout``), conformant ``CheckoutSession`` JSON.
  * ``completeCheckoutSession`` exists but returns a conformant
    ``MessageError`` with code ``unsupported`` — the money path (Stripe Shared
    Payment Token redemption) is Phase 2.

Disable test: deleting this plugin removes the manifest, feed, and the
``/acp/`` endpoints; nothing in core or a sibling plugin references it.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel

# ACP spec version we implement; echoed in the ``API-Version`` response header.
ACP_API_VERSION = '2026-04-17'


class AgenticCheckoutPlugin(Plugin):
    name = 'agentic_checkout'
    label = 'Agentic Commerce Protocol (ACP)'
    version = '0.1.0'
    description = (
        'Agentic Commerce Protocol (2026-04-17) checkout surface. AI agents '
        '(ChatGPT Instant Checkout, etc.) discover the catalog via '
        '/.well-known/acp.json + an ACP product feed, then create a priced, '
        'conformant CheckoutSession backed by our Cart. Bearer/scope auth '
        '(acp.checkout). Phase 1 — read/quote only; the money path '
        '(Stripe Shared Payment Token) is OFF until a merchant enrolls.'
    )
    has_models = False
    # OFF by default — no live money path yet; a merchant opts in from
    # Dashboard → Apps once enrolled in Stripe ACP.
    enabled_by_default = False
    requires = ['orders', 'catalog', 'inventory', 'agent_mcp', 'google_shopping']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.agentic_checkout.urls',
            prefix='acp/',
            namespace='agentic_checkout',
        )
        self.register_urls(
            'plugins.installed.agentic_checkout.urls_well_known',
            prefix='.well-known/',
            namespace='agentic_checkout_well_known',
        )

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Agentic Commerce Protocol',
            description=(
                'Expose the catalog + checkout to AI agents over ACP. Requires '
                'a Bearer token (Settings → Developer → API tokens) with the '
                'acp.checkout scope. The money path needs a Stripe ACP '
                'enrollment (Phase 2).'
            ),
            category='checkout',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Master switch',
                },
                'session_ttl_minutes': {
                    'type': 'integer',
                    'default': 60,
                    'minimum': 5,
                    'title': 'Checkout session lifetime (minutes)',
                },
            },
        }
