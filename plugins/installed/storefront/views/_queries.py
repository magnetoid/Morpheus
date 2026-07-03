"""Shared GraphQL query strings used by multiple storefront view modules.

Kept private (leading underscore in the filename) so this module isn't
treated as a public submodule — it's a private constant bag.
"""

from __future__ import annotations

PRODUCT_LIST_QUERY = """
query ProductList($first: Int!, $search: String, $category: String) {
  products(first: $first, search: $search, category: $category) {
    id name slug productType
    price { amount currency } priceStartsFrom
    compareAtPrice { amount }
    primaryImage { url altText }
    isOnSale discountPercentage
    averageRating
  }
}
"""

PRODUCT_DETAIL_QUERY = """
query ProductDetail($slug: String!) {
  product(slug: $slug) {
    id name slug description shortDescription productType
    price { amount currency } priceStartsFrom
    compareAtPrice { amount }
    images { url altText isPrimary sortOrder }
    variants {
      id name sku size shortDescription description
      variantType sortOrder isActive
      price { amount currency }
      compareAtPrice { amount currency }
      isOnSale discountPercentage
      imageUrl
    }
    tags category { name slug }
    collections { name slug }
    averageRating
    reviews { rating title body customer { fullName } createdAt }
  }
}
"""

CART_QUERY = """
query Cart {
  cart {
    id itemCount subtotal { amount currency }
    items {
      id quantity unitPrice { amount currency } totalPrice { amount currency }
      product { name slug primaryImage { url } }
      variant { name sku }
    }
    coupon { code discountType discountValue }
    giftCard { code balance currency }
  }
}
"""

# Real money math for the summary rows — the same breakdown order finalize
# uses (promotions + coupon + gift card + shipping + tax), NOT a template-side
# re-computation. Fetched alongside CART_QUERY wherever a summary renders.
CART_TOTALS_QUERY = """
query CartTotals($cartId: ID!) {
  cartTotals(cartId: $cartId) {
    subtotal { amount currency }
    discount { amount currency }
    shipping { amount currency }
    tax { amount currency }
    total { amount currency }
  }
}
"""
