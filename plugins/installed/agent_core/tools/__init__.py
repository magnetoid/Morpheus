"""Built-in tool catalog shipped by agent_core.

Each module groups tools that operate on a domain. They are registered
into `agent_registry` via `AgentCorePlugin.contribute_agent_tools()`.

The diagnostics tools (filesystem, logs, system, plugin lifecycle) are
imported from `core.assistant.tools.*` rather than re-implemented — they're
already agent-kernel compatible. This is what lets Linda delegate
"what's the disk usage?" to a sub-agent without losing capability.
"""
from __future__ import annotations

import logging

from plugins.installed.agent_core.tools.catalog import (
    archive_category_tool,
    archive_product_tool,
    backfill_alt_text_tool,
    catalog_stats_tool,
    create_category_tool,
    delete_product_tool,
    find_products_tool,
    get_product_tool,
    list_categories_tool,
    publish_digital_product_tool,
    restore_product_tool,
    update_category_tool,
    update_product_tool,
)
from plugins.installed.agent_core.tools.cart import (
    add_to_cart_tool,
    get_cart_summary_tool,
)
from plugins.installed.agent_core.tools.inventory import (
    adjust_stock_tool,
    set_stock_tool,
)
from plugins.installed.agent_core.tools.orders import (
    cancel_order_tool,
    list_recent_orders_tool,
    mark_order_fulfilled_tool,
    mark_order_refunded_tool,
    mark_order_shipped_tool,
    summarise_order_tool,
)
from plugins.installed.agent_core.tools.analytics import (
    revenue_summary_tool,
    top_products_tool,
)
from plugins.installed.agent_core.tools.content import (
    draft_product_description_tool,
)

logger = logging.getLogger('morpheus.agent_core')


def _diagnostics_tools() -> list:
    """Pull diagnostics tool objects from core.assistant.tools.*.

    Lazily imported so a broken module can't take down the agent kernel.
    Each `*_tool` is already wrapped via the @tool decorator in
    core.agents, so registry registration is straightforward.
    """
    out: list = []
    for module_path, names in (
        ('core.assistant.tools.filesystem',
            ['read_file_tool', 'list_dir_tool', 'search_files_tool']),
        ('core.assistant.tools.logs',
            ['recent_errors_tool', 'search_logs_tool']),
        ('core.assistant.tools.system',
            ['server_info_tool', 'disk_usage_tool', 'git_log_tool']),
        ('core.assistant.tools.plugins',
            ['list_plugins_tool', 'enable_plugin_tool', 'disable_plugin_tool']),
    ):
        try:
            mod = __import__(module_path, fromlist=names)
            for n in names:
                t = getattr(mod, n, None)
                if t is not None:
                    out.append(t)
        except Exception as e:  # noqa: BLE001
            logger.warning('agent_core: diagnostics import skipped for %s: %s',
                           module_path, e)
    return out


def all_builtin_tools() -> list:
    return [
        find_products_tool,
        get_product_tool,
        list_categories_tool,
        catalog_stats_tool,
        backfill_alt_text_tool,
        publish_digital_product_tool,
        update_product_tool,
        archive_product_tool,
        restore_product_tool,
        delete_product_tool,
        create_category_tool,
        update_category_tool,
        archive_category_tool,
        set_stock_tool,
        adjust_stock_tool,
        add_to_cart_tool,
        get_cart_summary_tool,
        list_recent_orders_tool,
        summarise_order_tool,
        mark_order_fulfilled_tool,
        mark_order_shipped_tool,
        cancel_order_tool,
        mark_order_refunded_tool,
        revenue_summary_tool,
        top_products_tool,
        draft_product_description_tool,
        *_diagnostics_tools(),
    ]
