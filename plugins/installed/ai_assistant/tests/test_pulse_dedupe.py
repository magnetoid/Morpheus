"""Pulse keeps one unread card per signal, however the card is worded.

The duplicate key was a hash of the card's title, written after the AI reworded it
and with the count inside it ("2 carts abandoned", "3 Carts Abandoned"), so every
refresh made a new card: dotbooks had 1,145 unread insights, 992 of them one
abandoned-cart alert, up to 57 a day.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from plugins.installed.ai_assistant.models import MerchantInsight
from plugins.installed.ai_assistant.services import pulse


def _cart_signal(n):
    return lambda: {
        'insight_type': 'opportunity',
        'priority': 'medium',
        'title': f'{n} abandoned cart(s) older than 3h',
        'body': 'Recovery emails go out automatically.',
        'estimated_impact': '',
        'suggested_action': {
            'kind': 'open_view',
            'url': '/dashboard/cart-abandonment/',
            'label': 'Open',
        },
    }


class PulseDedupeTests(TestCase):
    def _run(self, n, title):
        def reword(payload, **_kw):
            payload['title'] = title

        with (
            mock.patch.object(pulse, '_abandoned_cart_signal', _cart_signal(n)),
            mock.patch.object(pulse, '_humanize_signal', side_effect=reword),
        ):
            for name in (
                '_low_stock_signal',
                '_new_rma_signal',
                '_revenue_delta_signal',
                '_expiring_promo_signal',
                '_poor_review_signal',
            ):
                mock.patch.object(pulse, name, lambda: None).start()
            try:
                pulse.generate_pulse_insights(humanize=True)
            finally:
                mock.patch.stopall()

    def test_a_reworded_card_with_a_new_count_updates_the_unread_one(self):
        self._run(2, '2 carts abandoned')
        self._run(3, '3 Carts Abandoned')
        self._run(3, 'Carts >3h')
        rows = MerchantInsight.objects.filter(is_read=False)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().title, 'Carts >3h')

    def test_once_read_the_next_refresh_makes_a_fresh_card(self):
        self._run(2, '2 carts abandoned')
        MerchantInsight.objects.update(is_read=True)
        self._run(4, '4 carts abandoned')
        self.assertEqual(MerchantInsight.objects.filter(is_read=False).count(), 1)
