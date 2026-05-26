"""Admin dashboard forms — shared between every dashboard view.

This package replaces the original 944-LOC ``forms.py`` monolith. The
split is layered by domain; external callers keep importing from
``plugins.installed.admin_dashboard.forms`` unchanged, and the
``getattr(forms, 'StoreGeneralForm')`` lookup in
``views_split/settings.py`` keeps working thanks to the re-exports
below.

  * _helpers.py    — _money, _md_to_html, _ensure_html,
                     DashboardFormMixin. Private.
  * products.py    — ProductForm, VariantForm.
  * customers.py   — CustomerForm, AddressForm.
  * orders.py      — RefundForm, FulfillmentForm, DraftOrderForm.
  * marketing.py   — CouponForm.
  * settings.py    — StoreGeneralForm, StoreNotificationsForm.
"""
from __future__ import annotations

# Helpers that callers (or future plugins) may reuse.
from ._helpers import (
    DashboardFormMixin,
    _ensure_html,
    _md_to_html,
    _money,
)

# Products + variants.
from .products import ProductForm, VariantForm

# Customers + addresses.
from .customers import AddressForm, CustomerForm

# Orders (refunds, fulfillments, drafts).
from .orders import DraftOrderForm, FulfillmentForm, RefundForm

# Marketing.
from .marketing import CouponForm

# Store settings.
from .settings import StoreGeneralForm, StoreNotificationsForm

__all__ = [
    # helpers
    'DashboardFormMixin',
    # products
    'ProductForm',
    'VariantForm',
    # customers
    'CustomerForm',
    'AddressForm',
    # orders
    'RefundForm',
    'FulfillmentForm',
    'DraftOrderForm',
    # marketing
    'CouponForm',
    # settings
    'StoreGeneralForm',
    'StoreNotificationsForm',
]
