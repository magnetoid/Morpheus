"""
metafields — schema-less custom fields on any record.

Shopify's killer escape valve: every Product, Customer, Order, Page
can carry an arbitrary number of `(namespace, key, value)` triples
that the merchant or a plugin defines. Used for:
  • product attributes the catalog model doesn't have a column for
    (warranty months, ingredients list, fabric type, ASIN);
  • customer preferences (preferred-size, marketing-flag);
  • order custom data (gift-message, source-campaign);
  • plugin-private data without each plugin needing its own table.

Why we need it: Morpheus already has a strong typed catalog, but
real merchants always need ONE more field. Metafields are the right
answer to "can I add X to a product without changing the schema".

Design decisions:
  * `(content_type, object_id)` GenericForeignKey — works for every
    Django model out of the box, no per-model registration.
  * `(namespace, key)` are merchant-controlled strings; the platform
    doesn't gate them. Convention is `<plugin_name>.<key>` for plugin-
    owned metafields, bare `<key>` for merchant-defined.
  * `value_type` is a hint, not a strict type — value is a TextField
    that can hold any JSON-serialisable scalar. The hint drives the
    rendering (text input vs date picker vs file picker).
  * Unique on `(content_type, object_id, namespace, key)` so set()
    is idempotent.
  * Reads through `MetafieldManager.for_obj(instance)` return a flat
    `{namespace.key: typed_value}` dict — usable directly in Django
    templates.
"""
