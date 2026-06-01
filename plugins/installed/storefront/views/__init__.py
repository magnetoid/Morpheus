"""Storefront views — split from a 2098-line monolith into focused
submodules. Every public view is re-exported here so the URL conf
(``plugins.installed.storefront.urls``) keeps working unchanged.

Layout:
  _queries.py    — shared GraphQL query string constants
  home.py        — home()
  catalog.py     — product_list / product_detail / search / category_detail /
                   author_detail / staff_picks / categories / quick_search
                   plus PDP helpers (_pdp_faqs, _published_reviews,
                   _book_specs, _related_products) and hybrid search
                   helpers (_apply_search, _metafield_search_ids)
  cart.py        — cart / cart_add
  checkout.py    — checkout / checkout_shipping / checkout_review /
                   checkout_payment + gift-card side trips
  account.py     — account_home / account_profile / account_orders /
                   account_order_detail / account_order_return /
                   account_addresses / account_address_form /
                   account_address_delete / account_returns /
                   account_return_status / account_credits /
                   account_downloads / order_confirmation
  content.py     — about / contact / journal_index / journal_detail /
                   newsletter_subscribe / shipping / returns / coming_soon
  vendor.py      — vendors_directory / vendor_detail
"""

from __future__ import annotations

from .account import (
    account_address_delete,
    account_address_form,
    account_addresses,
    account_credits,
    account_downloads,
    account_home,
    account_order_detail,
    account_order_return,
    account_orders,
    account_payment_methods,
    account_points,
    account_profile,
    account_return_status,
    account_returns,
    order_confirmation,
)
from .cart import cart, cart_add, cart_remove
from .catalog import (
    # helpers re-exported for any callers that imported them via views.*
    _apply_search,
    _book_specs,
    _metafield_search_ids,
    _pdp_faqs,
    _published_reviews,
    _related_products,
    author_detail,
    categories,
    category_detail,
    collection_detail,
    product_detail,
    product_list,
    quick_search,
    search,
    staff_picks,
)
from .checkout import (
    checkout,
    checkout_apply_gift_card,
    checkout_payment,
    checkout_remove_gift_card,
    checkout_review,
    checkout_shipping,
)
from .checkout_one_page import checkout_one_page as checkout_one_page
from .content import (
    about,
    coming_soon,
    contact,
    journal_detail,
    journal_index,
    newsletter_subscribe,
    returns,
    shipping,
)
from .home import home
from .vendor import vendor_detail, vendors_directory

__all__ = [
    # home
    'home',
    # catalog
    'product_list',
    'product_detail',
    'search',
    'category_detail',
    'collection_detail',
    'author_detail',
    'staff_picks',
    'categories',
    'quick_search',
    # catalog helpers (re-exported for callers using views.*)
    '_apply_search',
    '_metafield_search_ids',
    '_pdp_faqs',
    '_published_reviews',
    '_book_specs',
    '_related_products',
    # cart / checkout
    'cart',
    'cart_add',
    'cart_remove',
    'checkout',
    'checkout_shipping',
    'checkout_review',
    'checkout_payment',
    'checkout_apply_gift_card',
    'checkout_remove_gift_card',
    # account
    'account_home',
    'account_profile',
    'account_orders',
    'account_order_detail',
    'account_order_return',
    'account_addresses',
    'account_address_form',
    'account_address_delete',
    'account_returns',
    'account_return_status',
    'account_credits',
    'account_points',
    'account_downloads',
    'account_payment_methods',
    'order_confirmation',
    # content / vendor
    'about',
    'contact',
    'journal_index',
    'journal_detail',
    'newsletter_subscribe',
    'shipping',
    'returns',
    'coming_soon',
    'vendors_directory',
    'vendor_detail',
]
