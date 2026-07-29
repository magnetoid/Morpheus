"""On-site AI stylist — the brand voice in a chat window.

Reskins the existing `ai_assistant` for the *shopper*. Lives in its
own plugin (not in ai_assistant) so:

  * the shop-side AI surface and the merchant-side Linda operator
    have separate enable switches;
  * disable = the storefront loses the AI chat widget and falls
    back to the existing search box.

The widget contributes a `StorefrontBlock` that mounts a chat panel
on every storefront page. Messages proxy to a thin GraphQL surface
that the merchant can run against the same provider their admin
agent already uses. Every reply is recorded via
`core.audit.services.record_ai_decision` so EU AI Act art. 12/13
audit is automatic.
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel


class AiStylistPlugin(Plugin):
    name = 'ai_stylist'
    label = 'On-site AI stylist'
    version = '1.0.0'
    description = (
        'Conversational shopping assistant on the storefront. Pulls the '
        'same RAG + provider config the admin agent uses, but with the '
        'shopper-facing persona + audit trail.'
    )
    has_models = True
    requires = ['ai_assistant', 'core.audit', 'consent']

    def contribute_storefront_blocks(self) -> list:
        # Widget withheld: the template ships no CSS/JS and there is no
        # shopper-facing backend endpoint yet, so it rendered as raw unstyled
        # markup ("Aria / Ask me anything…") in the page's bottom-left corner.
        # Until the panel styling, the send/poll script, and a consent-gated,
        # rate-limited storefront endpoint land, this contributes nothing to the
        # storefront (the crm plugin already provides a working "Chat with us"
        # widget). Restore the StorefrontBlock once the surface is finished.
        return []

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='AI stylist',
            description='Persona name, welcome prompt, system-prompt prelude, consent gating.',
            category='ai',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'persona_name': {
                    'type': 'string',
                    'default': 'Aria',
                    'title': 'Stylist name (shown to shoppers)',
                },
                'welcome_message': {
                    'type': 'string',
                    'default': "Hi! I'm Aria — what are you shopping for today?",
                    'title': 'Welcome prompt',
                },
                'system_prelude': {
                    'type': 'string',
                    'default': (
                        "You are a brand-aware shopping stylist. Speak in the merchant's "
                        'voice. Always cite product names + prices from the catalog. '
                        'Never invent SKUs.'
                    ),
                    'title': 'System prompt prelude',
                },
                'require_consent': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Require explicit consent before first message',
                },
                'audit_trail': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Record every assistant turn in core.audit (EU AI Act art. 12/13)',
                },
            },
        }
