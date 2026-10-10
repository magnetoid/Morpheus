# Linda on Janus, end to end: chats, automations, models (2026-10-10)

Owner's asks (2026-10-10):

- "Linda should remember old chats so we can continue them — a tab in her menu."
- "Integrate cron with Automations — choose the best way."
- "Can Linda use several LLMs in one chat session?"
- "Check that everything on Linda's pages is integrated with Janus."
- Rule: every Morpheus-specific tuning of Janus lives in Morpheus; Janus is
  updated occasionally.

Research: Janus source at `eafb7aba` (= `JANUS_KNOWN_GOOD`); audit of the eight
Linda tabs. Findings that shape the design:

- One endless conversation per staff member (`user:<pk>`); Janus session ids
  live only in the ephemeral home (`janus_session.json`), rotated after 20 turns
  or 6 h idle. No list, no "new chat".
- Janus's own `cronjob` tool keeps jobs in `$JANUS_HOME/cron/jobs.json`
  (deleted on redeploy), runs them only from its gateway/`cron tick` (Morpheus
  runs neither), and its arguments reach a shell (`script`), any URL
  (`base_url` — the provider key is sent there) and outbound channels
  (`deliver`). Creating a job needs no consent.
- Automations (`/dashboard/agents/background/`, `BackgroundAgent`) runs the
  in-process Worker, interval-only, gated by `enable_autonomous_operator`.
- Janus supports a per-turn `--provider/-m`, a `fallback_providers` chain
  (switch on rate limit / billing / overload / connection failure) and
  auxiliary models for side tasks.
- Linda tabs: Activity/Observability read `AgentRun` (Janus turns create none);
  Memory reads `LindaMemory` (Janus can't write it; what Janus learns is on the
  Janus page); AI Act export omits Linda's consent trail; Proposals are never
  created from Janus; a timed-out turn records 0 tokens (spend cap misses it).

## Decisions

1. **Chats tab.** Each conversation gets its own key (`user:<pk>:<uuid>`),
   title (first message, editable), last-activity time and archived flag, owned
   by one staff user and checked server-side. A "Chats" tab lists them; "New
   chat" starts one; opening one continues it. The Janus session id is stored on
   the conversation (DB), so a redeploy does not lose the thread; the home is
   rebuilt and the recap sent when the session file is gone.
2. **Automations = the one scheduler, run by Linda (Janus).** Janus's own
   `cronjob` toolset stays off. Automations gains: engine (`linda`), schedule
   string (interval or 5-field cron), last output, and a run conversation per
   automation (`cron:<id>`), shown in Chats. A due automation runs as a Janus
   turn from a Celery task (one task per run, own time limit), with a turn token
   minted for the automation's owner. A run may read and report; it can never
   satisfy consent (the gate refuses consent for `cron:` keys — no human is
   there), so store writes come back as proposals for the merchant. Linda can
   create/pause/resume/run/delete automations through MCP tools — writes, so they
   need the merchant's yes and leave an audit row.
3. **Models.** A model picker in the composer (providers with a key, from
   `core.agents.provider_registry`); the chosen provider/model rides on the
   turn; the session continues. A fallback chain (Settings → AI → Janus) is
   written into the generated config as `fallback_providers`. Every selectable
   model must be priced (`core/agents/pricing.py`) or the spend cap can't count it.
4. **Audit fixes** (low risk first): count tokens of timed-out turns; Activity
   shows Linda's turns, failures and refusals; AI Act export includes the
   consent trail; Memory points at what Janus learned; fix stale copy/links
   (`runs.html`, `observability.html`, `memory.html`, the 404 feed link
   `/dashboard/agents/runs/<id>/`, CLAUDE.md's "tests force legacy").

## Steps (each verified before the next)

1. Conversations: model fields + migration; ownership-checked views; Chats tab;
   continue/new/rename/archive. Verify: tests incl. another user's chat → 404.
2. Session persistence in the DB; recovery after a redeploy. Verify: test with a
   wiped home.
3. Model picker + fallback chain + pricing. Verify: engine argv/config tests.
4. Automations on Janus: schedule parser, Celery task, `cron:` consent refusal,
   MCP tools, UI. Verify: gate tests (a cron run can't approve a write), tick tests.
5. Audit fixes. Verify: per-fix tests.
6. Release (MINOR), deploy, live check on Irving (Grok) with a real chat and a
   real automation run.
