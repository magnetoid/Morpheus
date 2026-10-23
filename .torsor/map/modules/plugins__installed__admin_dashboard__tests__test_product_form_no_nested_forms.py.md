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

# plugins/installed/admin_dashboard/tests/test_product_form_no_nested_forms.py

Symbols in `plugins/installed/admin_dashboard/tests/test_product_form_no_nested_forms.py`.

- L24 `ProductFormNoNestedFormsTests` (class)
- L25 `setUp(self)` (method)
- L40 `_html(self)` (method)
- L47 `test_no_form_is_nested_inside_the_product_form(self)` (method) — No ``<form>`` opens between #product-form's open and its close.
- L60 `test_variant_forms_live_after_the_product_form_closes(self)` (method) — The delete form and the add-variant modal must sit outside #product-form.
