"""WebMCP tools the storefront registers with the visitor's browser.

WebMCP (Chrome 149 origin trial, W3C Web Machine Learning CG) lets a page
expose tools to the agent driving the browser: ``document.modelContext
.registerTool({name, description, inputSchema, execute})``. Lighthouse's
"Agentic Browsing" category scores a page on the tools it registers and the
validity of their schemas. These three tools are the shopper's basics — find,
add, review — each backed by the store's own GraphQL endpoint, so the browser
agent uses the same cart the shopper sees.

The definitions live here, not only in the template, so a test can validate
every query against the live schema; the template renders them as JSON.
"""

from __future__ import annotations

SEARCH_QUERY = """
query WebMcpSearch($first: Int!, $search: String) {
  products(first: $first, search: $search) {
    id name slug price { amount currency } primaryImage { url } isOnSale
  }
}
"""

ADD_TO_CART_MUTATION = """
mutation WebMcpAdd($input: AddToCartInput!) {
  addToCart(input: $input) {
    cart { id itemCount subtotal { amount currency } }
    errors { code message }
  }
}
"""

CART_QUERY = """
query WebMcpCart {
  cart {
    id itemCount subtotal { amount currency }
    items { quantity totalPrice { amount currency } product { name slug } variant { name } }
  }
}
"""

TOOLS: list[dict] = [
    {
        'name': 'search_products',
        'description': 'Search this store’s catalogue by words; returns products with price and link.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'What to look for'},
                'limit': {'type': 'integer', 'minimum': 1, 'maximum': 24, 'default': 8},
            },
            'required': ['query'],
        },
        'annotations': {'readOnlyHint': True},
        'graphql': SEARCH_QUERY,
        'variables': {'first': '$limit', 'search': '$query'},
    },
    {
        'name': 'add_to_cart',
        'description': 'Add a product to the shopper’s cart by product id (from search_products).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'product_id': {'type': 'string', 'description': 'The product id'},
                'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 99, 'default': 1},
            },
            'required': ['product_id'],
        },
        'annotations': {'readOnlyHint': False, 'consequentialHint': False},
        'graphql': ADD_TO_CART_MUTATION,
        'variables': {'input': {'productId': '$product_id', 'quantity': '$quantity'}},
    },
    {
        'name': 'get_cart',
        'description': 'The shopper’s current cart: items, quantities and subtotal.',
        'inputSchema': {'type': 'object', 'properties': {}},
        'annotations': {'readOnlyHint': True},
        'graphql': CART_QUERY,
        'variables': {},
    },
]
