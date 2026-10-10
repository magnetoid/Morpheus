"""Settings → AI → Janus.

One page, one URL. Actions post back to it (``action=save`` / ``action=test``)
because contributed pages mount at ``/dashboard/apps/<app>/<slug>/`` and deeper
paths under it do not route.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core.assistant import janus_runtime, janus_settings
from core.authz import require_capability
from plugins.installed.janus import upstream
from plugins.installed.janus.forms import JanusSettingsForm

logger = logging.getLogger('morpheus.janus')

_SETTINGS_KEYS = (
    'enabled',
    'model_source',
    'provider',
    'model',
    'base_url',
    'max_tool_turns',
    'turn_timeout_s',
    'extra_instructions',
    'bundled_skills',
    'learning',
    'web_search',
    'auto_update',
    'fallback_providers',
    'reasoning_effort',
)
_REVIEW_ACTIONS = ('forget_note', 'delete_skill', 'clear_lessons')
_VERSION_CACHE_KEY = 'janus:installed-version'


def _app():
    from plugins.registry import app_registry

    return app_registry.get('janus')


def _config() -> dict:
    app = _app()
    if app is None:
        return {}
    app.invalidate_config_cache()
    return dict(app.get_config() or {})


def _save(values: dict) -> list[str]:
    """Write the changed keys in one row update; return which keys changed."""
    from django.db import transaction

    from plugins.models import PluginConfig

    with transaction.atomic():
        row, _ = PluginConfig.objects.select_for_update().get_or_create(plugin_name='janus')
        config = dict(row.config or {})
        changed = [k for k, v in values.items() if config.get(k) != v]
        config.update(values)
        row.config = config
        row.save(update_fields=['config', 'updated_at'])
    app = _app()
    if app is not None:
        app.invalidate_config_cache()
    return changed


def _initial(config: dict) -> dict:
    from core.assistant import janus_engine as eng

    return {
        'enabled': config.get('enabled', True),
        'model_source': config.get('model_source', 'store'),
        'provider': config.get('provider', ''),
        'model': config.get('model', ''),
        'base_url': config.get('base_url', ''),
        'max_tool_turns': config.get('max_tool_turns', eng.MAX_TOOL_TURNS),
        'turn_timeout_s': config.get('turn_timeout_s', eng.turn_timeout_s()),
        'extra_instructions': config.get('extra_instructions', ''),
        'bundled_skills': config.get('bundled_skills', True),
        'learning': config.get('learning', True),
        'web_search': config.get('web_search', True),
        'auto_update': config.get('auto_update', True),
        'fallback_providers': list(config.get('fallback_providers') or []),
        'reasoning_effort': config.get('reasoning_effort', 'low'),
    }


def _installed_version(cmd: list[str], home: Path) -> str:
    cached = cache.get(_VERSION_CACHE_KEY)
    if cached is not None:
        return cached
    version = ''
    try:
        proc = subprocess.run(  # noqa: S603 — cmd comes from settings/PATH
            [*cmd, '--version'],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                'PATH': '/usr/local/bin:/usr/bin:/bin',
                'HOME': str(home),
                'JANUS_HOME': str(home),
            },
            check=False,
        )
        version = (proc.stdout or '').strip().splitlines()[0][:120] if proc.stdout else ''
    except (OSError, subprocess.SubprocessError, IndexError):
        logger.debug('janus: version probe failed', exc_info=True)
    cache.set(_VERSION_CACHE_KEY, version, 600)
    return version


def _status() -> dict:
    from core.assistant import janus_engine as eng
    from core.assistant import janus_settings

    cmd = eng.janus_cmd()
    installed = bool(cmd) and bool(Path(cmd[0]).is_file() or shutil.which(cmd[0]))
    try:
        home = eng.linda_janus_home()
        home_text = str(home)
    except OSError as e:
        home, home_text = None, f'unavailable ({e})'
    custom = janus_settings.custom_provider()
    if custom is not None:
        provider = f'{custom["provider"]} · {custom["model"]} (pinned here)'
    else:
        try:
            from core.agents.provider_registry import get_active_provider_name, get_provider_config

            name = get_active_provider_name()
            provider = f'{name} · {get_provider_config(name).model} (store AI provider)'
        except Exception:  # noqa: BLE001
            provider = 'unknown'
    return {
        'installed': installed,
        'binary': ' '.join(cmd) if cmd else '',
        'version': _installed_version(cmd, home) if installed and home else '',
        # The exact commit, and whether GitHub has moved on (checked once a day).
        'build': upstream.build_status(cmd),
        'updates': _updates(cmd),
        'home': home_text,
        'provider': provider,
        'toolsets': ', '.join(eng.turn_toolsets()),
        'auto_approve': eng.auto_approve_enabled(),
    }


_CHECK_RESULTS = {
    'current': 'Up to date with GitHub.',
    'installed': 'Installed a newer Janus; Linda uses it from her next message.',
    'failed': 'Found a newer Janus but kept the current one: it did not pass.',
    'skipped': 'The newest commit failed before, so it was not tried again.',
    'error': "Couldn't reach GitHub.",
    'rolled_back': 'Went back to the previous Janus after repeated failures.',
}


def _when(epoch) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(epoch), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _updates(cmd: list[str] | None) -> dict:
    """What the page shows about keeping Janus current (core/assistant/janus_runtime.py)."""
    summary = janus_runtime.summary()
    report = janus_runtime.contract_report(cmd[0] if cmd else None)
    checks = report.get('checks') or []
    last = summary.get('last_check') or {}
    active = summary.get('active') or {}
    failed = sorted(
        (
            {'commit': sha, 'reason': str(v.get('reason') or ''), 'at': _when(v.get('at'))}
            for sha, v in (summary.get('failed') or {}).items()
        ),
        key=lambda f: f['at'] or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )[:3]
    return {
        **summary,
        'active': {**active, 'installed': _when(active.get('installed_at'))} if active else None,
        'last': {
            **last,
            'when': _when(last.get('at')),
            'text': _CHECK_RESULTS.get(str(last.get('result') or ''), ''),
        }
        if last
        else None,
        'failed': failed,
        'contract': {
            'total': len(checks),
            'passed': sum(1 for c in checks if c.get('ok')),
            'failing': [c.get('name') for c in checks if c.get('required') and not c.get('ok')],
            'warnings': [
                c.get('name') for c in checks if not c.get('required') and not c.get('ok')
            ],
            'notes': report.get('notes') or [],
        }
        if checks
        else None,
    }


def _run_test(user) -> dict:
    """One tiny turn with no store tools: proves the engine and the model answer."""
    from core.assistant import janus_engine as eng

    out = eng.run_janus_turn(
        message='Reply with exactly: ok',
        conversation_key=f'janus-settings-test:{user.pk}:{uuid.uuid4().hex[:8]}',
        system_prompt='You are a connection check for a store assistant. Reply with exactly: ok',
        turn_token='',
        # This page does not stream, so the request must finish before a proxy
        # gives up on a silent connection.
        timeout_s=45,
    )
    return {
        'ok': not out.get('error'),
        'text': (out.get('text') or '')[:500],
        'error': (out.get('error') or '')[:500],
        'seconds': round((out.get('duration_ms') or 0) / 1000, 1),
    }


def _audit(user, changed: list[str]) -> None:
    try:
        from core.audit.services import record

        record(
            event_type='janus.settings_changed',
            actor=user,
            target='janus',
            # Key names only — never a value, since one of them is an API key.
            metadata={'changed': sorted(changed)},
        )
    except Exception:  # noqa: BLE001 — audit must never break the save
        logger.debug('janus: settings audit skipped', exc_info=True)


def _review(request, action: str) -> None:
    """Delete one piece of what Linda has learned. Each deletion is audited."""
    from core.assistant import janus_learning

    if action == 'forget_note':
        done = janus_learning.forget_note(
            which=request.POST.get('which', ''),
            entry_id=request.POST.get('note', ''),
            user=request.user,
        )
    elif action == 'delete_skill':
        done = bool(janus_learning.delete_skill(request.POST.get('skill', ''), user=request.user))
    else:
        done = janus_learning.clear_lessons(user=request.user)
    if done:
        messages.success(request, 'Deleted. Linda will not use it from her next message.')
    else:
        messages.error(request, 'Nothing to delete — it may already be gone.')


def _learned(user) -> dict:
    from core.assistant import janus_learning

    return {
        'notes': janus_learning.notes(user=user),
        'skills': janus_learning.skills(),
        'lessons': janus_learning.lesson_count(),
    }


@staff_member_required
@require_capability('system.write')
@require_http_methods(['GET', 'POST'])
def settings_view(request):
    config = _config()
    has_stored_key = bool(config.get('api_key'))
    test_result = None

    if request.method == 'POST' and request.POST.get('action') in _REVIEW_ACTIONS:
        _review(request, request.POST['action'])
        return redirect(request.path)
    if request.method == 'POST' and request.POST.get('action') == 'check_updates':
        if janus_runtime.maybe_update(force=True):
            messages.success(
                request,
                'Checking GitHub for a newer Janus. Installing and checking one takes about '
                'a minute; reload this page to see the result.',
            )
        else:
            messages.error(
                request,
                'Updates are off here: switched off below or by the server, or this '
                'server is pinned to one Janus commit.',
            )
        return redirect(request.path)
    if request.method == 'GET':
        # The periodic check also runs from Linda's turns; this keeps it going
        # on a store where the page is visited but Linda is not.
        janus_runtime.maybe_update()
    if request.method == 'POST' and request.POST.get('action') == 'test':
        test_result = _run_test(request.user)
        form = JanusSettingsForm(initial=_initial(config), has_stored_key=has_stored_key)
    elif request.method == 'POST':
        form = JanusSettingsForm(request.POST, has_stored_key=has_stored_key)
        if form.is_valid():
            data = form.cleaned_data
            values = {key: data[key] for key in _SETTINGS_KEYS}
            if data.get('clear_api_key'):
                values['api_key'] = ''
            elif data.get('api_key'):
                values['api_key'] = data['api_key']
            changed = _save(values)
            if changed:
                _audit(request.user, changed)
            messages.success(request, 'Janus settings saved.')
            return redirect(request.path)
        messages.error(request, 'Some settings need fixing — see below.')
    else:
        form = JanusSettingsForm(initial=_initial(config), has_stored_key=has_stored_key)

    return render(
        request,
        'janus/settings.html',
        {
            'form': form,
            'has_stored_key': has_stored_key,
            'status': _status(),
            'learned': _learned(request.user),
            'test_result': test_result,
            'limits': {
                'max_steps': janus_settings.MAX_TOOL_TURNS,
                'min_time': janus_settings.MIN_TURN_TIMEOUT_S,
                'max_time': janus_settings.MAX_TURN_TIMEOUT_S,
            },
            'active_nav': 'settings',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': 'Janus'},
            ],
        },
    )
