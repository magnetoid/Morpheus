from __future__ import annotations

import logging

from morpheus import Plugin, SettingsPanel, events

logger = logging.getLogger('morpheus.orders')


class OrdersPlugin(Plugin):
    name = 'orders'
    label = 'Orders'
    version = '1.0.0'
    description = 'Cart, order lifecycle, fulfillment, refunds, transactional email.'
    has_models = True
    requires = ['catalog', 'customers']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.orders.graphql.queries')
        self.register_graphql_extension('plugins.installed.orders.graphql.mutations')
        self.register_hook('payment.captured', self.on_payment_captured, priority=10)
        # NOTE: the order-confirmation email is owned solely by the core
        # transactional spine (core/emails/handlers.on_order_placed) — sent async
        # on commit with retries. This plugin no longer subscribes ORDER_PLACED
        # for email (it used to send a duplicate, synchronously, inside the
        # order-placement transaction).
        # Contribute order + return activity to the dashboard home feed.
        self.register_hook(events.ACTIVITY_FEED, self.on_activity_feed, priority=10)
        # Contribute order count / open returns / store credit to the
        # storefront account-home summary.
        self.register_hook(events.ACCOUNT_SUMMARY_FIELDS, self.on_account_summary, priority=10)
        # GDPR slices (customer.data_export / customer.anonymise) + the
        # login cart hand-off — orders-owned so customers never imports us.
        from plugins.installed.orders import gdpr  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_DATA_EXPORT, gdpr.on_customer_export, priority=10)
        self.register_hook(events.CUSTOMER_ANONYMISE, gdpr.on_customer_anonymise, priority=10)
        self.register_hook(events.CUSTOMER_LOGIN, self.on_customer_login, priority=30)
        # Nav-bar cart item count — contributed to every template (it reads
        # orders.Cart). The aggregator in plugins/context_processors.py runs it
        # only while orders is active, so the count vanishes on disable.
        from plugins.installed.orders.context_processors import cart_context  # noqa: PLC0415

        self.register_context_processor(cart_context)
        # Dashboard-home tiles: KPI row, recent-orders panel, setup step.
        from plugins.installed.orders import dashboard  # noqa: PLC0415

        self.register_hook(events.DASHBOARD_KPIS, dashboard.on_dashboard_kpis, priority=10)
        self.register_hook(events.DASHBOARD_HOME_PANELS, dashboard.on_dashboard_panels, priority=10)
        self.register_hook(events.DASHBOARD_SETUP_STEPS, dashboard.on_setup_steps, priority=20)
        # Register signals on import.
        from plugins.installed.orders import signals  # noqa: F401, PLC0415

    def get_config_schema(self):
        return {
            'type': 'object',
            'properties': {
                'skip_shipping_for_digital_carts': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Skip shipping step for digital/virtual carts',
                    'description': (
                        'When every cart item is flagged '
                        'requires_shipping=False (digital downloads, '
                        'virtual services, gift cards), the checkout '
                        'flow skips the shipping-address form and '
                        'shipping-method picker. Customer only enters '
                        'their email.'
                    ),
                },
                'digital_withdrawal_waiver_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Require a withdrawal-waiver for digital goods',
                    'description': (
                        'EU consumer law (Directive 2011/83/EU art. 16(m)): to '
                        'supply digital content before the 14-day withdrawal '
                        'period ends, the buyer must expressly consent and '
                        'acknowledge they lose the right of withdrawal. When on, '
                        'a required checkbox appears at checkout whenever the cart '
                        'contains a downloadable/digital item, and the '
                        'acknowledgement is recorded on the order.'
                    ),
                },
                'digital_withdrawal_waiver_text': {
                    'type': 'string',
                    'title': 'Withdrawal-waiver checkbox text',
                    'description': (
                        'The exact wording shown next to the checkbox and stored '
                        'on the order. Review with your own legal counsel — this '
                        'default is a common formulation, not legal advice.'
                    ),
                    'default': (
                        'I expressly request immediate access to the digital '
                        'content in my order, and I acknowledge that I thereby '
                        'lose my 14-day right of withdrawal once the download or '
                        'streaming begins.'
                    ),
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Checkout & cart',
            description='Tweaks to the cart + checkout flow. Defaults are sensible for new stores.',
            schema=self.get_config_schema(),
            category='general',
        )

    def on_payment_captured(self, payment, **kwargs):
        from plugins.installed.orders.services import OrderService  # noqa: PLC0415

        OrderService.confirm_order(payment.order)

    def on_customer_login(self, customer=None, request=None, **kwargs):
        """CUSTOMER_LOGIN: adopt/merge the anonymous-session cart onto the
        account. Fail-soft — a cart hiccup must never break login."""
        try:
            from plugins.installed.orders.services import (  # noqa: PLC0415
                merge_session_cart_on_login,
            )

            merge_session_cart_on_login(request, customer)
        except Exception:  # noqa: BLE001
            import logging  # noqa: PLC0415

            logging.getLogger('morpheus.orders').warning(
                'cart merge on login failed', exc_info=True
            )

    def on_account_summary(self, value, user=None, **kwargs):
        """Fold this customer's order count, open returns and store-credit
        balance into the account-home summary (``ACCOUNT_SUMMARY_FIELDS``
        filter). Mutate the dict, return it; the hook bus isolates failures.
        """
        from plugins.installed.orders import store_credit  # noqa: PLC0415
        from plugins.installed.orders.models import Order  # noqa: PLC0415
        from plugins.installed.orders.refunds import ReturnRequest  # noqa: PLC0415

        value['orders_count'] = Order.objects.filter(customer=user).count()
        value['pending_returns'] = ReturnRequest.objects.filter(
            order__customer=user,
            state__in=('requested', 'approved', 'received'),
        ).count()
        value['store_credit_balance'] = store_credit.balance(user)
        return value

    def on_activity_feed(self, value, limit=20, **kwargs):
        """Fold recent order events + return-request activity into the
        dashboard home feed (``ACTIVITY_FEED`` filter). Append own items,
        return the list; the hook bus isolates failures.
        """
        from plugins.installed.orders.models import OrderEvent  # noqa: PLC0415
        from plugins.installed.orders.refunds import ReturnRequest  # noqa: PLC0415

        for ev in OrderEvent.objects.select_related('order').order_by('-created_at')[: limit * 2]:
            verb = (ev.event_type or 'updated').replace('_', ' ').replace('.', ' ')
            value.append(
                {
                    'kind': 'order',
                    'icon': 'shopping-bag',
                    'label': f'Order #{ev.order.order_number} — {verb}',
                    'hint': ev.message or '',
                    'url': f'/dashboard/orders/{ev.order.order_number}/',
                    'when': ev.created_at,
                }
            )
        for rr in ReturnRequest.objects.select_related('order').order_by('-updated_at')[:limit]:
            value.append(
                {
                    'kind': 'return',
                    'icon': 'undo-2',
                    'label': f'RMA {rr.rma_number} — {rr.get_state_display()}',
                    'hint': f'Order #{rr.order.order_number}',
                    'url': f'/dashboard/returns/{rr.id}/',
                    'when': rr.updated_at,
                }
            )
        return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.orders.agent_tools import (  # noqa: PLC0415
            analytics_summary_tool,
            analytics_top_products_tool,
            approve_return_tool,
            list_returns_tool,
            orders_get_tool,
            orders_search_tool,
            refund_order_tool,
        )

        return [
            refund_order_tool,
            list_returns_tool,
            approve_return_tool,
            orders_search_tool,
            orders_get_tool,
            analytics_summary_tool,
            analytics_top_products_tool,
        ]
