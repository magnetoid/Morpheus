"""A conversation's Janus home: where it lives, the store skills staged into it,
the config and identity each turn writes there, how the subprocess reaches the
store's MCP server from it, and the lock that keeps one turn in a home at a time.

A leaf of :mod:`core.assistant.janus_engine`, which re-exports every name here.
The functions in this file read each other here: a test that replaces one of them
for another patches this module, not the engine.
The one name the engine does not re-export is ``_last_prune``: it is rebound, so
it is read and written here only.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from core.assistant import activity, janus_settings
from core.assistant.janus_binary import _settings
from core.assistant.turn_identity import ENV_VAR as TURN_TOKEN_ENV

logger = logging.getLogger('morpheus.assistant.janus')

# The MCP server name in the generated config. It is also the first toolset a
# turn loads (``janus_engine.TURN_TOOLSETS``, where the boundary is explained).
MCP_SERVER_NAME = 'morpheus_admin'

# Tool-calling iterations per message. Janus defaults to 90; a turn must still end
# inside its time limit, and a step measured ~7s on prod (DeepSeek plus an MCP
# call), so 30 steps fit the four-minute default.
MAX_TOOL_TURNS = 30


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


# Each turn's copy of the store skills, inside the conversation home: core's
# (``core``) and every active app's ``janus_skills/`` folder (under its name).
STORE_SKILLS_DIR = 'store-skills'
_SKILL_FILE_MAX = 200_000


def app_skill_dirs() -> list[tuple[str, Path]]:
    """``(app name, folder)`` for every active app that ships ``janus_skills/``."""
    from plugins.registry import app_registry

    found = []
    for plugin in app_registry.active_plugins():
        module = sys.modules.get(type(plugin).__module__)
        path = getattr(module, '__file__', None)
        if not path:
            continue
        skills = Path(path).resolve().parent / 'janus_skills'
        if skills.is_dir() and not skills.is_symlink():
            found.append((plugin.name, skills))
    return sorted(found)


def _copy_skill_tree(src: Path, dest: Path) -> None:
    """Plain files only: no link is followed and no hidden file or folder is copied."""
    for root, dirs, names in os.walk(src, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith('.') and not (Path(root) / d).is_symlink()]
        for name in names:
            file = Path(root) / name
            if name.startswith('.') or file.is_symlink() or not file.is_file():
                continue
            if file.stat().st_size > _SKILL_FILE_MAX:
                continue
            target = dest / file.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)


_staging_locks: dict[str, threading.Lock] = {}
_staging_locks_guard = threading.Lock()


def _staging_lock(home: Path) -> threading.Lock:
    with _staging_locks_guard:
        return _staging_locks.setdefault(str(home), threading.Lock())


def stage_store_skills(home: Path) -> Path | None:
    """Rebuild ``<home>/store-skills`` for this turn and return it (None when off).

    Rebuilt every turn from the code, so an app switched off takes its skills with
    it, and an edit the agent makes to a skill lasts one turn in one conversation:
    Janus used to read the skills straight from the /app tree.

    Two messages of one chat can be in flight at once: a lock serialises them in
    this process, each copy is built in its own temporary folder, and a swap that
    another process won leaves its copy (the same files) in place.
    """
    staged = home / STORE_SKILLS_DIR
    with _staging_lock(home):
        if not janus_settings.bundled_skills_enabled():
            shutil.rmtree(staged, ignore_errors=True)
            return None
        fresh = Path(tempfile.mkdtemp(prefix=f'.{STORE_SKILLS_DIR}-', dir=home))
        old = Path(tempfile.mkdtemp(prefix=f'.{STORE_SKILLS_DIR}-old-', dir=home))
        try:
            sources = [('core', bundled_skills_dir())] if bundled_skills_dir().is_dir() else []
            for name, folder in sources + app_skill_dirs():
                try:
                    _copy_skill_tree(folder, fresh / name)
                except OSError:
                    logger.warning('janus: skills of %s not staged', name, exc_info=True)
            with contextlib.suppress(FileNotFoundError):
                staged.rename(old / STORE_SKILLS_DIR)
            try:
                fresh.rename(staged)
            except OSError:
                # Another process put its copy there between the two renames.
                if not staged.is_dir():
                    raise
        finally:
            shutil.rmtree(fresh, ignore_errors=True)
            shutil.rmtree(old, ignore_errors=True)
    return staged


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


def _config_text(
    mcp_url: str,
    headers: dict[str, str] | None = None,
    progress_path: Path | None = None,
    *,
    fallbacks: list[dict[str, str]] | None = None,
    skills_dir: Path | None = None,
    learning: bool | None = None,
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
    if skills_dir is not None:
        quoted = str(skills_dir).replace('\\', '/')
        external = f'\n  external_dirs:\n    - "{quoted}"'
    if learning is None:
        learning = janus_settings.learning_enabled()
    learning = 'true' if learning else 'false'
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
    # display.turn_completion_explainer: on, an empty reply ends in a printed
    #   "⚠️ No reply: …" explainer and exit 0, which reached the merchant as her
    #   answer; off, Janus prints "(empty)", which _turn_result treats as a failure.
    # hooks: one line per step into the home's progress file, for the chat
    #   (core/assistant/activity.py). A display only: each says on_failure: warn,
    #   so a failed hook is logged and the step goes ahead.
    # tools.tool_search: always written. Janus's default, auto, sizes the model's
    #   context from OpenRouter's catalogue (a fetch of up to 10 s every turn), so
    #   whether a turn sent every store tool or only the search bridge changed with
    #   whether openrouter.ai answered. Off: every store tool goes with each call
    #   and nothing is fetched. On: store tools load on request through Janus's
    #   tool_search / tool_describe / tool_call, which reach the same MCP edge.
    tool_search = 'on' if janus_settings.tool_search_enabled() else 'off'
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
display:
  turn_completion_explainer: false
tools:
  tool_search:
    enabled: "{tool_search}"
{fallback_block}{hooks}"""


# Janus reads its identity from SOUL.md in the home and seeds its own ("You are
# Janus Agent…") when the file is missing.
_SOUL = (
    'You are Linda, the AI assistant a merchant uses to run their online store. '
    'You work only for this store. You never mention the engine or framework that runs you.\n'
)
# Stops Janus copying its ~70 general-purpose skills into the home.
_NO_BUNDLED_SKILLS = '.no-bundled-skills'
# How Janus says it was installed. "docker" (true of the image) makes `janus chat`
# skip its update check, a PyPI fetch every six hours per home whose answer
# nothing shows: Janus moves only when a Morpheus release moves the pin.
_INSTALL_METHOD = ('.install_method', 'docker\n')


def _prepare_home(home: Path) -> None:
    """Linda's identity, no general-purpose Janus skills in her prompt, and no
    update check."""
    from core.assistant import janus_learning

    with contextlib.suppress(OSError):
        soul = home / 'SOUL.md'
        if not soul.is_file() or soul.read_text(encoding='utf-8') != _SOUL:
            soul.write_text(_SOUL, encoding='utf-8')
        (home / _NO_BUNDLED_SKILLS).touch(exist_ok=True)
        name, method = _INSTALL_METHOD
        stamp = home / name
        if not stamp.is_file() or stamp.read_text(encoding='utf-8') != method:
            stamp.write_text(method, encoding='utf-8')
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
    learning: bool | None = None,
) -> Path:
    """Write (or REWRITE) the store-agent Janus config.

    Rewriting matters: this file is per-conversation, so a write-once version
    pins whatever token and URL existed when the conversation started. A rotated
    MCP token would then never reach an existing conversation, and the stale one
    would sit on disk in one copy per conversation.
    """
    cfg_path = home / 'config.yaml'
    desired = _config_text(
        mcp_url,
        mcp_headers,
        home / activity.PROGRESS_FILE,
        fallbacks=fallbacks,
        skills_dir=stage_store_skills(home),
        learning=learning,
    )
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
    if (context or {}).get('mcp_public'):
        # A turn run by a Celery worker (an automation): the worker container has
        # no web server on loopback, so it reaches the store by its public address,
        # which routes to this store and no other.
        return f'https://{_default_host()}/mcp/admin/v1/', {}
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


_TURN_LOCK = '.morpheus-turn.lock'


def _lock_home(conv_home: Path):
    """The home's turn lock, held, or None while another turn holds it.

    One turn per conversation at a time: a second turn's hydrate would rewrite the
    notes and remove the files the first turn's Janus wrote and has not harvested
    yet. Closing the file releases the lock, and so does the process dying.
    """
    handle = (conv_home / _TURN_LOCK).open('w')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        handle.close()
        if isinstance(e, BlockingIOError):
            return None
        raise
    return handle
