"""Reviews plugin — uses ``catalog.Review`` rather than defining its own model.

The catalog already ships a Review model (product, customer, rating, body,
is_approved, is_verified_purchase). This plugin contributes the storefront
write form and a thin view; merchant moderation lives in the existing
catalog admin.
"""
