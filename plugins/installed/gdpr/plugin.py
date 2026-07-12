"""GDPR compliance plugin — EU data-subject rights + legal pages.

Consent capture (the cookie banner + ConsentLog) is owned by the separate
``consent`` plugin; this plugin does NOT rebuild it. What it adds is the
*rights* layer on top:

  * Self-service data export (Art. 15) + account deletion (Art. 17) at
    /account/privacy/, delegating the actual work to
    ``customers.services.gather_customer_data`` / ``anonymise_customer``.
  * A ``DataRequest`` audit row per exercised right.
  * A privacy tile in the account area + Privacy / Terms / cookie-preferences
    links in the storefront footer — both contributed (disable-safe).
  * Idempotent seeding of Privacy / Terms / Imprint CMS pages.

All self-service pages sit behind the Settings → General → GDPR/ePrivacy
master switch (``gdpr_enabled``), so a merchant outside GDPR jurisdiction can
turn the whole surface off.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class GdprPlugin(Plugin):
    name = 'gdpr'
    label = 'GDPR / Privacy'
    version = '0.1.0'
    has_models = True
    requires = ['consent', 'customers', 'cms']
    description = (
        'EU data-subject rights (Art. 15 export + Art. 17 erasure) as a '
        'self-service account hub, an auditable DataRequest trail, and seeded '
        'Privacy / Terms / Imprint legal pages. Cookie consent stays with the '
        'consent plugin.'
    )

    def ready(self) -> None:
        # Data-rights pages at the site root (/account/privacy/, …).
        self.register_urls('plugins.installed.gdpr.urls', prefix='', namespace='gdpr')

    def contribute_storefront_blocks(self) -> list:
        # Both surfaces are registry-gated contributions, so disabling the
        # plugin removes the account tile AND the footer legal links.
        return [
            StorefrontBlock(
                slot='account_nav',
                template='gdpr/blocks/account_nav.html',
                priority=90,
            ),
            StorefrontBlock(
                slot='footer_extra',
                template='gdpr/blocks/footer_links.html',
                priority=90,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='GDPR / Privacy',
            description=(
                'Data-controller identity used on the seeded legal pages. The '
                'master on/off switch lives under Settings → General '
                '(GDPR/ePrivacy).'
            ),
            schema=self.get_config_schema(),
            category='general',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'data_controller_name': {
                    'type': 'string',
                    'title': 'Data controller name',
                    'description': 'Legal entity named on the Privacy / Imprint pages.',
                    'default': '',
                },
                'data_controller_email': {
                    'type': 'string',
                    'title': 'Privacy contact email',
                    'description': 'Where data-rights enquiries are sent.',
                    'default': '',
                },
            },
        }
