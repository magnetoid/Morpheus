"""Cart Abandonment plugin.

Two jobs, both beat-driven:

1. **Detection** (``scan_abandoned_carts``): fires
   ``events.CART_ABANDONED`` exactly once per newly-stale cart so other
   plugins (crm, ai_assistant, self_improvement) can take non-email
   follow-up actions. We mark it via cart metadata so re-runs don't
   double-emit.

2. **Recovery drip** (``send_cart_recovery_drip``): the SINGLE owner of
   recovery email. A consent-checked, multi-step sequence sent via the
   central email registry (``cart_recovery_1/2/3``). Disable this plugin
   and ALL recovery email stops — there is no other sender.

Configuration (set per-plugin in the dashboard or DB):
    abandon_after_minutes  — default 60. How long since updated_at
        before we treat the cart as abandoned (drives detection).
    require_email          — default True. Skip carts where we have no
        way to reach the customer.
    recovery_enabled       — default True. Master switch for the drip.
    step_delays_minutes    — default [60, 1440, 4320]. Per-step age
        thresholds (minutes since updated_at) for steps 1/2/3.
    require_marketing_consent — default True. Only email customers whose
        latest consent log has marketing=True.
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel


class CartAbandonmentPlugin(Plugin):
    name = 'cart_abandonment'
    label = 'Cart Abandonment'
    version = '0.2.0'
    description = (
        'Fires events.CART_ABANDONED for stale carts and owns the '
        'consent-checked, multi-step cart-recovery email drip.'
    )
    has_models = True
    requires = ['orders', 'consent']

    def ready(self) -> None:
        self.register_celery_tasks('plugins.installed.cart_abandonment.tasks')
        # One-click unsubscribe endpoint for the recovery drip (RFC 8058). Owned
        # by this plugin so the route vanishes when cart-recovery is disabled.
        self.register_urls(
            'plugins.installed.cart_abandonment.urls',
            prefix='',
            namespace='cart_abandonment',
        )
        self.register_celery_beat(
            'cart_abandonment.scan_abandoned',
            {
                'task': 'plugins.installed.cart_abandonment.tasks.scan_abandoned_carts',
                # Every 30 minutes — short enough to feel responsive,
                # long enough that DB load is trivial on a busy store.
                'schedule': 60 * 30,
            },
        )
        self.register_celery_beat(
            'cart_abandonment.recovery_drip',
            {
                'task': 'plugins.installed.cart_abandonment.tasks.send_cart_recovery_drip',
                # Every 15 minutes — fine-grained enough that a step
                # fires close to its configured delay.
                'schedule': 60 * 15,
            },
        )

    def contribute_email_templates(self) -> list:
        from morpheus.plugin import EmailTemplateDef

        return [
            EmailTemplateDef(
                key='cart_recovery_1',
                label='Cart recovery — step 1 (reminder)',
                default_subject='You left items in your cart',
                group='Cart recovery',
                description='First nudge, sent shortly after a cart is abandoned.',
            ),
            EmailTemplateDef(
                key='cart_recovery_2',
                label='Cart recovery — step 2 (still saved)',
                default_subject='Your cart is still waiting',
                group='Cart recovery',
                description='Second reminder, sent a day later if the cart is still open.',
            ),
            EmailTemplateDef(
                key='cart_recovery_3',
                label='Cart recovery — step 3 (last chance)',
                default_subject="Last chance — your cart's about to expire",
                group='Cart recovery',
                description='Final nudge, sent a few days after abandonment.',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Cart recovery',
            description='Abandoned-cart detection and the recovery-email drip.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'abandon_after_minutes': {
                    'type': 'integer',
                    'title': 'Abandon after (minutes)',
                    'default': 60,
                    'minimum': 5,
                },
                'require_email': {
                    'type': 'boolean',
                    'title': 'Skip carts with no email',
                    'default': True,
                },
                'recovery_enabled': {
                    'type': 'boolean',
                    'title': 'Send recovery emails',
                    'default': True,
                },
                'step_delays_minutes': {
                    'type': 'array',
                    'title': 'Recovery step delays (minutes since abandonment)',
                    'items': {'type': 'integer', 'minimum': 1},
                    'default': [60, 1440, 4320],
                },
                'require_marketing_consent': {
                    'type': 'boolean',
                    'title': 'Only email customers with marketing consent',
                    'default': True,
                },
            },
        }
