"""GDPR / ePrivacy cookie consent plugin.

EU sites without an opt-in cookie banner are violating ePrivacy + GDPR.
This plugin ships:

  * /consent/save/         — POST endpoint that records a decision +
                             sets the ``morpheus_consent`` cookie.
  * /consent/preferences/  — settings page so customers can change
                             their choice later.
  * A storefront block that renders the banner near </body> when the
    cookie is missing.
  * A ``ConsentLog`` row per decision (audit trail; required under
    Art. 7(1) GDPR — controller must be able to demonstrate consent).

Tracking integration: ``plugins.installed.tracking`` gates its GTM
container on ``analytics`` / ``marketing`` flags read from the cookie,
so the banner controls real loading — not just downstream tags.
"""

from __future__ import annotations

from morpheus.app import Plugin, StorefrontBlock
from morpheus.core import events


class ConsentPlugin(Plugin):
    name = 'consent'
    label = 'Cookie Consent'
    version = '0.1.0'
    description = (
        'GDPR / ePrivacy cookie banner with per-category opt-in '
        '(necessary, analytics, marketing, functional), persistent '
        'cookie, and an auditable ConsentLog of every decision.'
    )

    def ready(self) -> None:
        # GDPR slice: contribute this plugin's data to the export/erasure.
        from plugins.installed.consent import gdpr  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_DATA_EXPORT, gdpr.on_customer_export, priority=30)
        self.register_urls(
            'plugins.installed.consent.urls',
            prefix='consent/',
            namespace='consent',
        )

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # global_below_body: banner is fixed-position so the slot is
        # purely for injection — it sits over content via CSS.
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='storefront/blocks/_consent_banner.html',
                priority=90,
            ),
        ]
