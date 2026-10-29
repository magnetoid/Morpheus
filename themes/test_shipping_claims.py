"""No theme writes a shipping price or threshold into its templates.

A shipping cost is a promise checkout must keep, so it comes from the shipping
app's rates (the ``shipping_rates`` slot, the cart's free-shipping bar). Until
v0.128.0 dotbooks' shipping and about pages promised "$5 flat" and free
shipping over $40 while no store had a single rate configured.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_COMMENTS = re.compile(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}', re.S)
_CLAIMS = re.compile(
    r'free\s+(?:shipping|delivery)[^<{]{0,40}?(?:over|above)\s*[$£€]\s*\d'
    r'|free\s+on\s+orders\s+over\s*[$£€]\s*\d'
    r'|[$£€]\s*\d+(?:\.\d+)?\s*flat',
    re.I,
)


class ShippingClaimsTests(SimpleTestCase):
    def test_no_theme_hardcodes_a_shipping_price(self):
        root = Path(settings.BASE_DIR) / 'themes' / 'library'
        found = []
        for path in root.glob('*/templates/**/*.html'):
            text = _COMMENTS.sub('', path.read_text())
            found += [f'{path.relative_to(root)}: {m.group(0)!r}' for m in _CLAIMS.finditer(text)]
        self.assertEqual(found, [], 'Render shipping prices from the shipping app.')
