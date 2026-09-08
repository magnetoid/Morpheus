"""Linda's engine: Janus (magnetoid/janus), isolated from Django.

Morpheus and Janus both ship top-level packages named ``plugins`` / ``tools``,
so Janus MUST run in a subprocess (own venv / own sys.path). The merchant still
talks to **Linda** — Janus is the loop, not the name.

Discovery order for the binary:
  1. ``settings.JANUS_BIN`` / ``JANUS_BIN``
  2. ``janus`` on PATH
  3. ``<JANUS_ENGINE_ROOT>/.venv/bin/janus`` then ``venv/bin/janus``
  4. ``~/.janus/janus-agent`` source checkout (``python cli.py``)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.janus')

_DEFAULT_TIMEOUT_S = 120


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


def linda_janus_home() -> Path:
    s = _settings()
    if s is not None:
        home = Path(s.BASE_DIR) / '.linda-janus'
    else:
        home = Path.home() / '.linda-janus'
    home.mkdir(parents=True, exist_ok=True)
    return home


def _session_id(conversation_key: str) -> str:
    digest = hashlib.sha256(conversation_key.encode()).hexdigest()[:12]
    return f'linda-{digest}'


def _ensure_config(home: Path, *, mcp_url: str = '', mcp_token: str = '') -> Path:
    """Write a Linda-scoped Janus config if missing. Never overwrite secrets."""
    cfg_path = home / 'config.yaml'
    if cfg_path.exists():
        return cfg_path
    mcp_block = ''
    if mcp_url:
        auth = f'\n        Authorization: "Bearer {mcp_token}"' if mcp_token else ''
        mcp_block = f"""
mcp_servers:
  morpheus_admin:
    url: "{mcp_url}"
    headers:{auth or ' {}'}
    timeout: 60
"""
    cfg_path.write_text(
        f"""# Auto-generated for Linda. Janus is the engine; the merchant sees Linda.
model:
  default: {os.environ.get('JANUS_INFERENCE_MODEL') or 'auto'}
agent:
  max_turns: 90
{mcp_block}
""",
        encoding='utf-8',
    )
    try:
        cfg_path.chmod(0o600)
    except OSError:
        pass
    return cfg_path


def _mcp_url(context: dict[str, Any] | None) -> str:
    s = _settings()
    explicit = (getattr(s, 'LINDA_MCP_URL', '') if s else '') or os.environ.get(
        'LINDA_MCP_URL', ''
    )
    if explicit:
        return explicit.rstrip('/') + ('/' if not explicit.endswith('/') else '')
    request = (context or {}).get('request')
    if request is not None:
        try:
            return request.build_absolute_uri('/mcp/admin/v1/')
        except Exception:  # noqa: BLE001
            pass
    return 'http://127.0.0.1:8000/mcp/admin/v1/'


def _mcp_token() -> str:
    s = _settings()
    return (getattr(s, 'LINDA_MCP_TOKEN', '') if s else '') or os.environ.get(
        'LINDA_MCP_TOKEN', ''
    )


def run_janus_turn(
    *,
    message: str,
    conversation_key: str,
    system_prompt: str,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one Linda turn on Janus. Returns {text, error, duration_ms}."""
    cmd = janus_cmd()
    if not cmd:
        return {'text': '', 'error': 'janus_unavailable', 'duration_ms': 0}

    started = time.monotonic()
    home = linda_janus_home()
    sid = _session_id(conversation_key)
    conv_home = home / 'conv' / sid
    conv_home.mkdir(parents=True, exist_ok=True)
    _ensure_config(conv_home, mcp_url=_mcp_url(context), mcp_token=_mcp_token())

    env = os.environ.copy()
    env['JANUS_HOME'] = str(conv_home)
    env['JANUS_EPHEMERAL_SYSTEM_PROMPT'] = system_prompt[:80_000]
    # Dashboard already collected the merchant's message; don't stall on TTY prompts.
    env['JANUS_YOLO_MODE'] = env.get('JANUS_YOLO_MODE', '1')
    env.pop('JANUS_INTERACTIVE', None)

    argv = [*cmd, 'chat', '-q', message[:10_000], '--source', 'linda']
    if (conv_home / 'state.db').is_file():
        argv.append('--continue')

    try:
        proc = subprocess.run(  # noqa: S603 — cmd is resolved from settings/PATH
            argv,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(engine_root() or home),
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning('janus engine timed out after %ss key=%s', timeout_s, conversation_key)
        return {'text': '', 'error': f'janus timed out after {timeout_s}s', 'duration_ms': timeout_s * 1000}
    except OSError as e:
        logger.warning('janus engine spawn failed: %s', e)
        return {'text': '', 'error': f'janus spawn failed: {e}', 'duration_ms': 0}

    text = (proc.stdout or '').strip()
    err = (proc.stderr or '').strip()
    if proc.returncode != 0 and not text:
        logger.warning('janus engine rc=%s stderr=%s', proc.returncode, err[:400])
        return {'text': '', 'error': err[:500] or f'janus exit {proc.returncode}', 'duration_ms': int((time.monotonic() - started) * 1000)}
    if text.startswith('{') and '"final_response"' in text[:200]:
        try:
            payload = json.loads(text)
            text = str(payload.get('final_response') or payload.get('text') or text)
        except json.JSONDecodeError:
            pass
    duration = int((time.monotonic() - started) * 1000)
    return {'text': text, 'error': '', 'duration_ms': duration}
