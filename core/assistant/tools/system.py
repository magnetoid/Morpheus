"""System info tools — disk, memory, git, env."""

from __future__ import annotations

import shutil
import subprocess

from core.assistant.tools.filesystem import _PROJECT_ROOT, ToolError, ToolResult, tool


@tool(
    name='system.server_info',
    description='Server hostname, Python version, Django version, plugin count.',
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def server_info_tool() -> ToolResult:
    import platform
    import sys

    info = {
        'hostname': platform.node(),
        'platform': platform.platform(),
        'python': sys.version.split()[0],
    }
    try:
        import django

        info['django'] = django.get_version()
    except Exception:  # noqa: BLE001
        info['django'] = 'unknown'
    try:
        from plugins.registry import plugin_registry

        info['plugins_total'] = len(plugin_registry.all_plugins())
        info['plugins_active'] = len(plugin_registry.active_plugins())
    except Exception:  # noqa: BLE001
        info['plugins_total'] = info['plugins_active'] = -1
    return ToolResult(output=info)


@tool(
    name='system.disk_usage',
    description='Free / total disk space at the project root.',
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def disk_usage_tool() -> ToolResult:
    total, used, free = shutil.disk_usage(str(_PROJECT_ROOT))
    return ToolResult(
        output={
            'total_bytes': total,
            'used_bytes': used,
            'free_bytes': free,
            'free_human': f'{free / (1024**3):.1f} GB',
            'used_human': f'{used / (1024**3):.1f} GB',
        }
    )


@tool(
    name='system.git_log',
    description='Recent commits on the current branch.',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 10}},
    },
)
def git_log_tool(*, limit: int = 10) -> ToolResult:
    n = max(1, min(int(limit or 10), 50))
    try:
        out = subprocess.run(  # noqa: S603
            ['git', '-C', str(_PROJECT_ROOT), 'log', f'-{n}', '--pretty=format:%h %ai %s'],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise ToolError(f'git unavailable: {e}') from e
    if out.returncode != 0:
        raise ToolError(f'git log failed: {out.stderr.strip()[:200]}')
    return ToolResult(output={'commits': out.stdout.strip().splitlines()})
