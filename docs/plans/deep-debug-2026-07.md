# Deep-debug sweep — 2026-07-19

Source: an 8-area adversarial bug-hunt (32 agents, find → refute) over the core
kernel + recently-shipped plugins. **22 bugs survived verification.** Each was
re-read against source with a concrete failure scenario. This doc is the triage
register: what ships in the deep-debug batch vs. what's deferred (with reasons).

Companion: `docs/analysis/core_codebase_audit_2026-07.md` (the earlier core
audit; S3/H3 overlap and are folded in here).

## Fix-now batch (this deploy)

| # | Sev | Area | Bug | Fix |
|---|---|---|---|---|
| 1 | High | otel | `PIIScrubberProcessor.on_end` calls `set_attribute` on a `ReadableSpan` (no such method → `AttributeError` swallowed) → PII exported unscrubbed | Mutate `span._attributes` in place via testable `scrub_span_attributes()` helper |
| 2 | High | self-improv | `error_log` watermark counts its own in-progress `SiIngestJob` (`status='ok'` written before `run()`) → since = now−10min every run → drops ~83% of errors | `_last_successful_run()` filters `finished_at__isnull=False` |
| 5 | High | agent-authz | `context['staged']` skips the ENTIRE approval gate for ALL tools, but only ecommerce_writes implement staging → `catalog.delete_product`/`orders.cancel`/`mark_refunded` run with zero approval | Scope exemption to tools that declare `supports_staging`; others still hit `approval_registry.check()` |
| 3 | High | money | gift-card redeem debits at checkout but nothing re-credits on ORDER_CANCELLED / PAYMENT_REFUNDED (loyalty reverses; gift_cards doesn't) | gift_cards subscribes ORDER_CANCELLED + PAYMENT_REFUNDED → idempotent `kind='refund'` re-credit |
| 4 | High | money | `_compute_refund` sums pre-discount list price, ignores `Order.discount_total` → store credit over-issued; money refund blocked by ceiling | Clamp refundable to `order.total − already_refunded`; apply ceiling to the store-credit branch too |
| 9+19 | Med/Low | email | `send_campaign` dedupe/`recipient_count` include `ok=False` and `kind='test'` rows → failed recipients unretryable; test send suppresses a real subscriber; count inflated | Filter `kind='campaign', ok=True` on both queries |
| 10 | Med | email | newsletter `confirm()` guards only `!= 'confirmed'` → a stale confirm link resurrects an `unsubscribed` (terminal) subscriber | Refuse to re-confirm `unsubscribed`; only `pending` → `confirmed` |
| 12 | Med | hooks | `PluginRegistry.__init__` unconditionally rebinds the global `hook_registry` active-check → a 2nd instance gates every plugin handler off (test-isolation footgun) | Only the canonical singleton wires `set_active_check` |
| 14 | Med | hooks | `contribute_skills()` registered on enable, never dropped on disable → skills (and their tools) leak past a plugin disable | `_drop_contributions` unregisters the plugin's skills |
| 15+22 | Med/Low | agent-authz | `fs.search_files` ignores `is_path_protected` (secret-content oracle over `.env`); `fs.read_file` protected check is case-sensitive on a case-insensitive FS | Filter protected paths from search results + grep excludes; case-fold the read_file check |
| 16 | Low | agents | orphaned `AgentRun` rows stuck `state='running'` after a deploy/OOM kill — no reaper | New `sweep_stuck_runs` beat task (every 5min, >15min old, excludes `awaiting_approval`) |
| 17 | Low | agents | `llm.py` timeout comment says gunicorn 30s (really 60s); fallback router has no aggregate deadline → 4×20s stacking | Fix comment; add `LLM_FALLBACK_BUDGET_SECS=50` cascade budget |
| 21 | Low | agent-authz | `_require_hard_gate` writes `AgentApprovalRequest.objects.create(agent_name=…, payload=…)` — fields don't exist → always raises, swallowed → destructive-op audit row never written | Route the audit write to the real fields / `record_ai_decision` and stop swallowing silently |
| — | Low | agents | embeddings client built with SDK default 600s timeout + 2 retries on the request path | `OpenAI(timeout=10, max_retries=0)` |

## Deferred (own focused PR — reason)

> **Update (v0.26.1):** #13 (register_urls disable-safety) and #18 (auto-heal
> failure backoff) are now **FIXED + tested**. Still open: #6, #7, #8, #11, #20.
> The two money-math items (#7 breakdown priority, #8 refund idempotency) are
> deliberately held for a dedicated money-tested session.

| # | Sev | Bug | Why deferred |
|---|---|---|---|
| 6 | Med | Post-timeout daemon thread keeps executing write-tools + AgentStep writes after the run is reported `failed` | Needs a cooperative deadline threaded through the runtime loop (check before each `respond()`/`invoke()`); invasive. The #16 sweeper reaps the stuck row but not the zombie writes. |
| 7 | Med | Gift-card/loyalty tender applied at breakdown priority 10/15, before tax(20)/shipping(30) → under-applies, customer overpays | A gift card is a *tender*, not a discount — the correct fix moves it after tax/shipping, which touches the tax base. Deserves its own money-tested PR. |
| 8 | Med | `RefundService.process` dedups on (order, amount, reason) → a genuine 2nd equal-value refund silently moves no money | Proper fix = caller-supplied idempotency token threaded through returns/agent/admin callers; behavior change. |
| 11 | Med | Cart-recovery drip is consent-gated marketing but ships no List-Unsubscribe header/footer | Needs a per-cart unsubscribe token + template footer + suppression wiring. |
| 13 | Med | `register_urls` routes never unmounted on `deactivate()` → a disabled plugin's endpoints keep serving (fails disable litmus) | Needs owner-tagged `_plugin_urls` + urlconf rebuild on deactivate; load-bearing URL layer, wants the disable-test guard. Boundary-debt category. |
| 18 | Low | Auto-heal failures re-proposed every analyzer run, no backoff → unbounded SiRecommendation/SiActionLog growth | Add consecutive-failure cooldown suppression; moderate. |
| 20 | Low | `send_campaign` no chunking/throttle → large list hits 600s hard limit, wedged at `sending` | Chunk + re-enqueue continuation; larger rework. |

## Verify
`DATABASE_URL='sqlite:///:memory:' python manage.py test` the touched plugins +
`core`, ruff on changed files, one version bump (PATCH — bugfix batch), deploy-smoke.
