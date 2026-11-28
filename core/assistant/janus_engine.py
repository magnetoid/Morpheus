"""Store agent engine: Janus (magnetoid/janus), isolated from Django.

Janus **is** the agent. Linda is the merchant-facing brand only. Morpheus and
Janus both ship top-level packages named ``plugins`` / ``tools``, so Janus MUST
run in a subprocess (own venv / own sys.path). Each conversation home is seeded
with bundled Morpheus ecommerce skills (``core/assistant/janus_skills``).

This module runs the turn. Four leaves hold the rest. Their names are re-exported
here (all but ``janus_home._last_prune``, which is rebound), because importers and
test patches read ``janus_engine.<name>``:

  * :mod:`core.assistant.janus_binary`: finding the Janus program and its build.
  * :mod:`core.assistant.janus_providers`: the provider and model a turn is pinned to.
  * :mod:`core.assistant.janus_home`: the conversation home, its config and its lock.
  * :mod:`core.assistant.janus_sessions`: the session id, and what ``state.db`` holds.

A test's patch on ``janus_engine.<name>`` changes what this file reads: the turn
runner, and anyone who calls through this module. A leaf's functions read each
other in their own module, so to change what one of them sees of another, patch
the leaf (``janus_binary._build_of`` for ``build_of``, ``janus_sessions._home_usage``
for ``_bill``).

SAFETY — read this before widening anything below. Janus runs its own tool loop
in a subprocess and reaches Morpheus over MCP, so NONE of the in-process gates in
:mod:`core.assistant.runtime` (scope → budget → deadline → kernel consent) and
none of the write auditing apply to a Janus turn. Two decisions here are
load-bearing:

  * ``JANUS_YOLO_MODE`` auto-approves every tool call the subprocess makes,
    shell writes under ``/app`` included — which makes ``core/safety.py``'s
    FORBIDDEN_PATHS unenforceable for that process. It is OFF unless a
    deployment sets ``LINDA_JANUS_AUTO_APPROVE``. Never default it on.
  * The child gets an env ALLOWLIST, never ``os.environ.copy()``:
    ``DATABASE_URL``, ``SECRET_KEY`` and the payment keys stay in the parent.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import tempfile  # noqa: F401 — a test redirects the temp dir through ``janus_engine.tempfile``
import threading
import time
from pathlib import Path
from typing import Any

from core.assistant import activity, janus_settings

# Re-exported, used here or not: see the module docstring.
from core.assistant.janus_binary import (  # noqa: F401
    _build_of,
    _settings,
    _source_checkout_cmd,
    build_of,
    engine_root,
    janus_cmd,
)
from core.assistant.janus_home import (  # noqa: F401
    _INSTALL_METHOD,
    _NO_BUNDLED_SKILLS,
    _PRUNE_EVERY_S,
    _SKILL_FILE_MAX,
    _SOUL,
    _TURN_LOCK,
    HOME_PRUNE_AFTER_S,
    MAX_TOOL_TURNS,
    MCP_SERVER_NAME,
    STORE_SKILLS_DIR,
    _config_text,
    _copy_skill_tree,
    _default_host,
    _ensure_config,
    _lock_home,
    _maybe_prune_homes,
    _mcp_endpoint,
    _prepare_home,
    _session_id,
    _staging_lock,
    _staging_locks,
    _staging_locks_guard,
    app_skill_dirs,
    bundled_skills_dir,
    linda_janus_home,
    prune_idle_homes,
    stage_store_skills,
)
from core.assistant.janus_providers import (  # noqa: F401
    _JANUS_PROVIDERS,
    _PROVIDER_LABELS,
    UnsupportedProvider,
    _configured,
    _fallback_wiring,
    _provider_wiring,
    pinnable_providers,
    selectable_providers,
)
from core.assistant.janus_sessions import (  # noqa: F401
    _NOTICE_PREFIXES,
    _SESSION_FILE,
    _SESSION_ID_RE,
    _SESSION_LINE_RE,
    _USAGE_COLUMNS,
    SESSION_IDLE_S,
    SESSION_MAX_TURNS,
    _bill,
    _counted_usage,
    _forget_session_id,
    _home_usage,
    _recover_reply,
    _remember_session_id,
    _save_session_meta,
    _session_meta,
    _session_started_since,
    _stored_session_id,
    _strip_notices,
    _turn_usage,
)
from core.assistant.turn_identity import ENV_VAR as TURN_TOKEN_ENV

logger = logging.getLogger('morpheus.assistant.janus')

# The chat streams while a turn runs: the subprocess waits in a thread and the
# SSE generator sends progress every few seconds. gunicorn's gthread workers
# (scripts/docker-entrypoint.sh) keep their heartbeat on the main loop, so a long
# streaming request is not killed at GUNICORN_TIMEOUT, and the steady bytes keep
# Cloudflare and nginx from closing an idle connection. A caller that does NOT
# stream (the settings page's connection test) must pass its own short timeout.
# Four minutes leaves room for real jobs; the chat shows every step meanwhile.
_DEFAULT_TIMEOUT_S = 240

# The MCP server name in the generated config, and the ONLY toolsets a turn may
# use. Without an explicit ``-t``, ``janus chat`` loads its default ``janus-cli``
# toolset — 56 tools including terminal, write_file/patch, execute_code, web and
# browser — running as the same OS user that owns /app and can read the web
# process's environment through /proc. So the env allowlist below is not the
# boundary; this list is. ``skills`` is list/view/manage of skill documents under
# JANUS_HOME only (no execution), and is what injects the bundled ecommerce
# skills into the prompt. ``todo`` is an in-memory plan, and ``session_search``
# is a full-text search over this conversation's own earlier sessions in its
# home's state.db (no model call).
#
# Kept out on purpose (verified against Janus 0.18.0):
#   * ``delegation`` — delegate_task passes a model-supplied ``acp_command`` and
#     ``acp_args`` to subprocess.Popen, so anything Linda reads could start a
#     program. A pre-tool hook cannot guard it: Janus lets a call through when a
#     hook fails. Needs an upstream switch that drops those arguments.
#   * ``web`` and ``vision`` — they fetch a URL the model picks, which is an
#     outbound channel for whatever she has read. ``search`` is web_search only.
TURN_TOOLSETS = (MCP_SERVER_NAME, 'skills', 'todo', 'session_search')
# Added while the merchant allows it (Settings → AI → Janus): queries go to a
# public search engine through the ``ddgs`` package installed in the Janus venv.
WEB_SEARCH_TOOLSETS = ('search',)
# Added while learning is on: ``memory`` is Janus's notes, recall and agreement
# tools, all confined to JANUS_HOME. What they write outlives the home through
# core/assistant/janus_learning.py.
LEARNING_TOOLSETS = ('memory',)

# Base environment handed to the subprocess. Everything not listed here (and not
# matching the inference-key allowlist below) is withheld — see the module
# docstring. No ``JANUS_*`` variable is inherited either: Janus takes its
# settings from the config each turn writes and its provider and model from the
# command line, and a container's ``JANUS_MODEL`` / ``JANUS_PROVIDER`` would
# override both (with a model the spend cap cannot price). ``JANUS_HOME``, the
# ephemeral prompt and the yolo flag are set by :func:`run_janus_turn` itself.
_ENV_BASE_ALLOW = (
    'PATH',
    'HOME',
    'LANG',
    'LC_ALL',
    'LC_CTYPE',
    'TZ',
    'SSL_CERT_FILE',
    'SSL_CERT_DIR',
    'REQUESTS_CA_BUNDLE',
    'CURL_CA_BUNDLE',
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'NO_PROXY',
    'http_proxy',
    'https_proxy',
    'no_proxy',
)


def janus_available() -> bool:
    return janus_cmd() is not None


def auto_approve_enabled() -> bool:
    """Whether the subprocess may execute tool calls without a prompt.

    Default **False**: yolo mode inside Janus bypasses the safety boundary
    entirely (see the module docstring), so turning it on is an explicit,
    per-deployment decision.
    """
    s = _settings()
    return bool(getattr(s, 'LINDA_JANUS_AUTO_APPROVE', False) if s else False)


def learns(conversation_key: str = '') -> bool:
    """Whether this conversation reads and writes what Janus has learned.

    Never an external agent's. Its turns run as one shared service user, so
    hydrating would hand the store's notes (and every other token's notes about
    "the person") to a caller whose token grants no such read, and what it wrote
    would be loaded into every merchant turn.
    """
    from core.assistant.gates import is_external_key

    return janus_settings.learning_enabled() and not is_external_key(conversation_key)


def turn_toolsets(conversation_key: str = '') -> tuple[str, ...]:
    """The toolsets a turn loads: the base set, web search and memory while allowed."""
    toolsets = TURN_TOOLSETS
    if janus_settings.web_search_enabled():
        toolsets += WEB_SEARCH_TOOLSETS
    if learns(conversation_key):
        toolsets += LEARNING_TOOLSETS
    return toolsets


def turn_timeout_s() -> int:
    """Settings → AI → Janus, else ``LINDA_JANUS_TIMEOUT_S``; never above the cap."""
    s = _settings()
    raw = getattr(s, 'LINDA_JANUS_TIMEOUT_S', _DEFAULT_TIMEOUT_S) if s else _DEFAULT_TIMEOUT_S
    try:
        base = max(5, int(raw))
    except (TypeError, ValueError):
        base = _DEFAULT_TIMEOUT_S
    return janus_settings.turn_timeout_s(min(base, janus_settings.MAX_TURN_TIMEOUT_S))


def _inference_env_names() -> set[str]:
    """API-key / base-URL env names the LLM providers read.

    Sourced from :mod:`core.agents.provider_registry` rather than re-listed
    here: a second copy of this list would drift from the one the platform
    actually reads, and the failure mode is a provider key that silently never
    reaches the engine.
    """
    try:
        from core.agents.provider_registry import _ENV_BASE, _ENV_KEYS

        return set(_ENV_KEYS.values()) | set(_ENV_BASE.values())
    except Exception:  # noqa: BLE001 — an import failure must not open the allowlist
        logger.debug('janus: provider env names unavailable', exc_info=True)
        return set()


def _child_env(overrides: dict[str, str]) -> dict[str, str]:
    """Allowlisted environment for the Janus subprocess."""
    allow = set(_ENV_BASE_ALLOW) | _inference_env_names()
    env = {k: v for k, v in os.environ.items() if k in allow}
    env.update(overrides)
    return env


def _open_home(conversation_key: str):
    """The conversation's home and its turn lock (None while another turn holds it)."""
    conv_home = linda_janus_home() / 'conv' / _session_id(conversation_key)
    conv_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    _maybe_prune_homes(conv_home)
    return conv_home, _lock_home(conv_home)


def run_janus_turn(**kwargs: Any) -> dict[str, Any]:
    """Run one store-agent turn on Janus and wait for it. See :func:`iter_janus_turn`."""
    for item in iter_janus_turn(**kwargs):
        if item is not None and not item.get('type'):
            return item
    return {'text': '', 'error': 'janus turn produced no result', 'duration_ms': 0}


def iter_janus_turn(
    *,
    message: str,
    conversation_key: str,
    system_prompt: str,
    timeout_s: int | None = None,
    context: dict[str, Any] | None = None,
    turn_token: str = '',
    turn_context: str = '',
    history: str = '',
    tick_s: float = 1.0,
):
    """Run one store-agent turn on Janus, yielding about every ``tick_s``.

    Each tick yields the steps Janus reported since the last one (``step`` and
    ``plan`` events, see :mod:`core.assistant.activity`), or ``None`` when there
    were none. The last item is the result: ``{text, error, duration_ms, usage,
    build}``, the only item without a ``type``. The ticks let a streaming caller show what
    Linda is doing and keep proxies from closing an idle connection.

    ``system_prompt`` should be stable from turn to turn: Janus appends it to the
    system message, ahead of the whole transcript, so a prompt that changes every
    message defeats the provider's prompt cache. What changes per message goes in
    ``turn_context`` (sent with the message), and ``history`` is sent only when a
    fresh Janus session starts — a resumed session already holds the transcript.

    ``turn_token`` is the signed identity from :mod:`core.assistant.turn_identity`.
    Without one the MCP edge refuses every call, so the turn has no store tools.
    """
    cmd = janus_cmd()
    if not cmd:
        yield {'text': '', 'error': 'janus_unavailable', 'duration_ms': 0}
        return
    # Named from the command this turn runs, so the run records the Janus that
    # answered it (AgentRun.metadata).
    build = build_of(cmd)

    timeout = turn_timeout_s() if timeout_s is None else max(5, int(timeout_s))
    started = time.monotonic()
    try:
        # The model picked for this message (validated in _provider_wiring).
        provider_args, provider_env = _provider_wiring(str((context or {}).get('provider') or ''))
    except UnsupportedProvider as e:
        yield {'text': '', 'error': f'janus cannot run on {e}', 'duration_ms': 0, 'build': build}
        return
    try:
        conv_home, lock = _open_home(conversation_key)
    except OSError as e:
        # Reported like any engine failure, so the merchant gets the friendly
        # error and the self-improvement loop gets a signal, not a stack trace.
        logger.error('janus engine home unavailable: %s', e)
        yield {
            'text': '',
            'error': f'janus home unavailable: {e}',
            'duration_ms': 0,
            'build': build,
        }
        return
    if lock is None:
        # The conversation's last turn is still running (its reader may have left).
        yield {
            'text': '',
            'error': 'janus is busy with this conversation',
            'duration_ms': 0,
            'build': build,
        }
        return
    with lock:
        mcp_url, mcp_headers = _mcp_endpoint(context)
        # The backups Janus may switch to when the turn's provider fails.
        fallbacks, fallback_env = _fallback_wiring(provider_env)
        learning = learns(conversation_key)
        _ensure_config(
            conv_home,
            mcp_url=mcp_url,
            mcp_headers=mcp_headers,
            fallbacks=fallbacks,
            learning=learning,
        )
        _prepare_home(conv_home)
        progress = activity.ProgressReader(conv_home / activity.PROGRESS_FILE)
        progress.reset()

        from core.assistant import janus_learning

        user = (context or {}).get('user')
        snapshot = None
        if learning:
            snapshot = janus_learning.hydrate(conv_home, user=user)
        else:
            janus_learning.clear(conv_home)

        env = _turn_env(conv_home, system_prompt, turn_token, {**fallback_env, **provider_env})

        # Read here, not in argv_for: that runs on the worker thread, which has no view
        # of this request's database connection (and so of the merchant's settings).
        toolsets = ','.join(turn_toolsets(conversation_key))

        def argv_for(resume_id: str) -> list[str]:
            # -Q: stdout is the answer only (no banner, query echo or screen escapes).
            # -t: see TURN_TOOLSETS — never let the default toolset load.
            text = _compose_message(message, turn_context, '' if resume_id else history)
            argv = [*cmd, 'chat', '-Q', '-q', text, '--source', 'linda']
            argv += ['-t', toolsets, *provider_args]
            return [*argv, '--resume', resume_id] if resume_id else argv

        # The subprocess wait runs in a thread; everything touching the database stays
        # on this one (hydrate above, harvest below), where the request's connection is.
        payload = None
        try:
            payload = yield from _relay_steps(
                _wait_ticking(
                    lambda: _spawn(argv_for, env, conv_home, timeout, started, conversation_key),
                    tick_s,
                ),
                progress,
            )
        finally:
            if snapshot is not None:
                if payload is not None:
                    # Also after a timeout or crash: a note saved before the failure
                    # is still something Janus learned.
                    janus_learning.harvest(
                        conv_home, snapshot, conversation_key=conversation_key, user=user
                    )
                else:
                    # The caller went away mid-turn and Janus is still writing.
                    logger.info(
                        'janus: turn abandoned; learning not harvested key=%s', conversation_key
                    )
    yield {**payload, 'build': build}


def _relay_steps(ticks, progress: activity.ProgressReader):
    """Pass the ticks on, each one carrying the steps Janus reported since the last."""
    while True:
        try:
            next(ticks)
        except StopIteration as done:
            payload = done.value
            break
        events = progress.read()
        if events:
            yield from events
        else:
            yield None
    # Steps written in the moment before Janus exited.
    yield from progress.read()
    return payload


def _wait_ticking(run, tick_s: float):
    """Run ``run()`` in a thread, yielding ``None`` every ``tick_s`` until it returns."""
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box['payload'] = run()
        except Exception as e:  # noqa: BLE001 — reported as a failed turn, never lost
            logger.exception('janus engine turn crashed')
            box['payload'] = {'text': '', 'error': f'janus turn crashed: {e}', 'duration_ms': 0}
        finally:
            # An ERROR log is recorded to the database by core.brain's handler,
            # which opens a connection on this thread; close it or it leaks.
            from django.db import connections

            connections.close_all()

    worker = threading.Thread(target=work, name='janus-turn', daemon=True)
    worker.start()
    while True:
        worker.join(tick_s)
        if not worker.is_alive():
            return box['payload']
        yield None


def _turn_env(
    conv_home: Path, system_prompt: str, turn_token: str, provider_env: dict[str, str]
) -> dict[str, str]:
    return _child_env(
        {
            **provider_env,
            TURN_TOKEN_ENV: turn_token,
            'JANUS_HOME': str(conv_home),
            # The inherited HOME (/app in the image) is not writable, and anything
            # that caches under ~ should land in this conversation's private home.
            'HOME': str(conv_home),
            'JANUS_EPHEMERAL_SYSTEM_PROMPT': system_prompt[:80_000],
            # The dashboard already collected the merchant's message, so there is
            # no TTY to prompt on. That is a reason not to STALL, not a reason to
            # auto-approve: off unless the deployment opted in.
            'JANUS_YOLO_MODE': '1' if auto_approve_enabled() else '0',
        }
    )


def _compose_message(message: str, turn_context: str, history: str) -> str:
    """The -q message: context for this message, a recap when the session is new,
    then the merchant's words."""
    message = message[:10_000]
    parts = [p for p in (turn_context.strip()[:20_000], history.strip()[:20_000]) if p]
    if not parts:
        return message
    return (
        '[Context for this message, gathered by the store. The merchant did not write it.]\n'
        + '\n\n'.join(parts)
        + f"\n\n[The merchant's message]\n{message}"
    )


# Seconds coreutils ``timeout`` waits between its TERM and its KILL.
_KILL_AFTER_S = 5


def _timeout_bin() -> str:
    """coreutils ``timeout`` where the host has it (the image does, macOS does not).

    ``subprocess.run(timeout=…)`` stops Janus only while this process lives, and
    gunicorn recycles a worker at ``--max-requests``: Janus then ran on with
    nothing to stop it. Started under ``timeout``, Janus and what it started are
    stopped at the deadline whoever is still around.
    """
    return shutil.which('timeout') or ''


def _stopped_at_deadline(returncode: int, ran_s: float, limit_s: int) -> bool:
    """Whether ``timeout`` ended the command, from how the wrapper itself ended.

    It exits 124 after its TERM. Its KILL goes to the whole process group, the
    wrapper included, so Python then sees signal 9 (a shell reports 137). A kill
    before the deadline is someone else's (out of memory).
    """
    return returncode == 124 or (returncode in (137, -signal.SIGKILL) and ran_s >= limit_s)


def _spawn(
    argv_for,
    env: dict[str, str],
    conv_home: Path,
    timeout: int,
    started: float,
    conversation_key: str,
) -> dict[str, Any]:
    resume_id = _stored_session_id(conv_home)
    counted = _counted_usage(conv_home)
    # Always the conversation's own home. Janus auto-injects AGENTS.md / SOUL.md
    # from its working directory, so running inside an engine source checkout
    # would feed that project's developer instructions to the store agent.
    cwd = str(conv_home)
    spawned_at = time.time()
    wrapper = _timeout_bin()
    for _attempt in (0, 1):
        remaining = max(1, timeout - int(time.monotonic() - started))
        argv = argv_for(resume_id)
        if wrapper:
            argv = [wrapper, '-k', str(_KILL_AFTER_S), str(remaining), *argv]
        began = time.monotonic()
        try:
            proc = subprocess.run(  # noqa: S603 — cmd is resolved from settings/PATH
                argv,
                env=env,
                capture_output=True,
                text=True,
                # Longer than the wrapper's own limit, so the wrapper is the one
                # that stops Janus: Python killing the wrapper would orphan it.
                timeout=remaining + 2 * _KILL_AFTER_S if wrapper else remaining,
                cwd=cwd,
                check=False,
            )
        except subprocess.TimeoutExpired:
            proc = None
        except OSError as e:
            logger.error('janus engine spawn failed: %s', e)
            return {'text': '', 'error': f'janus spawn failed: {e}', 'duration_ms': 0}
        if proc is None or (
            wrapper and _stopped_at_deadline(proc.returncode, time.monotonic() - began, remaining)
        ):
            # ERROR, not WARNING: the merchant got no reply, and the error log keeps a
            # warning only while detailed capture is on.
            logger.error('janus engine timed out after %ss key=%s', timeout, conversation_key)
            # The longest turns are the ones that time out, and the daily spend
            # cap reads `usage`: count what the home spent before the kill.
            return {
                'text': '',
                'error': f'janus timed out after {timeout}s',
                'duration_ms': timeout * 1000,
                'usage': _bill(
                    conv_home, counted, resume_id or _session_started_since(conv_home, spawned_at)
                ),
            }
        if wrapper and proc.returncode in (125, 126, 127):
            # The wrapper could not start Janus (missing, not executable). Reported as
            # the same failure as without it: its own text says "timeout".
            logger.error('janus engine spawn failed: %s', (proc.stderr or '').strip()[:400])
            return {
                'text': '',
                'error': f'janus spawn failed: exit {proc.returncode}',
                'duration_ms': 0,
            }
        if proc.returncode != 0 and resume_id and 'Session not found' in (proc.stderr or ''):
            # The stored id outlived its state.db. Janus exits before any model
            # call on this path, so starting a fresh session (with the history
            # recap) costs nothing.
            _forget_session_id(conv_home)
            resume_id = ''
            continue
        break

    text = _strip_notices(proc.stdout or '')
    stderr = proc.stderr or ''
    if proc.returncode == 0 and not text and not _SESSION_LINE_RE.search(stderr):
        # Janus exited cleanly but printed neither the reply nor its session id:
        # something swapped its output streams. The reply is still in state.db.
        recovered_sid, text = _recover_reply(conv_home, resume_id, spawned_at)
        if recovered_sid:
            logger.warning('janus: reply recovered from state.db key=%s', conversation_key)
            stderr = f'{stderr}\nsession_id: {recovered_sid}'
    usage = _bill(conv_home, counted, _remember_session_id(conv_home, stderr))
    duration = int((time.monotonic() - started) * 1000)
    result = _turn_result(proc.returncode, text, _SESSION_LINE_RE.sub('', stderr).strip())
    return {**result, 'duration_ms': duration, 'usage': usage}


def _turn_result(returncode: int, text: str, err: str) -> dict[str, str]:
    """The reply or the failure, from what the Janus process returned."""
    if returncode != 0:
        # A crash AFTER partial output is still a crash. Returning the partial
        # text as a completed turn hides the failure from the merchant, from the
        # transcript, and from the self-improvement loop.
        logger.error(
            'janus engine rc=%s stdout_head=%s stderr=%s', returncode, text[:200], err[:400]
        )
        reason = err[:500] or f'janus exit {returncode}'
        if text:
            reason = f'{reason} (crashed after {len(text)} chars of partial output)'
        return {'text': '', 'error': reason}
    if not text or text == '(empty)':
        # Janus exits 0 with nothing to say when the model returned only hidden
        # reasoning, or every provider retry failed; the merchant must not get a
        # blank bubble recorded as Linda's answer.
        return {'text': '', 'error': 'janus returned no reply'}
    if text.startswith('{'):
        # Parse the WHOLE envelope — sniffing for the key in a fixed-size head
        # means a longer envelope renders raw JSON to the merchant as Linda's
        # answer.
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(payload, dict):
                text = str(payload.get('final_response') or payload.get('text') or text)
    return {'text': text, 'error': ''}
