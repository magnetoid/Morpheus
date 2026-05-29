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

from .home import home

from .catalog import (
    product_list,
    product_detail,
    search,
    category_detail,
    collection_detail,
    author_detail,
    staff_picks,
    categories,
    quick_search,
    # helpers re-exported for any callers that imported them via views.*
    _apply_search,
    _metafield_search_ids,
    _pdp_faqs,
    _published_reviews,
    _book_specs,
    _related_products,
)

from .cart import cart, cart_add

from .checkout import (
    checkout,
    checkout_shipping,
    checkout_review,
    checkout_payment,
    checkout_apply_gift_card,
    checkout_remove_gift_card,
)

from .account import (
    account_home,
    account_profile,
    account_orders,
    account_order_detail,
    account_order_return,
    account_addresses,
    account_address_form,
    account_address_delete,
    account_returns,
    account_return_status,
    account_credits,
    account_downloads,
    order_confirmation,
)

from .content import (
    about,
    contact,
    journal_index,
    journal_detail,
    newsletter_subscribe,
    shipping,
    returns,
    coming_soon,
)

from .vendor import vendors_directory, vendor_detail


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
    # cart / checkout
    'cart',
    'cart_add',
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
    'account_downloads',
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
