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
so the banner controls real loading — not just downstream tags. Since
v0.91.0 the decision also travels on every template context as ``consent``
(``context_processors.consent_context``): every ad-pixel block renders only
on ``consent.marketing`` and the analytics beacon only on
``consent.analytics`` — until then the banner recorded a choice that no
pixel read. ``Sec-GPC: 1`` (Global Privacy Control) counts as a refusal of
everything non-essential until the visitor chooses otherwise.
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
        # Server-side sends (core/consent.py) ask the same decision the templates read.
        from plugins.installed.consent import services  # noqa: PLC0415

        self.register_hook(events.CONSENT_DECISION, services.decision_answer, priority=50)
        self.register_hook(
            events.CONSENT_MARKETING_CUSTOMERS, services.marketing_customers_answer, priority=50
        )
        from plugins.installed.consent.context_processors import consent_context  # noqa: PLC0415

        # `consent` on every template context — the gate the tag blocks read.
        # Contributed, so it vanishes with the app (an unmanaged store keeps its tags).
        self.register_context_processor(consent_context)
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
