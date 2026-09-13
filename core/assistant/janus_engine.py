"""Store agent engine: Janus (magnetoid/janus), isolated from Django.

Janus **is** the agent. Linda is the merchant-facing brand only. Morpheus and
Janus both ship top-level packages named ``plugins`` / ``tools``, so Janus MUST
run in a subprocess (own venv / own sys.path). Each conversation home is seeded
with bundled Morpheus ecommerce skills (``core/assistant/janus_skills``).

Discovery order for the binary:
  1. ``settings.JANUS_BIN`` / ``JANUS_BIN``
  2. ``janus`` on PATH
  3. ``<JANUS_ENGINE_ROOT>/.venv/bin/janus`` then ``venv/bin/janus``
  4. ``~/.janus/janus-agent`` source checkout (``python cli.py``)

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
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.janus')

# Must stay UNDER the gunicorn worker timeout (GUNICORN_TIMEOUT, default 60s in
# scripts/docker-entrypoint.sh). This is a BLOCKING call inside the SSE
# generator, so an adapter timeout above the worker timeout means gunicorn kills
# the worker before we ever return a friendly error.
_DEFAULT_TIMEOUT_S = 55

# The MCP server name in the generated config, and the ONLY toolsets a turn may
# use. Without an explicit ``-t``, ``janus chat`` loads its default ``janus-cli``
# toolset — 56 tools including terminal, write_file/patch, execute_code, web and
# browser — running as the same OS user that owns /app and can read the web
# process's environment through /proc. So the env allowlist below is not the
# boundary; this list is. ``skills`` is list/view/manage of skill documents under
# JANUS_HOME only (no execution), and is what injects the bundled ecommerce
# skills into the prompt.
MCP_SERVER_NAME = 'morpheus_admin'
TURN_TOOLSETS = (MCP_SERVER_NAME, 'skills')

# Janus prints ``session_id: <id>`` to stderr in quiet mode. Stored per
# conversation and passed back with ``--resume``: a bare ``--continue`` looks up
# the newest session whose source is ``cli``, never ``linda``, so it failed every
# follow-up message. Validated before it reaches argv.
_SESSION_FILE = 'janus_session_id'
_SESSION_ID_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
_SESSION_LINE_RE = re.compile(r'^session_id:\s*(\S+)\s*$', re.M)

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
    which = shutil.which('janus')
    if which:
        return [which]
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


def turn_timeout_s() -> int:
    s = _settings()
    raw = getattr(s, 'LINDA_JANUS_TIMEOUT_S', _DEFAULT_TIMEOUT_S) if s else _DEFAULT_TIMEOUT_S
    try:
        return max(5, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_S


def linda_janus_home() -> Path:
    s = _settings()
    home = (Path(s.BASE_DIR) if s is not None else Path.home()) / '.linda-janus'
    home.mkdir(parents=True, exist_ok=True)
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


def _config_text(mcp_url: str, mcp_token: str) -> str:
    mcp_block = ''
    if mcp_url:
        auth = f'\n        Authorization: "Bearer {mcp_token}"' if mcp_token else ''
        mcp_block = f"""
mcp_servers:
  {MCP_SERVER_NAME}:
    url: "{mcp_url}"
    headers:{auth or ' {}'}
    timeout: 60
"""
    skills_block = ''
    skills_dir = bundled_skills_dir()
    if skills_dir.is_dir():
        quoted = str(skills_dir).replace('\\', '/')
        skills_block = f"""
skills:
  external_dirs:
    - "{quoted}"
"""
    return f"""# Auto-generated store agent home. Merchant-facing name is Linda.
model:
  default: {os.environ.get('JANUS_INFERENCE_MODEL') or 'auto'}
agent:
  max_turns: 90
{mcp_block}{skills_block}
"""


def _ensure_config(home: Path, *, mcp_url: str = '', mcp_token: str = '') -> Path:
    """Write (or REWRITE) the store-agent Janus config.

    Rewriting matters: this file is per-conversation, so a write-once version
    pins whatever token and URL existed when the conversation started. A rotated
    MCP token would then never reach an existing conversation, and the stale one
    would sit on disk in one copy per conversation.
    """
    cfg_path = home / 'config.yaml'
    desired = _config_text(mcp_url, mcp_token)
    try:
        current = cfg_path.read_text(encoding='utf-8')
    except OSError:
        current = None
    if current != desired:
        cfg_path.write_text(desired, encoding='utf-8')
    with contextlib.suppress(OSError):
        cfg_path.chmod(0o600)
    return cfg_path


def _mcp_url(context: dict[str, Any] | None) -> str:
    s = _settings()
    explicit = (getattr(s, 'LINDA_MCP_URL', '') if s else '') or os.environ.get('LINDA_MCP_URL', '')
    if explicit:
        # Exactly one trailing slash. The MCP endpoint is a POST with a JSON-RPC
        # body, and Django's APPEND_SLASH redirect DROPS that body — so a URL
        # missing the slash fails every tool call.
        return explicit.rstrip('/') + '/'
    request = (context or {}).get('request')
    if request is not None:
        try:
            return request.build_absolute_uri('/mcp/admin/v1/')
        except Exception:  # noqa: BLE001
            logger.debug('janus: could not build MCP url from request', exc_info=True)
    return f'http://127.0.0.1:{os.environ.get("PORT") or "8000"}/mcp/admin/v1/'


def _mcp_token() -> str:
    s = _settings()
    return (getattr(s, 'LINDA_MCP_TOKEN', '') if s else '') or os.environ.get('LINDA_MCP_TOKEN', '')


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


def _provider_wiring() -> tuple[list[str], dict[str, str]]:
    """CLI args + env that pin Janus to Morpheus's active LLM provider."""
    try:
        from core.agents.provider_registry import get_active_provider_name, get_provider_config

        name = get_active_provider_name()
        cfg = get_provider_config(name)
    except Exception:  # noqa: BLE001 — fall back to Janus's own resolution
        logger.warning('janus: provider config unavailable; Janus will auto-select', exc_info=True)
        return [], {}
    spec = _JANUS_PROVIDERS.get(name)
    if spec is None or not cfg.api_key:
        logger.warning('janus: no provider mapping for %r; Janus will auto-select', name)
        return [], {}
    janus_id, key_var, base_var = spec
    args = ['--provider', janus_id]
    if cfg.model:
        args += ['-m', cfg.model]
    env = {key_var: cfg.api_key}
    if cfg.base_url:
        env[base_var] = cfg.base_url
    return args, env


def _stored_session_id(conv_home: Path) -> str:
    try:
        sid = (conv_home / _SESSION_FILE).read_text(encoding='utf-8').strip()
    except OSError:
        return ''
    return sid if _SESSION_ID_RE.match(sid) else ''


def _remember_session_id(conv_home: Path, stderr: str) -> None:
    match = _SESSION_LINE_RE.search(stderr)
    if match and _SESSION_ID_RE.match(match.group(1)):
        with contextlib.suppress(OSError):
            (conv_home / _SESSION_FILE).write_text(match.group(1), encoding='utf-8')


def _forget_session_id(conv_home: Path) -> None:
    with contextlib.suppress(OSError):
        (conv_home / _SESSION_FILE).unlink()


def run_janus_turn(
    *,
    message: str,
    conversation_key: str,
    system_prompt: str,
    timeout_s: int | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one store-agent turn on Janus. Returns {text, error, duration_ms}."""
    cmd = janus_cmd()
    if not cmd:
        return {'text': '', 'error': 'janus_unavailable', 'duration_ms': 0}

    timeout = turn_timeout_s() if timeout_s is None else max(5, int(timeout_s))
    started = time.monotonic()
    home = linda_janus_home()
    sid = _session_id(conversation_key)
    conv_home = home / 'conv' / sid
    conv_home.mkdir(parents=True, exist_ok=True)
    _ensure_config(conv_home, mcp_url=_mcp_url(context), mcp_token=_mcp_token())

    provider_args, provider_env = _provider_wiring()
    env = _child_env(
        {
            **provider_env,
            'JANUS_HOME': str(conv_home),
            'JANUS_EPHEMERAL_SYSTEM_PROMPT': system_prompt[:80_000],
            # The dashboard already collected the merchant's message, so there is
            # no TTY to prompt on. That is a reason not to STALL, not a reason to
            # auto-approve: off unless the deployment opted in.
            'JANUS_YOLO_MODE': '1' if auto_approve_enabled() else '0',
        }
    )

    # -Q: stdout is the answer only (no banner, query echo or screen escapes).
    # -t: see TURN_TOOLSETS — never let the default toolset load.
    base_argv = [
        *cmd,
        'chat',
        '-Q',
        '-q',
        message[:10_000],
        '--source',
        'linda',
        '-t',
        ','.join(TURN_TOOLSETS),
        *provider_args,
    ]
    resume_id = _stored_session_id(conv_home)
    # Always the conversation's own home. Janus auto-injects AGENTS.md / SOUL.md
    # from its working directory, so running inside an engine source checkout
    # would feed that project's developer instructions to the store agent.
    cwd = str(conv_home)
    for _attempt in (0, 1):
        remaining = max(1, timeout - int(time.monotonic() - started))
        argv = [*base_argv, '--resume', resume_id] if resume_id else base_argv
        try:
            proc = subprocess.run(  # noqa: S603 — cmd is resolved from settings/PATH
                argv,
                env=env,
                capture_output=True,
                text=True,
                timeout=remaining,
                cwd=cwd,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.warning('janus engine timed out after %ss key=%s', timeout, conversation_key)
            return {
                'text': '',
                'error': f'janus timed out after {timeout}s',
                'duration_ms': timeout * 1000,
            }
        except OSError as e:
            logger.warning('janus engine spawn failed: %s', e)
            return {'text': '', 'error': f'janus spawn failed: {e}', 'duration_ms': 0}
        if proc.returncode != 0 and resume_id and 'Session not found' in (proc.stderr or ''):
            # The stored id outlived its state.db. Janus exits before any model
            # call on this path, so starting a fresh session costs nothing.
            _forget_session_id(conv_home)
            resume_id = ''
            continue
        break

    _remember_session_id(conv_home, proc.stderr or '')
    text = (proc.stdout or '').strip()
    err = _SESSION_LINE_RE.sub('', proc.stderr or '').strip()
    duration = int((time.monotonic() - started) * 1000)
    if proc.returncode != 0:
        # A crash AFTER partial output is still a crash. Returning the partial
        # text as a completed turn hides the failure from the merchant, from the
        # transcript, and from the self-improvement loop.
        logger.warning(
            'janus engine rc=%s stdout_head=%s stderr=%s',
            proc.returncode,
            text[:200],
            err[:400],
        )
        reason = err[:500] or f'janus exit {proc.returncode}'
        if text:
            reason = f'{reason} (crashed after {len(text)} chars of partial output)'
        return {'text': '', 'error': reason, 'duration_ms': duration}
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
    return {'text': text, 'error': '', 'duration_ms': duration}
