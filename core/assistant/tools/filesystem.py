"""Filesystem tools — read-only by default, scoped to the project root."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Defer the agents-kernel Tool import; the assistant must boot even if it fails.
try:
    from core.agents import ToolError, ToolResult, tool
except Exception:  # pragma: no cover — fallback shape
    from dataclasses import dataclass, field

    class ToolError(RuntimeError):
        pass

    @dataclass
    class ToolResult:
        output: object = None
        display: str = ''
        metadata: dict = field(default_factory=dict)

    def tool(*, name, description, schema=None, scopes=None, requires_approval=False):
        def _wrap(fn):
            from types import SimpleNamespace

            return SimpleNamespace(
                name=name,
                description=description,
                handler=fn,
                schema=schema or {'type': 'object', 'properties': {}},
                scopes=list(scopes or []),
                requires_approval=requires_approval,
                plugin='',
                invoke=lambda args, **kw: ToolResult(output=fn(**args)),
            )

        return _wrap


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MAX_BYTES = 200_000  # cap on a single read


def _safe_path(raw: str) -> Path:
    """Resolve `raw` against project root; reject anything outside."""
    if not raw:
        raise ToolError('path required')
    p = (_PROJECT_ROOT / raw).resolve() if not raw.startswith('/') else Path(raw).resolve()
    try:
        p.relative_to(_PROJECT_ROOT)
    except ValueError as e:
        raise ToolError(f'path outside project root: {raw}') from e
    return p


@tool(
    name='fs.read_file',
    description='Read a UTF-8 text file from the project (capped at 200KB).',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'path': {'type': 'string', 'description': 'Project-relative path.'}},
        'required': ['path'],
    },
)
def read_file_tool(*, path: str) -> ToolResult:
    p = _safe_path(path)
    # Refuse to read the safety-boundary's protected paths — .env / key material
    # / credentials (exfiltration into AgentStep rows + transcripts), plus the
    # financial/auth source. `_safe_path` already resolved the path, so this
    # matcher sees the normalized form (no ../ evasion).
    from core.safety import is_path_protected  # noqa: PLC0415

    rel = str(p.relative_to(_PROJECT_ROOT))
    if is_path_protected(rel):
        raise ToolError(f'refused: {rel} is a protected path (secrets / financial / auth)')
    if not p.exists() or not p.is_file():
        raise ToolError(f'not a file: {path}')
    try:
        data = p.read_bytes()[:_MAX_BYTES]
        text = data.decode('utf-8', errors='replace')
    except OSError as e:
        raise ToolError(f'read failed: {e}') from e
    return ToolResult(
        output={
            'path': str(p.relative_to(_PROJECT_ROOT)),
            'size': p.stat().st_size,
            'content': text,
        },
        display=f'{path} ({len(text)} chars)',
    )


@tool(
    name='fs.list_dir',
    description='List files in a directory (one level deep).',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'path': {'type': 'string', 'default': '.'}},
    },
)
def list_dir_tool(*, path: str = '.') -> ToolResult:
    p = _safe_path(path)
    if not p.is_dir():
        raise ToolError(f'not a directory: {path}')
    entries = []
    for entry in sorted(p.iterdir()):
        if entry.name.startswith('.'):
            continue
        try:
            stat = entry.stat()
            entries.append(
                {
                    'name': entry.name,
                    'is_dir': entry.is_dir(),
                    'size': stat.st_size if entry.is_file() else None,
                }
            )
        except OSError:
            continue
    return ToolResult(
        output={'path': path, 'entries': entries[:200]}, display=f'{path}: {len(entries)} entries'
    )


@tool(
    name='fs.search_files',
    description='Search for a string across the project. Uses `grep -rln`.',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {'type': 'string'},
            'path': {'type': 'string', 'default': '.'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 30},
        },
        'required': ['query'],
    },
)
def search_files_tool(*, query: str, path: str = '.', limit: int = 30) -> ToolResult:
    if not query.strip():
        raise ToolError('query required')
    target = _safe_path(path)
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                'grep',
                '-rln',
                '--exclude-dir=__pycache__',
                '--exclude-dir=venv',  # noqa: S607
                '--exclude-dir=.git',
                '--exclude-dir=node_modules',
                query,
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise ToolError(f'search failed: {e}') from e
    # Drop protected files from the results. grep reads .env / secrets / auth
    # source to test the query, but returning the matching FILENAME turns search
    # into a boolean oracle over exactly the content `fs.read_file` refuses —
    # `SECRET_KEY=sk-ab` hits iff present, enabling byte-by-byte extraction
    # (hunt #15). Filter through the same single-source boundary read_file uses.
    from core.safety import is_path_protected  # noqa: PLC0415

    files = []
    for line in result.stdout.splitlines():
        rel = os.path.relpath(line, _PROJECT_ROOT)
        if is_path_protected(rel):
            continue
        files.append(rel)
        if len(files) >= limit:
            break
    return ToolResult(
        output={'query': query, 'matches': files, 'count': len(files)},
        display=f'{len(files)} file(s) match {query!r}',
    )
