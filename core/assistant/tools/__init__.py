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
    orders_add_note_tool,
    orders_cancel_tool,
    orders_update_status_tool,
    products_update_price_tool,
    products_update_status_tool,
)
from core.assistant.tools.filesystem import (
    list_dir_tool,
    read_file_tool,
    search_files_tool,
)
from core.assistant.tools.logs import recent_errors_tool, search_logs_tool
from core.assistant.tools.plugins import (
    disable_plugin_tool,
    enable_plugin_tool,
    list_plugins_tool,
)
from core.assistant.tools.system import (
    disk_usage_tool,
    git_log_tool,
    server_info_tool,
)


def get_default_tools() -> list:
    return [
        # Filesystem
        read_file_tool,
        list_dir_tool,
        search_files_tool,
        # Database — generic
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
        # Configuration
        settings_list_tool,
        # Write operations — gated by confirmed=True; LLM must ask user first
        orders_update_status_tool,
        orders_cancel_tool,
        orders_add_note_tool,
        products_update_status_tool,
        products_update_price_tool,
        customers_add_note_tool,
        cms_publish_page_tool,
        cms_unpublish_page_tool,
        # Logs
        recent_errors_tool,
        search_logs_tool,
        # Plugins
        list_plugins_tool,
        enable_plugin_tool,
        disable_plugin_tool,
        # System
        server_info_tool,
        disk_usage_tool,
        git_log_tool,
        # Delegate
        list_available_agents_tool,
        invoke_agent_tool,
    ]
