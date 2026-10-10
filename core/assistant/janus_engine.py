"""Store agent engine: Janus (magnetoid/janus), isolated from Django.

Janus **is** the agent. Linda is the merchant-facing brand only. Morpheus and
Janus both ship top-level packages named ``plugins`` / ``tools``, so Janus MUST
run in a subprocess (own venv / own sys.path). Each conversation home is seeded
with bundled Morpheus ecommerce skills (``core/assistant/janus_skills``).

Discovery order for the binary:
  1. ``settings.JANUS_BIN`` / ``JANUS_BIN``
  2. a newer Janus the store installed itself from GitHub, after it passed the
     contract (:mod:`core.assistant.janus_runtime`)
  3. ``janus`` on PATH (the image's)
  4. ``<JANUS_ENGINE_ROOT>/.venv/bin/janus`` then ``venv/bin/janus``
  5. ``~/.janus/janus-agent`` source checkout (``python cli.py``)

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

import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from core.assistant import activity, janus_settings
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
MCP_SERVER_NAME = 'morpheus_admin'
TURN_TOOLSETS = (MCP_SERVER_NAME, 'skills', 'todo', 'session_search')
# Added while the merchant allows it (Settings → AI → Janus): queries go to a
# public search engine through the ``ddgs`` package installed in the Janus venv.
WEB_SEARCH_TOOLSETS = ('search',)
# Added while learning is on: ``memory`` is Janus's notes, recall and agreement
# tools, all confined to JANUS_HOME. What they write outlives the home through
# core/assistant/janus_learning.py.
LEARNING_TOOLSETS = ('memory',)

# Tool-calling iterations per message. Janus defaults to 90; a turn must still end
# inside its time limit, and a step measured ~7s on prod (DeepSeek plus an MCP
# call), so 30 steps fit the four-minute default.
MAX_TOOL_TURNS = 30

# Janus prints ``session_id: <id>`` to stderr in quiet mode. Stored per
# conversation and passed back with ``--resume``: a bare ``--continue`` looks up
# the newest session whose source is ``cli``, never ``linda``, so it failed every
# follow-up message. Validated before it reaches argv.
_SESSION_FILE = 'janus_session.json'
_SESSION_ID_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
_SESSION_LINE_RE = re.compile(r'^session_id:\s*(\S+)\s*$', re.M)

# A resumed session sends its whole transcript on every model call, and Janus only
# compresses at half the model's context (500K tokens for a 1M model), so a
# conversation that never starts over costs more on every message. Start a fresh
# session, with a short recap of recent history, after this many turns or this
# long idle. A fresh session also picks up notes learned in other conversations.
SESSION_MAX_TURNS = 20
SESSION_IDLE_S = 6 * 3600

# Base environment handed to the subprocess. Everything not listed here (and not
# matching the inference-key allowlist below) is withheld — see the module
# docstring. ``JANUS_HOME`` / the ephemeral prompt / the yolo flag are set
# explicitly by :func:`run_janus_turn` and deliberately NOT inherited.
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

# Janus env vars the parent sets itself; inheriting them would let a container
# env override a decision this module is supposed to own.
_ENV_JANUS_RESERVED = frozenset(
    {'JANUS_HOME', 'JANUS_YOLO_MODE', 'JANUS_EPHEMERAL_SYSTEM_PROMPT', 'JANUS_INTERACTIVE'}
)


def _settings():
    try:
        from django.conf import settings

        return settings
    except Exception:  # noqa: BLE001
        return None


def engine_root() -> Path | None:
    s = _settings()
    raw = (getattr(s, 'JANUS_ENGINE_ROOT', '') if s else '') or os.environ.get(
        'JANUS_ENGINE_ROOT', ''
    )
    candidates = []
    if raw:
        candidates.append(Path(raw).expanduser())
    candidates.append(Path.home() / '.janus' / 'janus-agent')
    if s is not None:
        candidates.append(Path(s.BASE_DIR) / 'vendor' / 'janus')
    for p in candidates:
        if (p / 'cli.py').is_file() or (p / 'run_agent.py').is_file():
            return p
    return None


def janus_cmd() -> list[str] | None:
    s = _settings()
    explicit = (getattr(s, 'JANUS_BIN', '') if s else '') or os.environ.get('JANUS_BIN', '')
    if explicit:
        return [explicit]
    # A newer Janus the store installed from GitHub and checked against the
    # contract (core/assistant/janus_runtime.py); else the image's.
    from core.assistant import janus_runtime

    found = janus_runtime.active_bin() or shutil.which('janus')
    if found:
        return [found]
    return _source_checkout_cmd()


def _source_checkout_cmd() -> list[str] | None:
    """A Janus source checkout (``JANUS_ENGINE_ROOT``, ``~/.janus/janus-agent``)."""
    root = engine_root()
    if root is None:
        return None
    for rel in ('.venv/bin/janus', 'venv/bin/janus'):
        bin_path = root / rel
        if bin_path.is_file():
            return [str(bin_path)]
    cli = root / 'cli.py'
    if cli.is_file():
        py = root / '.venv/bin/python'
        if not py.is_file():
            py = root / 'venv/bin/python'
        interpreter = str(py) if py.is_file() else sys.executable
        return [interpreter, str(cli)]
    return None


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


def turn_toolsets() -> tuple[str, ...]:
    """The toolsets a turn loads: the base set, web search and memory while allowed."""
    toolsets = TURN_TOOLSETS
    if janus_settings.web_search_enabled():
        toolsets += WEB_SEARCH_TOOLSETS
    if janus_settings.learning_enabled():
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


def linda_janus_home() -> Path:
    """Where conversation homes live: ``LINDA_JANUS_HOME``, else a private temp dir.

    Never under the app tree: in the production image ``/app`` is owned by root
    and not writable by the app user, so ``BASE_DIR/.linda-janus`` raised
    PermissionError on every real turn from v0.63.0 to v0.64.1. And never under
    ``/app/media`` — the one writable mount — because media is publicly served and
    each home holds the conversation's ``state.db``. The temp dir is wiped on
    redeploy, and nothing in it has to survive: what Janus learns is kept in the
    database (:mod:`core.assistant.janus_learning`), so no deployment needs a
    disk volume.
    """
    s = _settings()
    configured = (getattr(s, 'LINDA_JANUS_HOME', '') if s else '') or os.environ.get(
        'LINDA_JANUS_HOME', ''
    )
    home = (
        Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / 'linda-janus'
    )
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def bundled_skills_dir() -> Path:
    """Repo-shipped Morpheus ecommerce skills (not the operator ``~/.janus``)."""
    s = _settings()
    if s is not None:
        return Path(s.BASE_DIR) / 'core' / 'assistant' / 'janus_skills'
    return Path(__file__).resolve().parent / 'janus_skills'


def bundled_skill_names() -> list[str]:
    root = bundled_skills_dir()
    if not root.is_dir():
        return []
    names = {p.parent.name for p in root.rglob('SKILL.md') if p.is_file()}
    return sorted(names)


# A conversation home nobody has used for this long is removed. Each chat has
# its own home, so homes grow with chats; nothing in one has to survive (what
# Janus learns is harvested into the DB every turn, and a reopened chat without
# its home starts a fresh session that gets the recap from stored messages).
HOME_PRUNE_AFTER_S = 7 * 24 * 3600
_PRUNE_EVERY_S = 3600
_last_prune = 0.0


def prune_idle_homes(conv_root: Path, *, keep: Path, now: float | None = None) -> int:
    """Remove ``linda-*`` homes under `conv_root` idle past HOME_PRUNE_AFTER_S."""
    now = time.time() if now is None else now
    removed = 0
    for home in conv_root.iterdir():
        if home == keep or home.is_symlink() or not home.is_dir():
            continue
        if not home.name.startswith('linda-'):
            continue
        try:
            last_used = max(p.stat().st_mtime for p in (home, home / 'state.db') if p.exists())
        except (OSError, ValueError):
            continue
        if now - last_used > HOME_PRUNE_AFTER_S:
            shutil.rmtree(home, ignore_errors=True)
            removed += 1
    return removed


def _maybe_prune_homes(current: Path) -> None:
    """At most hourly per process; a failure here never costs a turn."""
    global _last_prune  # noqa: PLW0603 — a process-wide throttle
    if time.time() - _last_prune < _PRUNE_EVERY_S:
        return
    _last_prune = time.time()
    try:
        prune_idle_homes(current.parent, keep=current)
    except OSError:
        logger.debug('janus: home prune failed', exc_info=True)


def _session_id(conversation_key: str) -> str:
    digest = hashlib.sha256(conversation_key.encode()).hexdigest()[:12]
    return f'linda-{digest}'


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
    env = {
        k: v
        for k, v in os.environ.items()
        if (k in allow or k.startswith('JANUS_')) and k not in _ENV_JANUS_RESERVED
    }
    env.update(overrides)
    return env


def _config_text(
    mcp_url: str,
    headers: dict[str, str] | None = None,
    progress_path: Path | None = None,
    *,
    fallbacks: list[dict[str, str]] | None = None,
) -> str:
    mcp_block = ''
    if mcp_url:
        # JSON strings are valid YAML scalars, so values need no hand-escaping.
        extra = ''.join(
            f'\n      {name}: {json.dumps(value)}'
            for name, value in sorted((headers or {}).items())
        )
        # The credential is the per-turn token from the environment, resolved by
        # Janus at connect time. Nothing secret is written to this file.
        mcp_block = f"""
mcp_servers:
  {MCP_SERVER_NAME}:
    url: {json.dumps(mcp_url)}
    headers:
      Authorization: "Bearer ${{{TURN_TOKEN_ENV}}}"{extra}
    timeout: 60
    # Reads in one step run together instead of one after another.
    supports_parallel_tool_calls: true
    # Morpheus serves tools only; the resource and prompt helpers are dead weight.
    tools:
      resources: false
      prompts: false
"""
    external = ''
    skills_dir = bundled_skills_dir()
    if skills_dir.is_dir() and janus_settings.bundled_skills_enabled():
        quoted = str(skills_dir).replace('\\', '/')
        external = f'\n  external_dirs:\n    - "{quoted}"'
    learning = 'true' if janus_settings.learning_enabled() else 'false'
    # guard_agent_created: Janus scans a skill the agent writes only when this
    #   resolves on, and its "auto" default is OFF under `janus chat -q`.
    # inline_shell: a skill could otherwise run shell snippets when it loads.
    # curator: moves skills into skills/.archive, which is not kept, so a
    #   learned skill would silently disappear.
    # memory: off together with learning, so no stale notes are loaded.
    # nudge_interval / creation_nudge_interval 0: Janus's background review (a
    #   thread started every 10 messages or tool steps) silences itself with
    #   contextlib.redirect_stdout/stderr, which swaps the streams for the whole
    #   process, so the reply and session id printed meanwhile went to /dev/null
    #   and the merchant got "no reply" (live, v0.68.0). Linda learns through
    #   explicit memory and skill calls instead.
    # reasoning_effort: the provider default for a reasoning model is "high".
    # api_max_retries: Janus retries 3x with backoff, which spends the whole turn
    #   budget on a provider that is down.
    # web.backend: DuckDuckGo through the free ddgs package, named so a key that
    #   reaches the engine some other way can never switch Linda to a paid backend.
    # hooks: one line per step into the home's progress file, for the chat
    #   (core/assistant/activity.py). A display only: Janus ignores a failed hook.
    hooks = activity.hooks_config(progress_path) if progress_path is not None else ''
    # fallback_providers: backups Janus switches to when the main provider fails
    #   a call (see _fallback_wiring); their keys come with the turn's env.
    fallback_block = ''
    if fallbacks:
        rows = ''.join(
            f'\n  - provider: {json.dumps(f["provider"])}\n    model: {json.dumps(f["model"])}'
            for f in fallbacks
        )
        fallback_block = f'fallback_providers:{rows}\n'
    return f"""# Auto-generated store agent home. Merchant-facing name is Linda.
security:
  tirith_enabled: false
model:
  default: {os.environ.get('JANUS_INFERENCE_MODEL') or 'auto'}
agent:
  max_turns: {janus_settings.max_tool_turns(MAX_TOOL_TURNS)}
  reasoning_effort: {janus_settings.reasoning_effort()}
  api_max_retries: 1
{mcp_block}
skills:
  guard_agent_created: true
  inline_shell: false
  creation_nudge_interval: 0{external}
curator:
  enabled: false
memory:
  memory_enabled: {learning}
  user_profile_enabled: {learning}
  nudge_interval: 0
web:
  backend: ddgs
{fallback_block}{hooks}"""


# Janus reads its identity from SOUL.md in the home and seeds its own ("You are
# Janus Agent…") when the file is missing.
_SOUL = (
    'You are Linda, the AI assistant a merchant uses to run their online store. '
    'You work only for this store. You never mention the engine or framework that runs you.\n'
)
# Stops Janus copying its ~70 general-purpose skills into the home.
_NO_BUNDLED_SKILLS = '.no-bundled-skills'


def _prepare_home(home: Path) -> None:
    """Linda's identity, and no general-purpose Janus skills in her prompt."""
    from core.assistant import janus_learning

    with contextlib.suppress(OSError):
        soul = home / 'SOUL.md'
        if not soul.is_file() or soul.read_text(encoding='utf-8') != _SOUL:
            soul.write_text(_SOUL, encoding='utf-8')
        (home / _NO_BUNDLED_SKILLS).touch(exist_ok=True)
    try:
        janus_learning.remove_bundled_skills(home)
    except Exception:  # noqa: BLE001 — a leftover skill costs tokens, not the turn
        logger.debug('janus: bundled skill cleanup skipped', exc_info=True)


def _ensure_config(
    home: Path,
    *,
    mcp_url: str = '',
    mcp_headers: dict[str, str] | None = None,
    fallbacks: list[dict[str, str]] | None = None,
) -> Path:
    """Write (or REWRITE) the store-agent Janus config.

    Rewriting matters: this file is per-conversation, so a write-once version
    pins whatever token and URL existed when the conversation started. A rotated
    MCP token would then never reach an existing conversation, and the stale one
    would sit on disk in one copy per conversation.
    """
    cfg_path = home / 'config.yaml'
    desired = _config_text(mcp_url, mcp_headers, home / activity.PROGRESS_FILE, fallbacks=fallbacks)
    try:
        current = cfg_path.read_text(encoding='utf-8')
    except OSError:
        current = None
    if current != desired:
        cfg_path.write_text(desired, encoding='utf-8')
    with contextlib.suppress(OSError):
        cfg_path.chmod(0o600)
    return cfg_path


def _default_host() -> str:
    """The first concrete host the deployment serves (no wildcards or loopback)."""
    s = _settings()
    for entry in getattr(s, 'ALLOWED_HOSTS', None) or []:
        host = str(entry).strip()
        concrete = host and host != '*' and not host.startswith('.')
        if concrete and host not in ('localhost', '127.0.0.1'):
            return host
    return ''


def _mcp_endpoint(context: dict[str, Any] | None) -> tuple[str, dict[str, str]]:
    """Where the subprocess reaches the store's MCP server, and the headers it needs.

    Janus runs in the same container as the web server, so it calls loopback
    instead of the public URL: no round trip out through Cloudflare and back
    (measured on prod: 0.03s against 0.25s per call). Loopback alone fails,
    though. ``SECURE_SSL_REDIRECT`` answers plain http with a 301, a redirect
    drops the JSON-RPC body, and ``127.0.0.1`` is not in ``ALLOWED_HOSTS``. So the
    call names the store's real host and the https scheme the proxy chain would
    otherwise have set.
    """
    s = _settings()
    explicit = (getattr(s, 'LINDA_MCP_URL', '') if s else '') or os.environ.get('LINDA_MCP_URL', '')
    if explicit:
        # Exactly one trailing slash. The MCP endpoint is a POST with a JSON-RPC
        # body, and Django's APPEND_SLASH redirect DROPS that body — so a URL
        # missing the slash fails every tool call.
        return explicit.rstrip('/') + '/', {}
    host, secure = '', False
    request = (context or {}).get('request')
    if request is not None:
        try:
            host, secure = request.get_host(), request.is_secure()
        except Exception:  # noqa: BLE001 — fall back to the configured host
            logger.debug('janus: could not read host from request', exc_info=True)
    if not host:
        host = _default_host()
        secure = bool(getattr(s, 'SECURE_SSL_REDIRECT', False)) if s else False
    headers: dict[str, str] = {}
    if host:
        headers['Host'] = host
    if secure:
        headers['X-Forwarded-Proto'] = 'https'
    return f'http://127.0.0.1:{os.environ.get("PORT") or "8000"}/mcp/admin/v1/', headers


# Morpheus provider name → (Janus ``--provider`` id, API-key env var, base-URL env
# var), from janus_cli/auth.py's ProviderConfig table. Janus's ``auto`` routes to
# OpenRouter whenever OPENAI_API_KEY is set, and it never sees a key that lives
# in the dashboard rather than the environment. Production had both at once: the
# active provider was DeepSeek with its key in the dashboard, so every turn went
# to the wrong provider with the wrong key.
_JANUS_PROVIDERS = {
    'openai': ('openai-api', 'OPENAI_API_KEY', 'OPENAI_BASE_URL'),
    'anthropic': ('anthropic', 'ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL'),
    'gemini': ('gemini', 'GEMINI_API_KEY', 'GEMINI_BASE_URL'),
    'deepseek': ('deepseek', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL'),
    'grok': ('xai', 'XAI_API_KEY', 'XAI_BASE_URL'),
}


def pinnable_providers() -> tuple[str, ...]:
    """Morpheus provider names Janus can be pinned to (Settings → AI → Janus)."""
    return tuple(_JANUS_PROVIDERS)


_PROVIDER_LABELS = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
    'gemini': 'Gemini',
    'deepseek': 'DeepSeek',
    'grok': 'Grok',
}


def _configured(name: str):
    """(Janus spec, provider config) for a provider Janus can run that has a key."""
    spec = _JANUS_PROVIDERS.get(name)
    if spec is None:
        return None
    try:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config(name)
    except Exception:  # noqa: BLE001 — an unreadable provider is simply not offered
        return None
    return (spec, cfg) if cfg.api_key and cfg.model else None


def selectable_providers() -> list[dict[str, str]]:
    """Providers a message can be sent to: Janus runs them, they have a key, and
    their model is priced — an unpriced model would escape the daily spend cap."""
    from core.agents.pricing import is_priced

    out = []
    for name in _JANUS_PROVIDERS:
        found = _configured(name)
        if found is None or not is_priced(found[1].model):
            continue
        model = found[1].model
        out.append(
            {'name': name, 'model': model, 'label': f'{_PROVIDER_LABELS.get(name, name)} · {model}'}
        )
    return out


def _fallback_wiring(primary_env: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Backup providers for `fallback_providers` (Settings → AI → Janus) and their keys.

    Janus switches to the next one when the main provider fails a call (quota,
    rate limit, overload). Keys stored in the dashboard never reach Janus's own
    environment, so each backup's key travels with the turn like the main one.
    The main provider is never its own backup.
    """
    from core.agents.pricing import is_priced

    entries: list[dict[str, str]] = []
    env: dict[str, str] = {}
    for name in janus_settings.fallback_providers():
        found = _configured(name)
        if found is None:
            continue
        (janus_id, key_var, base_var), cfg = found
        if key_var in primary_env or key_var in env or not is_priced(cfg.model):
            continue
        entries.append({'provider': janus_id, 'model': cfg.model})
        env[key_var] = cfg.api_key
        if cfg.base_url:
            env[base_var] = cfg.base_url
    return entries, env


def _provider_wiring(choice: str = '') -> tuple[list[str], dict[str, str]]:
    """CLI args + env that pin Janus to its provider.

    The provider picked for this message in the composer (when it is one of
    :func:`selectable_providers`), else the one pinned on Settings → AI → Janus,
    else the store's active AI provider.
    """
    custom = janus_settings.custom_provider()
    picked = (
        _configured(choice)
        if choice and choice in {p['name'] for p in selectable_providers()}
        else None
    )
    if picked is not None:
        name, model, api_key, base_url = (
            choice,
            picked[1].model,
            picked[1].api_key,
            picked[1].base_url,
        )
    elif custom is not None:
        name, model, api_key, base_url = (
            custom['provider'],
            custom['model'],
            custom['api_key'],
            custom['base_url'],
        )
    else:
        try:
            from core.agents.provider_registry import get_active_provider_name, get_provider_config

            name = get_active_provider_name()
            cfg = get_provider_config(name)
        except Exception:  # noqa: BLE001 — fall back to Janus's own resolution
            logger.warning(
                'janus: provider config unavailable; Janus will auto-select', exc_info=True
            )
            return [], {}
        model, api_key, base_url = cfg.model, cfg.api_key, cfg.base_url
    spec = _JANUS_PROVIDERS.get(name)
    if spec is None or not api_key:
        logger.warning('janus: no provider mapping for %r; Janus will auto-select', name)
        return [], {}
    janus_id, key_var, base_var = spec
    args = ['--provider', janus_id]
    if model:
        args += ['-m', model]
    env = {key_var: api_key}
    if base_url:
        env[base_var] = base_url
    return args, env


def _session_meta(conv_home: Path) -> dict[str, Any]:
    try:
        meta = json.loads((conv_home / _SESSION_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _stored_session_id(conv_home: Path) -> str:
    """The session to resume, or '' to start a fresh one."""
    meta = _session_meta(conv_home)
    sid = str(meta.get('id') or '')
    if not _SESSION_ID_RE.match(sid):
        return ''
    try:
        turns, last_at = int(meta.get('turns') or 0), float(meta.get('last_at') or 0)
    except (TypeError, ValueError):
        return ''
    if turns >= SESSION_MAX_TURNS or time.time() - last_at > SESSION_IDLE_S:
        return ''
    return sid


def _remember_session_id(conv_home: Path, stderr: str) -> str:
    match = _SESSION_LINE_RE.search(stderr)
    if not (match and _SESSION_ID_RE.match(match.group(1))):
        return ''
    sid = match.group(1)
    meta = _session_meta(conv_home)
    turns = int(meta.get('turns') or 0) + 1 if meta.get('id') == sid else 1
    with contextlib.suppress(OSError):
        (conv_home / _SESSION_FILE).write_text(
            json.dumps({'id': sid, 'turns': turns, 'last_at': time.time()}), encoding='utf-8'
        )
    return sid


def _forget_session_id(conv_home: Path) -> None:
    with contextlib.suppress(OSError):
        (conv_home / _SESSION_FILE).unlink()


_USAGE_COLUMNS = (
    'input_tokens',
    'output_tokens',
    'cache_read_tokens',
    'cache_write_tokens',
    'reasoning_tokens',
    'api_call_count',
    'estimated_cost_usd',
)


def _session_usage(conv_home: Path, session_id: str) -> dict[str, Any]:
    """Janus's running token and cost totals for one session, from its state.db."""
    db = conv_home / 'state.db'
    if not session_id or not db.is_file():
        return {}
    try:
        with contextlib.closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)) as conn:
            row = conn.execute(
                f'SELECT model, {", ".join(_USAGE_COLUMNS)} FROM sessions WHERE id = ?',  # noqa: S608 — fixed column list  # nosec B608
                (session_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.debug('janus: usage unreadable', exc_info=True)
        return {}
    if row is None:
        return {}
    return {'model': row[0] or '', **{k: row[i + 1] or 0 for i, k in enumerate(_USAGE_COLUMNS)}}


def _session_started_since(conv_home: Path, since: float) -> str:
    """The Linda session Janus started at or after `since`, or ''."""
    db = conv_home / 'state.db'
    if not db.is_file():
        return ''
    try:
        with contextlib.closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)) as conn:
            row = conn.execute(
                "SELECT id FROM sessions WHERE source = 'linda' AND started_at >= ? "
                'ORDER BY started_at DESC LIMIT 1',
                (since,),
            ).fetchone()
    except sqlite3.Error:
        logger.debug('janus: session lookup failed', exc_info=True)
        return ''
    return str(row[0]) if row and _SESSION_ID_RE.match(str(row[0] or '')) else ''


def _recover_reply(conv_home: Path, resume_id: str, since: float) -> tuple[str, str]:
    """The session and last assistant reply this turn wrote to state.db, if any."""
    db = conv_home / 'state.db'
    if not db.is_file():
        return '', ''
    try:
        with contextlib.closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)) as conn:
            row = conn.execute(
                'SELECT m.session_id, m.content FROM messages m JOIN sessions s ON s.id = m.session_id '
                "WHERE s.source = 'linda' AND m.role = 'assistant' AND m.timestamp >= ? "
                "AND COALESCE(m.content, '') != '' AND (s.id = ? OR s.started_at >= ?) "
                'ORDER BY m.id DESC LIMIT 1',
                (since, resume_id, since),
            ).fetchone()
    except sqlite3.Error:
        logger.debug('janus: reply recovery failed', exc_info=True)
        return '', ''
    if not row or not _SESSION_ID_RE.match(str(row[0] or '')):
        return '', ''
    return str(row[0]), _strip_notices(str(row[1]))


def _turn_usage(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """What this turn added to a session's totals (the row accumulates across resumes)."""
    if not after:
        return {}
    usage = {k: max(0, (after.get(k) or 0) - (before.get(k) or 0)) for k in _USAGE_COLUMNS}
    usage['model'] = after.get('model') or ''
    return usage


# Status lines Janus prints to stdout even under -Q, which would otherwise be
# glued onto the answer.
_NOTICE_PREFIXES = ('⚠️  Reached maximum iterations', '❌ All API retries exhausted')


def _strip_notices(stdout: str) -> str:
    lines = [ln for ln in stdout.splitlines() if not ln.lstrip().startswith(_NOTICE_PREFIXES)]
    return '\n'.join(lines).strip()


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
    were none. The last item is the result: ``{text, error, duration_ms, usage}``,
    the only item without a ``type``. The ticks let a streaming caller show what
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

    timeout = turn_timeout_s() if timeout_s is None else max(5, int(timeout_s))
    started = time.monotonic()
    try:
        conv_home = linda_janus_home() / 'conv' / _session_id(conversation_key)
        conv_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        _maybe_prune_homes(conv_home)
    except OSError as e:
        # Reported like any engine failure, so the merchant gets the friendly
        # error and the self-improvement loop gets a signal, not a stack trace.
        logger.warning('janus engine home unavailable: %s', e)
        yield {'text': '', 'error': f'janus home unavailable: {e}', 'duration_ms': 0}
        return
    mcp_url, mcp_headers = _mcp_endpoint(context)
    # The model picked for this message (validated in _provider_wiring), and the
    # backups Janus may switch to when that provider fails.
    provider_args, provider_env = _provider_wiring(str((context or {}).get('provider') or ''))
    fallbacks, fallback_env = _fallback_wiring(provider_env)
    _ensure_config(conv_home, mcp_url=mcp_url, mcp_headers=mcp_headers, fallbacks=fallbacks)
    _prepare_home(conv_home)
    progress = activity.ProgressReader(conv_home / activity.PROGRESS_FILE)
    progress.reset()

    from core.assistant import janus_learning

    user = (context or {}).get('user')
    snapshot = None
    if janus_settings.learning_enabled():
        snapshot = janus_learning.hydrate(conv_home, user=user)
    else:
        janus_learning.clear(conv_home)

    env = _turn_env(conv_home, system_prompt, turn_token, {**fallback_env, **provider_env})

    # Read here, not in argv_for: that runs on the worker thread, which has no view
    # of this request's database connection (and so of the merchant's settings).
    toolsets = ','.join(turn_toolsets())

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
    yield payload


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


def _spawn(
    argv_for,
    env: dict[str, str],
    conv_home: Path,
    timeout: int,
    started: float,
    conversation_key: str,
) -> dict[str, Any]:
    resume_id = _stored_session_id(conv_home)
    usage_before = _session_usage(conv_home, resume_id)
    # Always the conversation's own home. Janus auto-injects AGENTS.md / SOUL.md
    # from its working directory, so running inside an engine source checkout
    # would feed that project's developer instructions to the store agent.
    cwd = str(conv_home)
    spawned_at = time.time()
    for _attempt in (0, 1):
        remaining = max(1, timeout - int(time.monotonic() - started))
        try:
            proc = subprocess.run(  # noqa: S603 — cmd is resolved from settings/PATH
                argv_for(resume_id),
                env=env,
                capture_output=True,
                text=True,
                timeout=remaining,
                cwd=cwd,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.warning('janus engine timed out after %ss key=%s', timeout, conversation_key)
            # The longest turns are the ones that time out, and the daily spend
            # cap reads `usage`: count what the session spent before the kill.
            killed = resume_id or _session_started_since(conv_home, spawned_at)
            return {
                'text': '',
                'error': f'janus timed out after {timeout}s',
                'duration_ms': timeout * 1000,
                'usage': _turn_usage(
                    usage_before if killed == resume_id else {},
                    _session_usage(conv_home, killed),
                ),
            }
        except OSError as e:
            logger.warning('janus engine spawn failed: %s', e)
            return {'text': '', 'error': f'janus spawn failed: {e}', 'duration_ms': 0}
        if proc.returncode != 0 and resume_id and 'Session not found' in (proc.stderr or ''):
            # The stored id outlived its state.db. Janus exits before any model
            # call on this path, so starting a fresh session (with the history
            # recap) costs nothing.
            _forget_session_id(conv_home)
            resume_id, usage_before = '', {}
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
    session = _remember_session_id(conv_home, stderr)
    if session != resume_id:
        usage_before = {}
    usage = _turn_usage(usage_before, _session_usage(conv_home, session))
    duration = int((time.monotonic() - started) * 1000)
    result = _turn_result(proc.returncode, text, _SESSION_LINE_RE.sub('', stderr).strip())
    return {**result, 'duration_ms': duration, 'usage': usage}


def _turn_result(returncode: int, text: str, err: str) -> dict[str, str]:
    """The reply or the failure, from what the Janus process returned."""
    if returncode != 0:
        # A crash AFTER partial output is still a crash. Returning the partial
        # text as a completed turn hides the failure from the merchant, from the
        # transcript, and from the self-improvement loop.
        logger.warning(
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
