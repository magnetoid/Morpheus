# Janus: a stronger Linda, live steps, current engine (2026-10)

Owner asked (2026-10-09): Linda "looks slightly constrained, it needs to be very
powerful like an agent"; improve the thinking animation; remove the purple border
around the chat; update Janus from its GitHub source; improve how Janus works with
Morpheus overall.

## What was found

| Area | State before |
|---|---|
| Janus source | Dockerfile installs `magnetoid/janus.git@main` (repo renamed to `magnetoid/Janus-Agent`; GitHub redirects). Upstream main = `eafb7ab` (0.18.0) = what every store runs. No record of the installed commit anywhere. |
| Tools | Store tools over MCP + skills (+ memory while learning). No planning, no web, no recall of earlier sessions. |
| Limits | 10 tool steps, 120 s per message (cap 20 steps / 170 s). The prompt said "a few tool steps and well under a minute… do a sample, then offer background workers". |
| Progress | Every 5 s "Linda is working · Ns", plus a card per store tool once it finished. Nothing for Janus's own tools; nothing while a tool runs. |
| Chat form | `:focus-within` drew a 3 px ring in `--brand` (indigo `#4f46e5`): the purple border. |

**Not enabled, and why.** Janus's `delegate_task` takes `acp_command` and `acp_args`
from the model's own arguments and runs them with `subprocess.Popen`
(`agent/copilot_acp_client.py`). A prompt injection in anything Linda reads
could start any program as the app user, who can read the web process's
environment through `/proc`. Subagents stay off until Janus has a config switch
that removes those two arguments; a pre-tool hook could block them but hooks
fail open (a crashed or slow hook lets the call through). `web_extract` and
`vision` stay off too: a URL fetch is an outbound channel the model controls.

## Changes (v0.83.0)

1. **More power, same boundary.** Turn toolsets add `todo` (plan and track),
   `session_search` (FTS over this conversation's earlier sessions, no LLM call)
   and `search` (`web_search` only; DuckDuckGo through `ddgs`, no key, a merchant
   switch on Settings → AI → Janus). Defaults: 30 steps (cap 60), 240 s (cap 300).
   The prompt now asks Linda to plan, carry the job through, check her work, and
   use background workers only for jobs bigger than one message.
2. **Live steps.** Janus shell hooks (`pre_tool_call` / `post_tool_call`) run a
   stdlib script that appends one JSON line per step to the conversation home's
   `progress.jsonl`. The turn reads new lines every tick and streams `step` and
   `plan` events. Verified live on Janus 0.18.0 before building: both hooks fire
   for agent-loop tools, ~65 ms per step.
3. **Chat UI.** One activity block per turn: a status line that says what Linda is
   doing now, her plan as a checklist, each step with its time, store-tool
   details folded into the step. It folds to "Worked for 42 s · 6 steps" when the
   answer arrives. No indigo ring; neutral focus. Reduced motion respected.
4. **Engine source.** Canonical repo URL; the installed version and commit
   (pip's `direct_url.json`) and the latest upstream commit (GitHub API, cached a
   day) shown on the Janus page. `JANUS_REF` stays `main`, so each deploy installs
   upstream's latest, as the owner set it up; pin a SHA to freeze.
5. **Stores.** dotbooks and supernatural had the old 10 / 120 s saved from the
   settings form; raised to the new defaults with an audit record. supernatural's
   Linda stays off (the owner switched it off on 2026-09-24).
6. **Janus keeps itself current, and compatible** (owner, same day: "make Janus
   update often from its git and keep everything compatible").
   `core/assistant/janus_contract.py` states what Morpheus relies on in Janus:
   toolsets holding only reviewed tools, every config key Morpheus writes still
   read, the env vars, CLI options and state.db columns. The build runs it and
   falls back to `JANUS_KNOWN_GOOD`; a running store installs newer commits of its
   branch beside the current Janus every 3 hours (`janus_runtime.py` +
   `janus_updater.py`, GitHub archive, no git needed) and switches only on a pass;
   three engine failures in a row roll back. Measured on prod first: archive install
   29 s / 226 MB, contract run 2 s, all checks pass on 0.18.0 except `ddgs` (added
   here).

## Upstream follow-up for Janus (owner's repo)

- `delegation.allow_acp_override: false` (or drop `acp_command`/`acp_args` from the
  schema when no ACP command is configured), then Linda can get subagents.
- `agent/background_review.py` still swaps stdout/stderr process-wide; nudges stay 0.
