# Morpheus OS — Core Codebase Deep Audit

> **Date:** 2026-07-18
> **Scope:** The `core/` kernel — all 278 Python files, 22,196 LOC (non-test), 5,807 test LOC across 48 test files. Plugin-level findings are covered in the companion reports ([enterprise_benchmark_gap_report_2026.md](enterprise_benchmark_gap_report_2026.md), [comprehensive_application_audit_2026-07.md](comprehensive_application_audit_2026-07.md)) and cross-referenced here only where core is the cause.
> **Method:** Three parallel module-group deep reviews (every finding verified against source with `file:line` evidence), plus direct evidence collection: `ruff check core/` (0 findings), `python3 manage.py check` (0 issues), LOC/test/debt metrics.

---

## Executive Summary

The core kernel is **well-architected and mostly well-built** — ruff-clean, boot-check-clean, only 1 TODO/FIXME in 22K LOC, and several genuinely excellent files (`core/safety.py`, `core/hooks.py`, `core/emails/`, `core/updates.py`). The dominant pattern in the findings is not sloppy code; it is **guarantees promised but not enforced**:

1. **Gating that exists only as model behavior.** The agent layer's approval and confirmation gates are enforced at the MCP HTTP edge but are fail-open in every in-process runtime; write confirmations are LLM-supplied parameters, not human approvals.
2. **Docstrings claiming guarantees the code doesn't deliver.** The OTel PII scrubber is a no-op, the circuit breaker has no Redis state despite documenting it, the audit log is mutable despite "immutable" framing, the token budget is documented but unread.
3. **Silently dead pipelines in the self-improvement loop.** Four links (heal-loop terminal state, zero-search collector, error-log collector, rejection suppression) are broken end-to-end — the "immune system" is running on roughly half its sensors.
4. **Timeout arithmetic that doesn't close.** In-request waits (up to 300s) and worst-case LLM latency (~121s) exceed the 30s gunicorn worker budget, turning safety nets into reliability bugs and leaving stuck `AgentRun` rows.

### Health Scorecard

| Dimension | Grade | Evidence |
|---|---|---|
| Lint / standards | **A** | `ruff check core/` — 0 findings |
| Boot health | **A** | `manage.py check` — 0 issues |
| Maintainability | **B** | 3 files >600 LOC; two runtimes drifting; 184 broad `except Exception` |
| Security posture | **C+** | Strong perimeter (OTP design, CSP, API keys); fail-open agent gates, no-op PII scrubber, OTP per-IP gap |
| Performance hygiene | **B-** | Good patterns in emails/hooks; per-request serialization cost, N+1s, sync collector writes |
| Scalability | **C+** | Worker-timeout mismatch, per-process circuit breakers, unbounded tables |
| Test coverage | **B-** | 5,807 test LOC (~26%), strong contract suites; **zero tests for the OTP flow** |

### Top 10 Findings (details inside)

| # | Severity | Finding |
|---|---|---|
| 1 | **Critical** | Agent approval gate is fail-open in-process; write confirmation is model-behavior only |
| 2 | **Critical** | Self-improvement heal loop never terminates — auto-applied recs re-execute forever or flip to false-failed |
| 3 | **Critical** | OTel `PIIScrubberProcessor` is a silent no-op — PII exported unscrubbed |
| 4 | **Critical** | Zero-search, error-log collectors and rejection suppression are 100% dead (wrong kwargs, retired table, vocabulary mismatch) |
| 5 | **High** | OTP issuance has no per-IP throttle and the rate-limit rule misses `/auth/otp/` — email-bombing relay |
| 6 | **High** | Assistant runtime enforces no scopes; client-controlled mode maps to full access for any staff user |
| 7 | **High** | `fs.read_file` can exfiltrate `.env`; `plugins.disable` bypasses `PROTECTED_PLUGINS`; `OpsProposal.apply()` can setattr `is_superuser` |
| 8 | **High** | In-request waits (300s) and LLM worst-case (~121s) exceed the 30s worker timeout — SIGKILL mid-turn, stuck runs |
| 9 | **High** | `is_customization_safe` and confidence are LLM-controlled — prompt-injection can steer auto-apply |
| 10 | **High** | Safety path matcher bypassable via un-normalized paths (`plugins/installed/x/../payments/y.py`) |

---

## Task 1 — Full Code Review of Core Modules

### 1.1 Module-by-module assessment

| Module | LOC | Verdict | Key issues |
|---|---|---|---|
| `core/agents/llm.py` | 865 | Good, oversized | Worst-case latency math exceeds worker budget; Gemini key in URL query string; global 1h response cache shared across users |
| `core/agents/runtime.py` | 455 | Good, one hole | Approval gate skipped when `approval_check=None` — and no production caller passes one ([runtime.py:269-272](file:///Users/magnetoid/coding/morph/core/agents/runtime.py#L269-L272)) |
| `core/agents/sandbox.py` | 184 | Good, documented limits | Cannot preempt C-level loops, no memory ceiling (honestly documented); treat as DoS-only containment |
| `core/agents/compaction.py` | ~120 | Excellent | Preserves assistant→tool-call pair integrity; subtle bug class already fixed |
| `core/assistant/runtime.py` | 782 | Oversized, drifting | Duplicates the agents-runtime dispatch loop, summarizer, compaction, and error humanizer (`_humanise_provider_error` vs `_friendly_provider_error` near-copies); enforces **no scopes** |
| `core/assistant/tools/ecommerce_writes.py` | 614 | Risky | `confirmed=True`/`hard_gate_ack=YES` are model-supplied parameters — any injected text can pre-confirm refunds/cancels |
| `core/assistant/tools/filesystem.py` | ~150 | One hole | `_safe_path` confines to project root but never consults `PROTECTED_PATHS` — `.env`, `id_rsa`, `*.pem` readable ([filesystem.py:46-116](file:///Users/magnetoid/coding/morph/core/assistant/tools/filesystem.py#L46-L116)) |
| `core/assistant/tools/spawn.py` | 431 | Timeout mismatch | `wait_for_workers` sleeps up to 300s in-request; daemon-thread runs die with SIGKILLed workers leaving `state='running'` forever |
| `core/assistant/tools/database.py` | ~120 | N+1s | `recent_orders` missing `select_related('customer')`; `list_models` runs one `COUNT(*)` per model per call |
| `core/assistant/tools/admin_ops.py` | 275 | Gaps | `plugins.disable` bypasses `PROTECTED_PLUGINS`; `settings.set` writes arbitrary keys incl. secrets → persisted into transcripts; `orders.refund` accepts negative amounts |
| `core/assistant/models.py` | 477 | One hole | `OpsProposal.apply()` is a generic `setattr` writer on any ContentType-resolved model — `auth.user.is_superuser` reachable; no per-kind field allowlist; callable from `proposed` status ([models.py:401-477](file:///Users/magnetoid/coding/morph/core/assistant/models.py#L401-L477)) |
| `core/hooks.py` | 740 | **Excellent** | Handler isolation, fail-closed filter mode with dedicated test, on-commit webhook enqueue, disable-gating, best-documented event catalog in the repo. One cost issue: `_serialize_payload` runs on every `fire()` even with zero webhooks/NATS |
| `core/audit/` | ~170 | Weakest link vs. claims | Mutable rows despite "immutable" framing; `record()` "never raises" is false for non-JSON-serializable metadata |
| `core/observability.py` | ~110 | One critical bug | `PIIScrubberProcessor.on_end` calls `span.set_attribute` on an ended span → no-op with pinned SDK; PII exports unscrubbed |
| `core/sentry.py` | ~90 | Good, one gap | Scrubbing misses `event['breadcrumbs']` and `event['contexts']` despite the comment claiming it |
| `core/auth/` | ~300 | Strong design, 4 gaps | Per-email lockout, SHA-256 codes, no enumeration — but: no per-IP issue throttle, non-atomic consume (replay race), Redis outage 500s the login page, **zero tests** |
| `core/ratelimit.py` + `core/utils/rate_limit.py` + `api/rate_limit.py` | ~250 | Divergent trio | Three limiters with different IP resolution and failure policies (fail-open vs 500-on-Redis-outage); `api/rate_limit.py` buckets by first 20 chars of **unvalidated** Bearer token — spoofed header gets the 600/min tier |
| `core/circuit_breaker.py` | 240 | Doc drift | Documents Redis-shared state — implementation is in-memory only; no single-probe gating (thundering herd after cooldown); effective threshold is N×workers |
| `core/db_router.py` | 39 | Loaded gun | No read-after-write pinning; stale reads under lag once a replica is configured; docstring promises random replica selection that doesn't exist |
| `core/money.py` | 172 | Good, one flaw | Hard-coded 2-decimal `CENTS` — wrong for JPY (0) and KWD (3) on a multi-currency platform |
| `core/safety.py` | 296 | **Excellent, two gaps** | Best file in the kernel (allowlist-first, symlink tests, contract suite) — but path matcher doesn't normalize (`./`, `..`, `//` evasions) and enforcement files (`scripts/`, `.github/`, `requirements.txt`) are outside the boundary |
| `core/self_improvement/` | ~2,500 | Strong skeleton, 4 dead links | See §1.3 — heal loop never terminates, 2 collectors dead, suppression no-op, LLM-controlled safety flags |
| `core/emails/` | ~330 | **Excellent** | render-in-request/send-on-commit topology, bounded retries, autoescaped templates, redacted logs. Minor: permanent failures retried 3× |
| `core/i18n/` | ~300 | Good, N+1 by design | `trans` filter = 1 query per object per field; `fr-CA` vs `fr` write/read mismatch makes stored rows unreachable |
| `core/workflows.py` | 308 | Good | `skipped` state never assigned; failed compensation can report `compensated`; MRO step order contradicts docstring |
| `core/updates.py` | 307 | **Excellent** | Dry-run default, ff-only, boot-probe in fresh interpreter, dependency-manifest guard, honest rollback semantics |
| `core/errors/` | ~330 | Good, write-amplifying | One INSERT per exception under error storms; fingerprint includes line number → new groups every deploy; middleware-internal exceptions invisible |
| `core/management/commands/morph_bench.py` | 279 | Useful, inaccurate | Measures TTFB+1KB not total time; fresh TCP+TLS per request; `--regression-pct 0` silently becomes 15; missing baseline ignored |

### 1.2 Standards and tech-debt metrics (measured)

| Metric | Value | Assessment |
|---|---|---|
| Ruff findings in `core/` | **0** | Clean |
| Django system check | **0 issues** | Clean |
| TODO/FIXME/HACK markers | **1** | Negligible |
| Broad `except Exception` (non-test) | **184** | High — mostly deliberate fail-soft, but hides regressions; the riskiest are in gate/enforcement paths |
| Silent `pass` after except | **23** | Acceptable count; 2 confirmed harmful (i18n tool registration vanishes silently) |
| Files >600 LOC | 3 (`llm.py`, `assistant/runtime.py`, `hooks.py`) | `hooks.py` earns its size; the two runtimes should converge, not shrink |
| Test ratio | 5,807 / 22,196 LOC (~26%) | Reasonable, but misallocated — OTP front door has zero tests |
| Docstring-vs-code drift incidents | **12 confirmed** | The single most frequent defect class in this audit |

### 1.3 The self-improvement loop — 4 silently dead links (Critical)

The "immune system" is architecturally sound but operationally degraded. Each break is silent — no errors, just absent behavior:

1. **Heal loop never terminates** ([heal.py:137-139](file:///Users/magnetoid/coding/morph/core/self_improvement/heal.py#L137-L139)). On success, status stays `auto_applied` → re-executed every 5 min forever (flooding `si_action_log`), or count-based healers return `ok=False` on the second run and a *successful* rec flips to `failed`.
2. **Zero-search pipeline 100% dead** ([zero_search.py:30-34](file:///Users/magnetoid/coding/morph/core/self_improvement/collectors/zero_search.py#L30-L34) vs [catalog.py:980-985](file:///Users/magnetoid/coding/morph/plugins/installed/storefront/views/catalog.py#L980-L985)). Handler expects `result_count`; the fire site sends `results_count=None`. No zero-result search has ever produced a signal — the synonym healer has never received evidence.
3. **Error-log collector reads a retired table** ([error_log.py:128-135](file:///Users/magnetoid/coding/morph/core/self_improvement/collectors/error_log.py#L128-L135)). Since ADR 0025 all errors write to `core.errors.ErrorEvent`; the collector still reads `observability.ErrorEvent` (no writers). The error_cluster → Brain feed is silently starved.
4. **Reject/snooze suppression never matches** ([services.py:74-84](file:///Users/magnetoid/coding/morph/core/self_improvement/services.py#L74-L84) vs [self_improvement.py:118-122](file:///Users/magnetoid/coding/morph/plugins/installed/admin_dashboard/views_split/self_improvement.py#L118-L122)). Dashboard writes recommendation-vocabulary class + signal PK; `emit_signal` filters signal-vocabulary source + SHA-256 fingerprint. Rejected issues re-enter the backlog every nightly run.

---

## Task 2 — Performance Evaluation

> No production metrics endpoint exists (see Task 4), so this is a **structural** performance review: request-path work, timeout arithmetic, and I/O patterns verified in code. Each item names the resource it burns.

### 2.1 Compute (CPU) bottlenecks

| Severity | Finding | Resource cost |
|---|---|---|
| High | `hooks.fire()` runs `_serialize_payload` (full `json.dumps`→`loads` round-trip + per-call class definition + unbounded QuerySet evaluation) **on every fire, even with zero webhooks and NATS off** ([hooks.py:250-320](file:///Users/magnetoid/coding/morph/core/hooks.py#L250-L320)) | CPU + cursor time on every `cart.item_added` / `product.viewed` |
| Medium | Per-turn memory recall loads up to 200 rows and cosine-scores them in Python on every chat message | CPU per assistant turn |
| Medium | Error capture groups only at read time; every exception = one INSERT ([errors/services.py:74-109](file:///Users/magnetoid/coding/morph/core/errors/services.py#L74-L109)) | Write storm amplification under incident load |
| Low | NATS publish opens a fresh connection + `stream_info` per event ([tasks.py:120-146](file:///Users/magnetoid/coding/morph/core/tasks.py#L120-L146)) | 2 extra round-trips per outbox event |

### 2.2 I/O bottlenecks

| Severity | Finding | Resource cost |
|---|---|---|
| High | Embeddings client constructed per call with SDK-default **600s timeout + 2 retries**, on the request path every turn ([embeddings.py:44-76](file:///Users/magnetoid/coding/morph/core/embeddings.py#L44-L76)) | A hung embeddings endpoint stalls chat far past the 30s worker budget |
| High | Push collectors (`zero_search`, `csp`, `cart_abandon`) write 2–3 DB round-trips **synchronously in request paths** ([services.py:86-115](file:///Users/magnetoid/coding/morph/core/self_improvement/services.py#L86-L115)) | Latency on search/browse hot paths; racy check-then-create |
| Medium | `StoreSettings.get()` hits DB per call; placeholder-image context processor calls it **every page render, uncached** ([context_processors.py:38-46](file:///Users/magnetoid/coding/morph/core/context_processors.py#L38-L46)) | +1 query on every storefront request |
| Medium | `db.list_models` runs one `COUNT(*)` per installed model per call | Hundreds of counts, several over large tables |
| Medium | `db.recent_orders` N+1 on `customer.email`; `trans` i18n filter N+1 by design (24 products × 3 fields ≈ 72 queries) | Query amplification in tools and list templates |
| Low | `upstream_drift` collector: one `git diff` subprocess + one `is_path_customized` query **per drifted file** | O(N) processes on large vendor drifts |

### 2.3 Latency and timeout arithmetic (the structural bug)

The 30s gunicorn worker budget ([llm.py:37-42](file:///Users/magnetoid/coding/morph/core/agents/llm.py#L37-L42) documents it) is exceeded by design in three places:

- **Fallback router:** 3 providers × 20s sequential = 60s; runtime retries the whole call once → **~121s worst case** ([llm.py:852-854](file:///Users/magnetoid/coding/morph/core/agents/llm.py#L852-L854), [assistant/runtime.py:411-431](file:///Users/magnetoid/coding/morph/core/assistant/runtime.py#L411-L431))
- **Consensus evaluate:** up to 4 providers × 20s sequential = 80s **inside a tool call**
- **In-request waits:** `wait_for_workers` up to 300s, `delegate.invoke_agent` 90s

Result: SIGKILL mid-turn, dead SSE streams, and `AgentRun.state='running'` rows that no reaper ever closes. This converts the provider-failover safety net into the platform's most reliable way to produce stuck state.

### 2.4 Throughput constraints

- Spawn concurrency capped per call (6) but unbounded across calls; daemon threads hold per-thread DB connections for their lifetime ([spawn.py:375-392](file:///Users/magnetoid/coding/morph/core/assistant/tools/spawn.py#L375-L392))
- Circuit breaker state is per-process: with N gunicorn workers the effective trip threshold is N× configured, and after cooldown every worker probes the recovering dependency simultaneously (`half_open_probe_in_flight` is declared but never used)
- `execute_queue` has no concurrency guard — two workers (or a slow run + next beat) execute the same recommendation concurrently

---

## Task 3 — Security Assessment

### 3.1 What is genuinely strong

- **OTP design:** per-email cumulative lockout (IP-rotation-proof), SHA-256 codes at rest, latest-code-wins invalidation, no account enumeration, second-factor gate fails **closed** with a dedicated test
- **API keys:** hash-at-rest, prefix identification, raw key shown once
- **`core/safety.py`:** allowlist-first boundary, symlink escape tests, contract test suite — the model file for the repo
- **Emails:** fully autoescaped, no `|safe`, redacted logs, on-commit send (rolled-back orders never email)
- **Hook bus:** handler isolation, opt-in fail-closed filters, disable-gating, on-commit webhooks
- **Governed apply chain** (self-improvement code changes): kill switch, owner approval in DB, post-approval re-scan, path check before every write, full audit trail

### 3.2 Vulnerabilities and gaps (validated)

| # | Severity | Finding | Evidence |
|---|---|---|---|
| S1 | **Critical** | Approval gate fail-open in-process: `requires_approval` enforced only at MCP edge; `AgentRuntime` skips it when `approval_check=None`; no production caller wires one. Write tools like `catalog.publish_digital_product` reachable without approval | [runtime.py:269-272](file:///Users/magnetoid/coding/morph/core/agents/runtime.py#L269-L272), [services.py:192](file:///Users/magnetoid/coding/morph/plugins/installed/agent_core/services.py#L192) |
| S2 | **Critical** | Write confirmation is model-behavior: `confirmed=True`/`hard_gate_ack=YES` are LLM-supplied params. Attacker-controlled text (order notes, product descriptions, RAG chunks) can instruct the model to pre-confirm refunds/cancels/plugin-disables | [ecommerce_writes.py:47-119](file:///Users/magnetoid/coding/morph/core/assistant/tools/ecommerce_writes.py#L47-L119) |
| S3 | **Critical** | OTel PII scrubber no-op: `set_attribute` on ended span is silently dropped by the SDK → emails/phones/IPs in span attributes exported unscrubbed | [observability.py:63-84](file:///Users/magnetoid/coding/morph/core/observability.py#L63-L84) |
| S4 | **High** | OTP issuance: no per-IP throttle; middleware rule `^/auth/(login\|signup\|password/reset)/?` doesn't match mounted `/auth/otp/` → email-bombing relay at up to 300/min global | [auth/services.py:46-50](file:///Users/magnetoid/coding/morph/core/auth/services.py#L46-L50), [ratelimit.py:38-41](file:///Users/magnetoid/coding/morph/core/ratelimit.py#L38-L41) |
| S5 | **High** | Assistant runtime: no scope enforcement, client-controlled `mode` → unknown mode maps to `general` wildcard = full access. Any `is_staff` user gets refunds, `settings.set`, `plugins.toggle` regardless of permissions | [assistant/runtime.py:657-736](file:///Users/magnetoid/coding/morph/core/assistant/runtime.py#L657-L736), [modes.py:122-128](file:///Users/magnetoid/coding/morph/core/assistant/modes.py#L122-L128) |
| S6 | **High** | `fs.read_file` reads `.env` / key material — never consults `PROTECTED_PATHS`; contents land in `AgentStep` rows and chat transcripts | [filesystem.py:46-116](file:///Users/magnetoid/coding/morph/core/assistant/tools/filesystem.py#L46-L116) |
| S7 | **High** | `OpsProposal.apply()` generic `setattr` on any model/field — `auth.user.is_superuser` reachable; no per-kind field allowlist; callable without `approved` status | [assistant/models.py:401-477](file:///Users/magnetoid/coding/morph/core/assistant/models.py#L401-L477) |
| S8 | **High** | `plugins.disable` tool bypasses `PROTECTED_PLUGINS` (soft-brick `admin_dashboard`/`orders`); the CLI `morpheus disable` consults no guard either; dashboard keeps a divergent copy of the list | [tools/plugins.py:81-99](file:///Users/magnetoid/coding/morph/core/assistant/tools/plugins.py#L81-L99), [morpheus.py:177-191](file:///Users/magnetoid/coding/morph/core/management/commands/morpheus.py#L177-L191) |
| S9 | **High** | `is_customization_safe` + `confidence` read from analyzer LLM JSON; signal payloads contain attacker-influenceable text interpolated into the prompt → prompt-injection can steer auto-apply | [recommend.py:128-137](file:///Users/magnetoid/coding/morph/core/self_improvement/recommend.py#L128-L137), [policy.py:191-196](file:///Users/magnetoid/coding/morph/core/self_improvement/policy.py#L191-L196) |
| S10 | **High** | Safety path matcher bypassable: un-normalized paths (`plugins/installed/x/../payments/y.py`, doubled slashes, absolute) evade every `PROTECTED_PATHS` entry while `git apply` resolves them into protected files | [safety.py:217-227](file:///Users/magnetoid/coding/morph/core/safety.py#L217-L227) |
| S11 | **High** | Enforcement files outside the boundary: `scripts/check_forbidden_diff.py`, `.github/workflows/`, `.pre-commit-config.yaml`, `requirements.txt` — an AI proposal may weaken its own gate or add an unvetted dependency | [safety.py:30-62](file:///Users/magnetoid/coding/morph/core/safety.py#L30-L62) |
| S12 | **High** | `settings.set` writes arbitrary plugin keys (incl. `api_key`); tool args persisted to audit + transcripts → secrets in cleartext transcripts | [admin_ops.py:90-110](file:///Users/magnetoid/coding/morph/core/assistant/tools/admin_ops.py#L90-L110) |
| S13 | **Medium** | Bearer-token rate-limit bucketing by raw token prefix **before auth validation** — spoofed/rotating header gets the 600/min tier; token fragments in Redis keys | [api/rate_limit.py:29-36](file:///Users/magnetoid/coding/morph/api/rate_limit.py#L29-L36) |
| S14 | **Medium** | Memory-poisoning chain: worker `final_text` (can contain attacker content) → `inferred` LindaMemory → injected into every future system prompt, no sanitization | [reflection.py:92-133](file:///Users/magnetoid/coding/morph/core/assistant/reflection.py#L92-L133) |
| S15 | **Medium** | Sentry scrubbing misses breadcrumbs/contexts; OTP `consume_otp` non-atomic (replay race); Redis outage 500s login; `_safe_next` misses `/\evil.com` backslash case (open redirect) | [sentry.py:64-73](file:///Users/magnetoid/coding/morph/core/sentry.py#L64-L73), [auth/services.py:85-96](file:///Users/magnetoid/coding/morph/core/auth/services.py#L85-L96), [auth/views.py:40-45,121-127](file:///Users/magnetoid/coding/morph/core/auth/views.py#L40-L45) |
| S16 | **Medium** | Audit trail mutable + metadata never scrubbed; `record()` "never raises" false for non-serializable metadata | [audit/models.py:11-63](file:///Users/magnetoid/coding/morph/core/audit/models.py#L11-L63) |
| S17 | **Low** | Gemini API key in URL query string (access logs); `X-Request-ID` reflected with control chars (log forging); `search_files` grep argument injection (`-`prefix); dashboard CSP still allows `unsafe-inline`/`unsafe-eval` with no reporting endpoint | various |

---

## Task 4 — Scalability Assessment

### 4.1 Load capacity constraints (structural)

| Constraint | Failure mode under load | Scaling lever blocked |
|---|---|---|
| Worker-timeout mismatch (§2.3) | Under LLM provider slowness, every assistant turn risks SIGKILL → connection churn, stuck runs, retried work | Vertical + horizontal (more workers just produce more stuck runs) |
| Per-process circuit breakers | N workers = N× trip threshold; thundering-herd probes after cooldown | Horizontal — adding workers weakens the protection |
| `db_router` without read-after-write pinning | Enabling a replica introduces stale-read split-brain in exactly-once flows (`ORDER_PAID` gating) | Read scaling via replicas |
| Error capture write amplification | Incident → exception storm → INSERT per request → DB pressure during the worst moment | Failure-domain isolation |
| Unbounded `si_*` tables + no retention | `si_signal`/`si_action_log` grow forever (core errors get nightly prune; SI tables don't — and the heal loop bug multiplies rows 288×/day per stuck rec) | Long-run operational stability |
| Shared per-request serialization in `fire()` | Every high-frequency event pays JSON round-trip + potential QuerySet evaluation | Event throughput |
| Spawn thread DB connections | Unbounded cross-call spawn threads hold connections for their lifetime | Connection pool headroom |

### 4.2 Single points of failure

- **Redis** is cache + Celery broker + rate-limit backend + lockout store. Outage behavior is inconsistent by module: storefront limiter fails open, `utils/rate_limit.py` decorator 500s, login 500s. One dependency, three failure policies.
- **The LLM provider path** has good failover (router + breaker + mock) but the latency budget arithmetic means failover itself can kill the request (§2.3).
- **`execute_queue`** has no `select_for_update`/`running` transition — horizontal worker scaling creates duplicate heal execution.

### 4.3 What's already scale-ready

- Outbox pattern with `FOR UPDATE SKIP LOCKED` (safe multi-worker drain)
- Inventory reservation with `select_for_update` + `transaction.atomic`
- Webhook delivery with on-commit enqueue, HMAC, backoff, DLQ
- `request_id` contextvar propagation for distributed tracing
- Rate-limit middleware with CF-IP-aware resolution and tests

---

## Task 5 — UX & Functionality Gaps (core-caused)

Core defects that surface as broken or degraded user-facing functionality:

| Severity | User-visible symptom | Root cause |
|---|---|---|
| High | "Reject" in the self-improvement dashboard doesn't work — rejected recommendations return nightly | Suppression vocabulary mismatch (finding §1.3 #4) |
| High | Healing action log floods with repeats; successful heals later show as "failed" | Heal-loop terminal-state bug (§1.3 #1) |
| High | Search synonyms never improve; zero-result searches never surface | Dead zero_search pipeline (§1.3 #2) |
| High | Brain "errors" insight feed is stale/empty | Collector reads retired table (§1.3 #3) |
| High | Assistant chat hangs then dies on provider slowness; spawned workers never report back | Timeout arithmetic (§2.3) + no stuck-run reaper |
| Medium | Login page 500s during Redis outage instead of degrading | `check_and_consume` lets `ConnectionError` propagate |
| Medium | Weekly engineering digest never arrives (task logs counts, sends nothing) | `digest_weekly` stub; `weekly_digest_v1` prompt is dead code |
| Medium | Stored `fr-CA` translations unreachable from templates (and vice-versa) | Write stores BCP-47, read truncates to `fr` |
| Medium | Redirect healer can mint browser-cached 301s to 404s | `_candidate_pairs` never verifies the target resolves |
| Low | Prompt teaches nonexistent tool names (`products.count`) → model fumbles first calls | Stale prompt line in [prompts.py:27-28](file:///Users/magnetoid/coding/morph/core/assistant/prompts.py#L27-L28) |
| Low | `plugins.enable` creates phantom `PluginConfig` rows for typo'd names | No validation against `MORPHEUS_DEFAULT_PLUGINS` |

---

## Task 6 — Prioritized Improvement Register

Priority = (business impact × blast radius × exploitability) ÷ implementation effort.

### Critical (fix this week)

| ID | Finding | Effort | Risk mitigated |
|---|---|---|---|
| C1 | Fail-closed approval gate + human approval tokens for `requires_approval` tools (S1, S2) | 3–5 d | Unauthorized AI writes (refunds, publishes, plugin toggles) |
| C2 | Heal-loop terminal state + healer idempotency (§1.3 #1) | 1–2 d | Infinite re-execution, false-failure noise, log flooding |
| C3 | OTel PII scrubber fix (S3) | 0.5 d | PII leaking to trace backend |
| C4 | Repair dead collectors + suppression (§1.3 #2–4) | 2–3 d | Immune system running blind; broken staff UX |
| C5 | OTP per-IP throttle + rate-rule fix (S4) | 1 d | Email-bombing relay, sender-reputation damage |

### High (fix this month)

| ID | Finding | Effort | Risk mitigated |
|---|---|---|---|
| H1 | Assistant scope enforcement + server-side mode mapping (S5) | 2–3 d | Privilege escalation by any staff user |
| H2 | Secrets exposure triad: `fs.read_file` denylist, `OpsProposal` field allowlist + approved-only apply, `plugins.disable`/CLI through `is_plugin_protected` (S6–S8) | 2–3 d | `.env` exfiltration, `is_superuser` escalation, soft-brick |
| H3 | Timeout arithmetic: per-call LLM deadline, cap in-request waits at ~20s, embeddings client timeout 10s + reuse, stuck-run sweeper (§2.3) | 2–3 d | SIGKILL mid-turn, stuck `AgentRun` rows, dead SSE |
| H4 | Self-improvement trust hardening: server-side `is_customization_safe`, clamp confidence, normalize safety paths, protect enforcement files, implement token budget (S9–S11) | 3–4 d | Prompt-injection-driven auto-apply, gate-weakening diffs |
| H5 | `settings.set` key allowlist + transcript redaction (S12) | 1 d | Secrets in cleartext transcripts |
| H6 | OTP hardening pack: atomic consume, Redis-outage fail-open, `_safe_next` via `url_has_allowed_host_and_scheme`, **OTP test suite** (S15) | 2 d | Code replay, login 500s, open redirect, untested front door |
| H7 | Rate-limiter consolidation: one helper, one IP resolution, one failure policy; hash bearer identity post-auth (S13) | 2 d | Limit bypass, inconsistent outage behavior |

### Medium (this quarter)

| ID | Finding | Effort |
|---|---|---|
| M1 | `fire()` fast-path: check webhook/NATS presence before serializing; cache endpoint list | 1 d |
| M2 | Circuit breaker: implement single-probe gating + shared state (or fix the docs) | 1–2 d |
| M3 | db_router read-after-write pinning | 1–2 d |
| M4 | `money.py` currency-aware precision (JPY/KWD) | 1 d |
| M5 | Sentry breadcrumbs/contexts scrubbing; audit append-only + defensive serialization | 1–2 d |
| M6 | Error capture write-time dedup (fingerprint counter + sampled detail); drop lineno from fingerprint | 1–2 d |
| M7 | StoreSettings singleton caching; `recent_orders` select_related; `list_models` count cache; i18n prefetch helper | 1–2 d |
| M8 | Memory-poisoning mitigation: sanitize/review inferred memories | 1 d |
| M9 | `si_*` retention task; rec-level dedup via fingerprint; advise-vs-propose persistence; `locked_until` honored | 2–3 d |
| M10 | Runtime convergence: extract shared dispatch/humanizer between the two runtimes | 3–5 d |
| M11 | Tool arg validation against declared JSON schema (`jsonschema`) | 1–2 d |
| M12 | Collector/healer disable-state checks; async `emit_signal` for hot paths; atomic dedup (`F()` + update_or_create) | 2 d |

### Low (backlog)

| ID | Finding |
|---|---|
| L1 | NATS connection reuse + cached stream check |
| L2 | `morph_bench` accuracy (total time, keep-alive note, loud baseline-missing, allow 0 threshold) |
| L3 | workflows.py: record skipped steps, honest torn-state reporting, MRO/doc alignment |
| L4 | Dead code sweep: `_inject_memories`, legacy `APIKey.key` plaintext column, `_unpack` legacy tuples, `debug_task` |
| L5 | Docstring alignment pass (12 confirmed drift incidents — treat as one themed PR) |
| L6 | Gemini via OpenAI-compatible endpoint (header auth); `X-Request-ID` whitelist; grep `--` guard |
| L7 | CSP: precompiled Tailwind to drop `unsafe-eval`, nonces, report endpoint on enforcing policy |
| L8 | Email retry narrowing (permanent failures shouldn't retry); Brain analyst `None`-token TypeError guard |

---

## Task 7 — Structured Proposals for High-Priority Improvements

### Proposal C1 — Close the agent authorization gap (fail-closed gates + human approval)

**Problem:** `requires_approval` is enforced only at the MCP edge; in-process runtimes skip it; write confirmations are model-supplied parameters that injected text can forge.

**Implementation plan:**
1. `AgentRuntime._dispatch_tool`: if `tool.requires_approval and approval_check is None` → `ToolError("approval required but no approval flow active")` (fail closed).
2. Introduce `ApprovalToken` model: `hash(tool_name + canonical_args + conversation_id + user_id)`, created by a real dashboard/chat UI click, single-use, 5-min TTL. `_dispatch_tool` verifies and consumes it.
3. Wire `approval_check` in `spawn.py`, `agent_core/services.py`, `briefing.py` to check the token store.
4. Remove `confirmed`/`hard_gate_ack` as sufficient gates — keep them as UX hints only.
5. Tests: approval-required tool without token → error; with forged model flag → error; with valid token → executes; token reuse → error.

**Resources:** 1 senior backend, 3–5 days. No new dependencies.
**Expected outcome:** No code path can execute an approval-gated write without a recorded human action.
**Success metrics:** 100% of `requires_approval` tool invocations have a matching consumed `ApprovalToken` row (auditable query); 0 in security regression test `test_agentic_hardening.py` extensions; prompt-injection fixture (malicious product description instructing refund) fails to execute.

### Proposal C2+C4 — Revive the self-improvement loop (4 dead links)

**Problem:** heal loop never terminates; zero-search and error-log collectors are dead; rejection suppression never matches. The platform's flagship subsystem is running on half its sensors and spamming its own logs.

**Implementation plan:**
1. `heal.run_one`: on success set terminal `status='merged'` (new `'healed'` if a distinct state is wanted); healers return `ok=True, details={'updated': 0}` when idempotent-noop; regression test running `run_one` twice.
2. `zero_search`: align kwarg to `results_count`, fire with the real count from the PLP path, integration test asserting one `si_signal` per zero-result search.
3. `error_log` collector: repoint to `core.errors.ErrorEvent` with field mapping (`created_at`, `traceback`, reuse `fingerprint`); update stale comments in `settings.py`/`celery.py`.
4. Suppression: store the signal fingerprint on `SiRecommendation` at creation; reject/snooze writes `match_class=<mapped source>` + real fingerprint; add the documented-but-missing cluster-level suppression re-check; integration test: reject → next analyzer run produces no rec.
5. Add rec-level dedup (fingerprint column; skip create when an open rec exists).

**Resources:** 1 backend, 3–4 days.
**Expected outcome:** All four pipelines deliver signals end-to-end; heal actions execute exactly once; rejected issues stay rejected.
**Success metrics:** zero-result search produces a signal within 1 min (staging test); error capture produces a cluster rec in the next nightly run; heal action log rows per rec ≤ 2; rejected fingerprint rec count stays 0 across 7 nightly runs; `si_action_log` growth rate drops >95%.

### Proposal C3 — Fix the OTel PII scrubber

**Problem:** `PIIScrubberProcessor.on_end` mutates an ended span — a silent no-op with the pinned SDK; PII attributes export unscrubbed, contradicting the module's privacy guarantee.

**Implementation plan:**
1. Move scrubbing into the exporter path (wrap the OTLP exporter) or mutate `span._attributes` directly with an explanatory comment.
2. Unit test: span with `user.email`/`http.client_ip` attributes exports redacted values.
3. Backfill check: verify what attribute keys actually carry PII in current spans and cover them.

**Resources:** 1 backend, 0.5 day.
**Success metrics:** new test passes; staging trace export shows redacted values for the PII attribute set; Sentry/OTel backend audit shows no raw emails in new spans.

### Proposal C5 — OTP issuance throttle + flow hardening

**Problem:** no per-IP issuance cap; rate-limit rule misses `/auth/otp/`; consume race; Redis outage 500s; backslash open redirect; zero tests — for the platform's front door.

**Implementation plan:**
1. Add `/auth/otp/` to `_RULES` with a tight per-IP budget (10/min) + per-IP daily issuance cap in `issue_otp`.
2. Atomic consume: `filter(pk=..., consumed_at__isnull=True).update(consumed_at=now)` → proceed only on 1.
3. Catch cache backend exceptions in `check_and_consume` → fail open with warning (match documented policy).
4. `_safe_next` → `url_has_allowed_host_and_scheme`.
5. New `core/auth/tests/`: issue→consume→expiry→single-use→lockout→MFA-gate→safe-next matrix.

**Resources:** 1 backend, 2 days.
**Success metrics:** >1,000 distinct-email OTP requests from one IP in load test → ≤10/min accepted; concurrent double-submit of one code → exactly one success; Redis down → login page renders (degraded), not 500; OTP test suite ≥15 tests green in CI.

### Proposal H3 — Fix the timeout arithmetic

**Problem:** worst-case LLM latency ~121s and in-request waits up to 300s vs a 30s worker budget → SIGKILL mid-turn, dead streams, permanently `running` AgentRuns.

**Implementation plan:**
1. Per-call deadline budget passed into the fallback router (e.g. 24s total); skip runtime-level retry when the router already fell back; run consensus providers concurrently (threads) with the same budget.
2. Embeddings: module-level client, `timeout=10, max_retries=0`, query-embedding cache.
3. `wait_for_workers`/`invoke_agent`: cap at ~20s, return "still running — poll" status instead of blocking.
4. Stuck-run sweeper: beat task marking `AgentRun.state='running'` older than 10 min as `failed` with reason `worker_timeout`.

**Resources:** 1 senior backend, 2–3 days.
**Success metrics:** p99 assistant-turn latency < 28s under provider-failure injection (kill primary provider in staging); 0 AgentRuns stuck `running` >15 min over 7 days; SSE stream survives single-provider outage with a graceful error event.

### Proposal H4 — Self-improvement trust-boundary hardening

**Problem:** auto-apply safety flags are LLM-controlled and prompt-injection-reachable; safety path matcher evadable; the enforcement files themselves are unprotected; documented token budget unimplemented.

**Implementation plan:**
1. Compute `is_customization_safe` server-side from `SiCustomization` for the targets involved; clamp `confidence` to [0,1]; use deterministic `_score` for impact; treat all LLM plan values as advisory.
2. `is_path_protected`: `posixpath.normpath`, reject `..` post-norm, strip leading `/`/`./`; add evasion cases to `test_safety_boundary.py`.
3. Add `scripts/`, `.github/`, `.pre-commit-config.yaml`, `requirements*.txt`, `pyproject.toml` to `PROTECTED_PATHS` (gate-file tier forcing human review).
4. Implement `daily_token_budget`: sum `tokens_used` per day in `run_analyzer`, abort cluster loop past budget.

**Resources:** 1 senior backend, 3–4 days.
**Success metrics:** injection fixture (crafted search query/error text steering `is_customization_safe: true`) cannot produce an auto-apply; 6 path-evasion fixtures all blocked; any diff touching enforcement files requires human approval (CI test); analyzer run with budget=1k tokens aborts with `budget_exceeded` log.

### Proposal H1+H2 — Assistant authorization & secrets exposure pack

**Problem:** assistant enforces no scopes (mode is client-controlled); `fs.read_file` reads `.env`; `OpsProposal` can setattr any field; `plugins.disable`/CLI bypass protected-plugin guard.

**Implementation plan:**
1. Map tool scopes → `request.user.has_perm()` in assistant `_dispatch_tool` (user already in context); treat `mode` as UX-only, server-mapped.
2. `read_file_tool`: reject paths matching `PROTECTED_PATHS`, dotfiles, and key material.
3. `OpsProposal`: per-kind field allowlists; `apply()` requires `status='approved'`.
4. Route `disable_plugin_tool` and `morpheus disable` through `core.safety.is_plugin_protected`; dashboard imports the list from core (delete its divergent copy).

**Resources:** 1 backend, 2–3 days.
**Success metrics:** staff user without `orders.change_order` permission → refund tool call denied (test); `fs.read_file('.env')` → denial (test); proposal targeting `is_superuser` → rejected at validation (test); disabling `admin_dashboard` via tool and CLI → both refused (tests).

---

## Task 8 — Validation of Findings

### 8.1 Evidence collected directly (this audit)

| Check | Command / method | Result |
|---|---|---|
| Lint conformance | `ruff check core/ --statistics` | **0 findings** |
| Boot/system health | `DATABASE_URL='sqlite:///:memory:' python3 manage.py check` | **0 issues (0 silenced)** |
| Code size | `find core -name '*.py' \| wc -l` + LOC | 278 files; 22,196 non-test LOC; 5,807 test LOC |
| Debt markers | grep TODO/FIXME/HACK/XXX | 1 occurrence |
| Exception-handling surface | grep `except Exception` / silent `pass` | 184 / 23 |
| Finding verification | Every Critical/High finding re-read against source with line numbers by the reviewing pass; 2 candidate findings dropped as false positives during review | ~80 findings, all source-verified |

### 8.2 Cross-referencing performed

- **Prior audits:** consistent with [comprehensive_application_audit_2026-07.md](comprehensive_application_audit_2026-07.md) (agent invocation risk, RBAC enforcement gap, cache correctness) and [enterprise_benchmark_gap_report_2026.md](enterprise_benchmark_gap_report_2026.md) (audit immutability, rate-limit divergence). This audit adds the *core-internal root causes* (e.g. the OTel scrubber no-op behind "PII" findings; the fail-open approval gate behind "agent invocation" findings).
- **Project docs:** findings match documented landmines in `CLAUDE.md` (disable-vs-absence, protected plugins) and extend them (the CLI and the old disable tool bypass the guard CLAUDE.md describes).
- **Industry benchmarks used for calibration:** OWASP API Security Top 10 (S4, S13 ≈ API4 unrestricted resource consumption / API1 BOLA-class ownership), OWASP LLM Top 10 (S2, S9, S14 ≈ LLM01 prompt injection / LLM06 excessive agency), SOC 2 CC6/CC7 (S16, C3 ≈ audit integrity / confidential-data handling), SRE timeout-budget practice (H3: end-to-end deadline must be ≤ gateway timeout).

### 8.3 Honest validation limits

- **No production logs or live metrics were available in-repo.** Performance findings are structural (verified request-path work and timeout arithmetic), not measured p99s. Closing this gap is itself a finding — the platform has no Django `/metrics` endpoint; Proposal M-series and the companion audit's observability items cover it.
- **No user-feedback corpus exists in-repo.** UX findings in Task 5 are derived from code paths that deterministically produce broken behavior (dead pipelines, stub tasks), not from sentiment data.
- **Exploitability ratings are analytical.** No penetration test was run; findings S1–S12 were confirmed reachable in code but not exercised against a live instance. Recommend a focused red-team pass on the agent tool surface after C1/H1/H2 land.

### 8.4 Suggested validation loop going forward

1. Land C1–C5 (week 1–2) with their regression tests — each proposal names its measurable check.
2. Add a `test_docstring_guarantees` convention: any module claiming a guarantee (scrubbing, immutability, budgets, shared state) must have a test that would fail if the guarantee is false. This single convention would have caught 12 of this audit's findings.
3. Stand up the metrics endpoint + one staging load test before/after H3 to convert structural performance claims into measured ones.

---

## Appendix A — What is genuinely excellent (preserve these patterns)

- `core/safety.py` + `test_safety_boundary.py` — the model contract suite; extend, don't rewrite
- `core/hooks.py` — handler isolation, fail-closed filters, on-commit enqueue, event catalog documentation
- `core/emails/` — render-in-request/send-on-commit, autoescaped, redacted
- `core/updates.py` — defensive deployment done right
- `core/agents/compaction.py` — tool-call pair integrity
- OTP design fundamentals — lockout, hashing, no enumeration (the gaps are at the edges, not the core)
- The governed apply chain (codegen → consensus → owner approval → path-checked write → audit)
- Failure-containment culture — persistence falls back to JSONL, trace sinks are per-sink best-effort

*Report compiled from three parallel source-verified module reviews (agents/assistant, platform kernel, self-improvement/safety/i18n/emails/brain), direct command evidence (ruff, system check, LOC/debt metrics), and cross-referencing against two prior platform audits and project rule documents.*
