"""Regression: one-page checkout must send valid AddressInput field names.

A field-name mismatch (addressLine1 vs line1) 500'd every checkout submit
once the one-page flow became the default. This locks the contract.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.storefront.views.checkout_one_page import _shipping_input


def _camel(name: str) -> str:
    head, *tail = name.split('_')
    return head + ''.join(p.title() for p in tail)


class ShippingInputContractTests(SimpleTestCase):
    def test_keys_match_addressinput_camelcase(self):
        sent = set(_shipping_input({}).keys())
        self.assertEqual(
            sent,
            {
                'firstName',
                'lastName',
                'line1',
                'line2',
                'city',
                'state',
                'postalCode',
                'country',
                'phone',
            },
        )
        # Never the old broken names that caused the 500.
        self.assertNotIn('addressLine1', sent)

    def test_keys_are_real_addressinput_fields(self):
        # Every key we send must exist on AddressInput (camelCase of its
        # python fields) — catches future schema drift.
        valid = {_camel(f.python_name) for f in AddressInput.__strawberry_definition__.fields}
        sent = set(_shipping_input({}).keys())
        self.assertTrue(sent <= valid, f'unknown AddressInput fields: {sent - valid}')

    def test_maps_form_values(self):
        out = _shipping_input(
            {'first_name': 'Ada', 'address_line1': '1 Byron St', 'postal_code': 'EC1'}
        )
        self.assertEqual(out['firstName'], 'Ada')
        self.assertEqual(out['line1'], '1 Byron St')
        self.assertEqual(out['postalCode'], 'EC1')
