"""Built-in Assistant tools.

These are NOT contributed by plugins. They live in core so the Assistant
keeps working when the plugin layer is degraded.

Each tool wraps a single capability the Assistant can use to inspect or
operate the platform. Tools follow the same `Tool` shape as the agent
kernel so the runtime treats them uniformly.
"""
from __future__ import annotations

from core.assistant.tools.database import (
    count_rows_tool,
    list_models_tool,
    recent_orders_tool,
)
from core.assistant.tools.delegate import (
    invoke_agent_tool,
    list_available_agents_tool,
)
from core.assistant.tools.ecommerce import (
    analytics_summary_tool,
    analytics_top_products_tool,
    cms_pages_tool,
    customers_get_tool,
    customers_search_tool,
    db_describe_model_tool,
    email_templates_tool,
    markets_list_tool,
    media_search_tool,
    metafields_list_for_tool,
    orders_get_tool,
    orders_search_tool,
    products_get_tool,
    products_search_tool,
    settings_list_tool,
)
from core.assistant.tools.ecommerce_writes import (
    cms_publish_page_tool,
    cms_unpublish_page_tool,
    customers_add_note_tool,
    metafields_delete_tool,
    metafields_set_tool,
    orders_add_note_tool,
    orders_cancel_tool,
    orders_update_status_tool,
    products_update_price_tool,
    products_update_status_tool,
)


def get_default_tools() -> list:
    """Linda's primary tool catalog — commerce + content + memory + delegate.

    The diagnostics tools (filesystem, logs, system, plugin lifecycle) are
    intentionally NOT here — they live behind ``delegate.invoke_agent(
    'diagnostics', ...)`` so Linda's selection space stays small. See
    plugins/installed/agent_core/agents/diagnostics.py.
    """
    # Local import — keeps `memory.py` lazy so failed imports don't break
    # tool resolution at construct time.
    from core.assistant.tools.memory import (
        memory_forget_tool,
        memory_recall_tool,
        memory_remember_tool,
    )
    from core.assistant.tools.navigation import dashboard_navigate_tool
    return [
        # Database — schema introspection
        list_models_tool,
        count_rows_tool,
        db_describe_model_tool,
        # Ecommerce — orders / products / customers
        orders_search_tool,
        orders_get_tool,
        recent_orders_tool,
        products_search_tool,
        products_get_tool,
        customers_search_tool,
        customers_get_tool,
        # Analytics
        analytics_summary_tool,
        analytics_top_products_tool,
        # Content
        cms_pages_tool,
        email_templates_tool,
        media_search_tool,
        # Metafields — schema-less custom data
        metafields_list_for_tool,
        # Configuration
        settings_list_tool,
        markets_list_tool,
        # Memory — cross-session preferences
        memory_recall_tool,
        memory_remember_tool,
        memory_forget_tool,
        # Write operations — gated by confirmed=True; LLM must ask user first
        orders_update_status_tool,
        orders_cancel_tool,
        orders_add_note_tool,
        products_update_status_tool,
        products_update_price_tool,
        customers_add_note_tool,
        cms_publish_page_tool,
        cms_unpublish_page_tool,
        metafields_set_tool,
        metafields_delete_tool,
        # Navigation — surface dashboard deep-links as click-through chips.
        dashboard_navigate_tool,
        # Delegate — diagnostics, content writer, pricing, merchant ops, etc.
        list_available_agents_tool,
        invoke_agent_tool,
    ]
