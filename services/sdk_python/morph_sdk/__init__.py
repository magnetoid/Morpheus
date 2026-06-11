"""Morpheus Python SDK — agent-first commerce primitives.

Quick start:

    from morph_sdk import MorphAgentClient

    agent = MorphAgentClient(
        base_url="https://store.example.com",
        agent_token="...",
    )
    products = agent.search_products("blender under 80")
    intent = agent.propose_intent(
        kind="checkout",
        summary="Buy the Vitamix Pro for me",
        payload={"product_id": products[0]["id"], "quantity": 1},
    )
    # ... wait for customer to authorize via the merchant UI ...
    receipt = agent.poll_receipt(intent["id"])
    assert receipt.verify()  # HMAC-checked locally
"""

from morph_sdk.client import MorphAgentClient
from morph_sdk.errors import AgentBudgetError, MorphError, PermissionDeniedError
from morph_sdk.receipts import AgentReceipt, verify_receipt

__all__ = [
    'MorphAgentClient',
    'MorphError',
    'PermissionDeniedError',
    'AgentBudgetError',
    'AgentReceipt',
    'verify_receipt',
]
