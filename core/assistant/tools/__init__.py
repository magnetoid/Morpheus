"""Built-in Assistant tools.

These are NOT contributed by plugins. They live in core so the Assistant
keeps working when the plugin layer is degraded.

Each tool wraps a single capability the Assistant can use to inspect or
operate the platform. Tools follow the same `Tool` shape as the agent
kernel so the runtime treats them uniformly.
"""
# Lazy (in-function) imports keep tool resolution working when a sub-module
# fails to import — the established pattern in this package.
# ruff: noqa: PLC0415

from __future__ import annotations

from core.assistant.tools.capabilities import capabilities_tool, plugins_describe_tool
from core.assistant.tools.database import (
    count_rows_tool,
    list_models_tool,
)
from core.assistant.tools.delegate import (
    invoke_agent_tool,
    list_available_agents_tool,
)
from core.assistant.tools.ecommerce import (
    db_describe_model_tool,
    settings_list_tool,
)
from core.assistant.tools.ecommerce_writes import (
    customers_add_note_tool,
    products_update_price_tool,
    products_update_status_tool,
)
from core.assistant.tools.spawn import (
    poll_workers_tool,
    spawn_workers_tool,
    wait_for_workers_tool,
)


def get_default_tools() -> list:
    """Linda's primary tool catalog — commerce + content + memory + delegate.

    Post-pivot (2026-05-23): the diagnostics / merchant_ops / pricing /
    content_writer / concierge sub-agents have been collapsed into a single
    generic ``worker``. Linda fans out N workers in parallel via
    ``delegate.spawn_workers`` and collects results via
    ``delegate.poll_workers`` / ``delegate.wait_for_workers``.
    """
    # Local import — keeps `memory.py` lazy so failed imports don't break
    # tool resolution at construct time.
    from core.assistant.tools.admin_ops import (
        plugins_toggle_tool,
        settings_set_tool,
        theme_activate_tool,
        updates_apply_tool,
        updates_status_tool,
    )
    from core.assistant.tools.code import (
        code_apply_proposal_tool,
        code_draft_tool,
        code_evaluate_proposal_tool,
        code_list_proposals_tool,
        run_python_tool,
    )
    from core.assistant.tools.health import platform_circuit_breakers_tool
    from core.assistant.tools.memory import (
        memory_forget_tool,
        memory_recall_tool,
        memory_remember_tool,
    )
    from core.assistant.tools.navigation import dashboard_navigate_tool
    from core.assistant.tools.skills import (
        skills_distill_tool,
        skills_list_tool,
        skills_record_outcome_tool,
    )

    tools = [
        # Database — schema introspection
        list_models_tool,
        count_rows_tool,
        db_describe_model_tool,
        # (orders read/write tools migrated to the orders plugin; sourced by
        # name from the registry via _migrated_names below.)
        # Configuration
        settings_list_tool,
        # Memory — cross-session preferences
        memory_recall_tool,
        memory_remember_tool,
        memory_forget_tool,
        # Self-learning — distill, review, and score reusable skills.
        skills_distill_tool,
        skills_list_tool,
        skills_record_outcome_tool,
        # Code — compose tools in a sandboxed Python script (read/safe tools only).
        run_python_tool,
        # Self-development — draft a NEW tool's source (scanned; review-only, not live),
        # multi-model consensus review, and proposal listing. Linda-only (selfdev scope).
        code_draft_tool,
        code_evaluate_proposal_tool,
        code_list_proposals_tool,
        # Phase 4 apply (ADR 0014) — owner-approved proposal → code on a branch.
        # DORMANT: inert unless MORPHEUS_SELF_UPDATE_ENABLED + owner approval.
        code_apply_proposal_tool,
        # Write operations — gated by confirmed=True; LLM must ask user first.
        # (orders write tools migrated to the orders plugin — registry-sourced
        # via _migrated_names below.)
        products_update_status_tool,
        products_update_price_tool,
        customers_add_note_tool,
        # Self-awareness — enumerate the full toolset so Linda discovers her
        # own reach instead of replying "I can't"; introspect any installed
        # plugin (manifest + models + commands + code path) to learn it.
        capabilities_tool,
        plugins_describe_tool,
        # Navigation — surface dashboard deep-links as click-through chips.
        dashboard_navigate_tool,
        # Platform health — circuit breakers, dependency state, "is X down".
        platform_circuit_breakers_tool,
        # Platform ops — self-update + store config + plugin toggles (gated).
        updates_status_tool,
        updates_apply_tool,
        settings_set_tool,
        plugins_toggle_tool,
        theme_activate_tool,
        # Delegate — fan out N parallel Workers, then collect their results.
        # spawn_workers_tool is the primary path; invoke_agent_tool is a
        # back-compat shim that wraps spawn + wait_for.
        list_available_agents_tool,
        spawn_workers_tool,
        poll_workers_tool,
        wait_for_workers_tool,
        invoke_agent_tool,
    ]

    # Tools migrated out of core into their owning plugins (D3): sourced by name
    # from the agent registry so the query layer lives in the plugin while
    # Linda's curated catalogue keeps the exact same tool names. A name that
    # isn't registered (plugin disabled) is simply skipped — disabling the
    # owning plugin correctly removes the tool from Linda.
    from core.agents import agent_registry

    _migrated_names = [
        'orders.search',
        'orders.get',
        'orders.update_status',
        'orders.cancel',
        'orders.add_note',
        'orders.refund',
        'products.search',
        'products.get',
        'customers.search',
        'customers.get',
        'media.search',
        'metafields.list_for',
        'metafields.set',
        'metafields.delete',
        'markets.list',
        'analytics.summary',
        'analytics.top_products',
        'cms.pages',
        'cms.publish_page',
        'cms.unpublish_page',
        'email.templates',
        'workflows.run',
    ]
    tools += [t for t in (agent_registry.get_tool(n) for n in _migrated_names) if t is not None]
    return tools
