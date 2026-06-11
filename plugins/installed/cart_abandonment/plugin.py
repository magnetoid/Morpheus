"""Cart Abandonment plugin.

Periodically scans for carts that have items, haven't been touched for
a while, and aren't yet recovered. For each one we fire
``events.CART_ABANDONED`` exactly once (we mark it via cart metadata so
re-runs don't double-emit). Email + remarketing plugins subscribe to
the event and take it from there.

Configuration (set per-plugin in the dashboard or DB):
    abandon_after_minutes  — default 60. How long since updated_at
        before we treat the cart as abandoned.
    require_email          — default True. Skip carts where we have no
        way to reach the customer.
"""

from __future__ import annotations

from morpheus import Plugin


class CartAbandonmentPlugin(Plugin):
    name = 'cart_abandonment'
    label = 'Cart Abandonment'
    version = '0.1.0'
    description = (
        'Fires events.CART_ABANDONED for stale carts so email + '
        'remarketing handlers can pick them up.'
    )
    has_models = False

    def ready(self) -> None:
        self.register_celery_tasks('plugins.installed.cart_abandonment.tasks')
        self.register_celery_beat(
            'cart_abandonment.scan_abandoned',
            {
                'task': 'plugins.installed.cart_abandonment.tasks.scan_abandoned_carts',
                # Every 30 minutes — short enough to feel responsive,
                # long enough that DB load is trivial on a busy store.
                'schedule': 60 * 30,
            },
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
            },
        }
