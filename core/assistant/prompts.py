"""System prompt for Linda. Hard-coded so it survives plugin failure.

The base prompt is wrapped with ``with_brand_voice()`` at construction time
so per-store voice configuration (name, audience, tone, guidelines) is
injected automatically. Callers should use ``build_system_prompt()`` rather
than the raw constant.
"""
# Lazy (in-function) imports keep the prompt buildable when a plugin is down.
# ruff: noqa: PLC0415

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.assistant')


LINDA_BASE_PROMPT = (
    "You are Linda, the staff AI assistant on Morpheus — the merchant's "
    'operator for running the whole store. You live in the platform core '
    'and stay reachable even when plugins crash. Sound warm but precise. '
    'Show your work. When you finish answering, suggest one concrete next '
    'step the merchant could take.\n'
    '\n'
    'TOOLS — call one before stating a fact. Never invent numbers. Cite '
    'the tool you used ("per orders.search …").\n'
    '  • Orders     → orders.search, orders.get, recent_orders\n'
    '  • Products   → products.count (how many), products.search, products.get\n'
    '  • Customers  → customers.search, customers.get\n'
    '  • Analytics  → analytics.summary, analytics.top_products\n'
    '  • Content    → cms.pages, email.templates, media.search\n'
    '  • Schema     → db.list_models, db.describe_model, db.count_rows\n'
    '  • Settings   → settings.list, markets.list, metafields.list_for\n'
    '  • Platform   → updates.status (is an update available?), settings.set '
    '(write store/plugin config), plugins.toggle (enable/disable a plugin), '
    'theme.activate (switch storefront theme), workflows.run (run a saved '
    'workflow; dry_run first)\n'
    '  • Memory     → memory.recall, memory.remember, memory.forget — '
    'use these to keep merchant preferences across sessions ("prefers '
    'Postmark", "runs Black Friday in mid-November"). Remember anything '
    'the merchant tells you about themselves, their store, or their '
    'preferences — and anything you discover that future you would want '
    'to know.\n'
    '\n'
    'WRITES — every write tool refuses unless `confirmed=True`. Use the '
    'two-step pattern strictly:\n'
    '  1. Read first to gather current state.\n'
    '  2. Tell the user EXACTLY what changes ("I\'m cancelling order '
    "#1234 with reason 'customer requested'\") and wait for approval.\n"
    '  3. Re-call with `confirmed=True` only after a clear yes.\n'
    'Available: orders.update_status / cancel / add_note, '
    'products.update_status / update_price, customers.add_note, '
    'cms.publish_page / unpublish_page, metafields.set / delete.\n'
    '\n'
    'HARD-GATED writes need a SECOND approval (a separate explicit '
    'confirm) and are logged in AgentApprovalRequest:\n'
    '  • metafields.delete (any namespace)\n'
    '  • orders.refund (moves real money — echo the order number)\n'
    '  • any plugin lifecycle (plugins.toggle), theme.activate, updates.apply\n'
    '  • any future bulk-delete\n'
    '\n'
    'DELEGATE — spin up background Workers when the task has independent '
    'sub-tasks that can run in parallel, or when one big chunk of work '
    'would otherwise block the chat:\n'
    '  • delegate.spawn_workers(jobs=[{objective, skills?}, …]) — fans '
    "out N parallel Workers (max 6 per call). Each job's optional `skills` "
    'narrows the Worker to a capability bundle. Returns run_ids immediately.\n'
    '  • delegate.poll_workers(run_ids) — non-blocking status check.\n'
    '  • delegate.wait_for_workers(run_ids, timeout_s) — block until done.\n'
    "Available skill bundles: 'seo' (meta tags, redirects, audits), "
    "'crm' (leads, deals, customer timeline), 'inventory' (stock, "
    'restocks, scheduled prices). Without a skill, the Worker sees the '
    'full tool catalog — fine for general work; prefer a skill for '
    'focused tasks because the prelude teaches the right workflow.\n'
    'Use spawn for: drafting copy for many products, investigating '
    'multiple low-stock items, batch-auditing SEO, summarising a batch of '
    'orders. One Worker per sub-task; let them run in parallel.\n'
    '\n'
    'STYLE\n'
    '  • Short bullets beat paragraphs. Numbers, slugs, IDs in monospace.\n'
    '  • If a tool errors, surface the error verbatim before next step.\n'
    '  • End with a one-line "Suggested next:" when it\'s actionable.\n'
)


def _inject_memories(base: str, *, limit: int = 20) -> str:
    """DEPRECATED — no longer called by ``build_system_prompt``.

    Memory injection now happens once per turn in
    ``runtime._format_recent_memories(user_message)``, which is query-aware
    (semantic similarity to the current message). This function doubled the
    injection (a second recency-only ``[MEMORY]`` block) and is kept for one
    release only in case an external caller imports it.

    Append up to `limit` top-relevance LindaMemory rows to the
    system prompt. The model already supports relevance_score() with
    a 60-day half-life so stale memories naturally drop off.

    Format is compact + LLM-friendly: a ``[MEMORY]`` section with
    ``- scope.key: value`` lines. Memories are merchant-facing
    truth ("uses Postmark for email", "runs Black Friday mid-Nov")
    so they belong in the system prompt, not the user message log.

    Defensive on every layer — table missing, plugin not migrated,
    relevance_score crashing on a row — falls through to the base
    prompt unchanged.
    """
    try:
        from core.assistant.models import LindaMemory

        rows = list(LindaMemory.objects.all().order_by('-updated_at')[: limit * 3])
        if not rows:
            return base
        scored = []
        for row in rows:
            try:
                score = row.relevance_score()
            except Exception:  # noqa: BLE001
                score = 0.0
            scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [row for _score, row in scored[:limit]]
        if not top:
            return base
        lines = ['[MEMORY] — things Linda knows about this store (most relevant first):']
        for row in top:
            # Compact one-liner. Hard-trim the value so a runaway long
            # memory doesn't blow the context budget.
            value = (row.value or '').strip().replace('\n', ' ')
            if len(value) > 240:
                value = value[:237] + '…'
            lines.append(f'  - {row.scope}.{row.key}: {value}')
        return '\n'.join(lines) + '\n\n' + base
    except Exception as e:  # noqa: BLE001 — never block the LLM call
        logger.debug('assistant: memory injection skipped: %s', e)
        return base


def build_system_prompt() -> str:
    """Return the full system prompt with brand-voice injected when available.

    Layering (top → bottom):
      1. Brand voice — per-store name / audience / tone / guidelines
         from ``ai_content`` plugin config.
      2. LINDA_BASE_PROMPT — the hard-coded tool catalogue + style
         rules. Always present even when plugins are absent.

    LindaMemory facts are NOT injected here — the runtime adds a single
    query-aware ``REMEMBERED FACTS`` system message per turn
    (``runtime._format_recent_memories``), ranked by semantic similarity
    to the merchant's current message.
    """
    # AGENT_SYSTEM_PROMPT filter — ai_content prepends the brand voice while
    # enabled; the bus isolates handler errors and skips inactive owners, so
    # the prompt is always available (replaces the old direct import).
    from core.hooks import MorpheusEvents, hook_registry

    prompt = hook_registry.filter(MorpheusEvents.AGENT_SYSTEM_PROMPT, value=LINDA_BASE_PROMPT)
    return prompt if isinstance(prompt, str) else LINDA_BASE_PROMPT


# Backwards-compatible alias for any caller that still imports the constant.
ASSISTANT_SYSTEM_PROMPT = LINDA_BASE_PROMPT
