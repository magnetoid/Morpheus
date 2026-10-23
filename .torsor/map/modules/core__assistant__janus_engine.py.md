---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/assistant/janus_engine.py

Symbols in `core/assistant/janus_engine.py`.

- L141 `_settings()` (function)
- L150 `engine_root()` (function)
- L167 `janus_cmd()` (function)
- L182 `_source_checkout_cmd()` (function) — A Janus source checkout (``JANUS_ENGINE_ROOT``, ``~/.janus/janus-agent``).
- L201 `janus_available()` (function)
- L205 `auto_approve_enabled()` (function) — Whether the subprocess may execute tool calls without a prompt.
- L216 `turn_toolsets()` (function) — The toolsets a turn loads: the base set, web search and memory while allowed.
- L226 `turn_timeout_s()` (function) — Settings → AI → Janus, else ``LINDA_JANUS_TIMEOUT_S``; never above the cap.
- L237 `linda_janus_home()` (function) — Where conversation homes live: ``LINDA_JANUS_HOME``, else a private temp dir.
- L260 `bundled_skills_dir()` (function) — Repo-shipped Morpheus ecommerce skills (not the operator ``~/.janus``).
- L268 `bundled_skill_names()` (function)
- L285 `prune_idle_homes(conv_root: Path, *, keep: Path, now: float | None=None)` (function) — Remove ``linda-*`` homes under `conv_root` idle past HOME_PRUNE_AFTER_S.
- L304 `_maybe_prune_homes(current: Path)` (function) — At most hourly per process; a failure here never costs a turn.
- L316 `_session_id(conversation_key: str)` (function)
- L321 `_inference_env_names()` (function) — API-key / base-URL env names the LLM providers read.
- L338 `_child_env(overrides: dict[str, str])` (function) — Allowlisted environment for the Janus subprocess.
- L350 `_config_text(mcp_url: str, headers: dict[str, str] | None=None, progress_path: Path | None=None, *, fallbacks: list[dict[str, str]] | None=None)` (function)
- L450 `_prepare_home(home: Path)` (function) — Linda's identity, and no general-purpose Janus skills in her prompt.
- L465 `_ensure_config(home: Path, *, mcp_url: str='', mcp_headers: dict[str, str] | None=None, fallbacks: list[dict[str, str]] | None=None)` (function) — Write (or REWRITE) the store-agent Janus config.
- L492 `_default_host()` (function) — The first concrete host the deployment serves (no wildcards or loopback).
- L503 `_mcp_endpoint(context: dict[str, Any] | None)` (function) — Where the subprocess reaches the store's MCP server, and the headers it needs.
- L560 `pinnable_providers()` (function) — Morpheus provider names Janus can be pinned to (Settings → AI → Janus).
- L575 `_configured(name: str)` (function) — (Janus spec, provider config) for a provider Janus can run that has a key.
- L589 `selectable_providers()` (function) — Providers a message can be sent to: Janus runs them, they have a key, and
- L606 `_fallback_wiring(primary_env: dict[str, str])` (function) — Backup providers for `fallback_providers` (Settings → AI → Janus) and their keys.
- L632 `_provider_wiring(choice: str='')` (function) — CLI args + env that pin Janus to its provider.
- L685 `_session_meta(conv_home: Path)` (function)
- L693 `_stored_session_id(conv_home: Path)` (function) — The session to resume, or '' to start a fresh one.
- L708 `_remember_session_id(conv_home: Path, stderr: str)` (function)
- L722 `_forget_session_id(conv_home: Path)` (function)
- L738 `_session_usage(conv_home: Path, session_id: str)` (function) — Janus's running token and cost totals for one session, from its state.db.
- L757 `_session_started_since(conv_home: Path, since: float)` (function) — The Linda session Janus started at or after `since`, or ''.
- L775 `_recover_reply(conv_home: Path, resume_id: str, since: float)` (function) — The session and last assistant reply this turn wrote to state.db, if any.
- L797 `_turn_usage(before: dict[str, Any], after: dict[str, Any])` (function) — What this turn added to a session's totals (the row accumulates across resumes).
- L811 `_strip_notices(stdout: str)` (function)
- L816 `run_janus_turn(**kwargs: Any)` (function) — Run one store-agent turn on Janus and wait for it. See :func:`iter_janus_turn`.
- L824 `iter_janus_turn(*, message: str, conversation_key: str, system_prompt: str, timeout_s: int | None=None, context: dict[str, Any] | None=None, turn_token: str='', turn_context: str='', history: str='', tick_s: float=1.0)` (function) — Run one store-agent turn on Janus, yielding about every ``tick_s``.
- L930 `_relay_steps(ticks, progress: activity.ProgressReader)` (function) — Pass the ticks on, each one carrying the steps Janus reported since the last.
- L948 `_wait_ticking(run, tick_s: float)` (function) — Run ``run()`` in a thread, yielding ``None`` every ``tick_s`` until it returns.
- L974 `_turn_env(conv_home: Path, system_prompt: str, turn_token: str, provider_env: dict[str, str])` (function)
- L994 `_compose_message(message: str, turn_context: str, history: str)` (function) — The -q message: context for this message, a recap when the session is new,
- L1008 `_spawn(argv_for, env: dict[str, str], conv_home: Path, timeout: int, started: float, conversation_key: str)` (function)
- L1081 `_turn_result(returncode: int, text: str, err: str)` (function) — The reply or the failure, from what the Janus process returned.
