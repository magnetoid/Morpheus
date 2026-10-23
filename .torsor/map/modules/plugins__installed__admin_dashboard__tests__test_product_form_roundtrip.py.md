---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/installed/admin_dashboard/tests/test_product_form_roundtrip.py

Symbols in `plugins/installed/admin_dashboard/tests/test_product_form_roundtrip.py`.

- L32 `_FormDataSet` (class) — Build the entry list a browser submits for ``<form id=form_id>``.
- L44 `__init__(self, form_id: str)` (method)
- L54 `_owned(self, attrs: dict)` (method)
- L61 `handle_starttag(self, tag, attrs_list)` (method)
- L99 `handle_endtag(self, tag)` (method)
- L120 `handle_data(self, data)` (method)
- L127 `browser_form_data(html: str, form_id: str)` (function)
- L137 `ProductEditorRoundTripTests` (class)
- L138 `setUp(self)` (method)
- L159 `_submitted(self)` (method)
- L164 `_save(self, data)` (method)
- L172 `test_unchanged_save_keeps_inventory_and_shipping_flags(self)` (method)
- L179 `test_unchanged_save_keeps_category_vendor_and_extra_categories(self)` (method)
- L198 `test_each_product_flag_is_submitted_once(self)` (method)
- L204 `test_unticking_featured_and_taxable_persists(self)` (method)
- L215 `test_digital_product_still_drops_inventory_and_shipping(self)` (method)
- L225 `test_a_service_product_stays_a_service_and_unshipped(self)` (method)
- L245 `test_an_unchanged_save_keeps_the_products_currency(self)` (method)
- L260 `test_a_variant_is_priced_in_its_products_currency(self)` (method)
