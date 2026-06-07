"""Core agent code sandbox — runs first-party, agent-authored Python.

This is the AGENT sandbox: the substrate for Linda composing tools in code
(`run_python`, Phase 2 of the self-learning uplift) and, later, drafting her own
modules. It is CORE because the self-building loop is core (ADR 0010) and must
not hinge on a disableable plugin. (The separate `functions` plugin sandboxes
*merchant* cart/pricing code — different layer, same conservative technique.)

Safety layers:
  * AST validation — no import, async, yield, global/nonlocal; no dunder
    attribute access; a denylist of dangerous names (open/eval/exec/…).
  * Curated ``__builtins__`` — no ``__import__``, no file/network reach.
  * Wall-clock timeout on a worker thread.

It is *deliberately conservative*, NOT a hostile-code sandbox: the author is
first-party Linda, gated by tool scopes upstream. For untrusted multi-tenant
execution, swap the thread runner for a subprocess/container (same as the
functions plugin's note).
"""

from __future__ import annotations

import ast
import threading
from typing import Any

MAX_SOURCE_BYTES = 16_000
DEFAULT_TIMEOUT_MS = 3000
MAX_LEAKED_THREADS = 5  # backstop: refuse new runs while runaway scripts pile up

# Threads still alive past their timeout (truly-stuck scripts). A finite-but-slow
# script removes itself on completion; a real infinite loop stays until process
# exit. New runs are refused once this exceeds MAX_LEAKED_THREADS (DoS backstop).
_leaked_lock = threading.Lock()
_leaked: set = set()


class SandboxError(RuntimeError):
    """Raised on validation failure, timeout, or in-script error."""


_FORBIDDEN_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.AsyncFunctionDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
    ast.Yield,
    ast.YieldFrom,
)

_FORBIDDEN_NAMES = frozenset(
    {
        '__import__',
        '__builtins__',
        'open',
        'exec',
        'eval',
        'compile',
        'globals',
        'locals',
        'vars',
        'input',
        'breakpoint',
        'getattr',
        'setattr',
        'delattr',
    }
)

# Curated builtins — crucially NO __import__, open, eval, exec.
_SAFE_BUILTINS: dict[str, Any] = {
    'True': True,
    'False': False,
    'None': None,
    'abs': abs,
    'all': all,
    'any': any,
    'bool': bool,
    'dict': dict,
    'enumerate': enumerate,
    'filter': filter,
    'float': float,
    'int': int,
    'isinstance': isinstance,
    'len': len,
    'list': list,
    'map': map,
    'max': max,
    'min': min,
    'range': range,
    'reversed': reversed,
    'round': round,
    'set': set,
    'sorted': sorted,
    'str': str,
    'sum': sum,
    'tuple': tuple,
    'zip': zip,
    'Exception': Exception,
    'KeyError': KeyError,
    'TypeError': TypeError,
    'ValueError': ValueError,
}


def _validate(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODES):
            raise SandboxError(f'forbidden syntax: {type(node).__name__}')
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith('__')
            and node.attr.endswith('__')
        ):
            raise SandboxError(f'forbidden dunder access: {node.attr}')
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise SandboxError(f'forbidden name: {node.id}')
        # Block dunders hidden in string literals — defeats format-string /
        # getattr-by-name introspection oracles (e.g. "{0.__class__}".format).
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and '__' in node.value:
            raise SandboxError('forbidden dunder in string literal')


def run_sandboxed(
    source: str,
    *,
    extra_globals: dict[str, Any] | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> Any:
    """Execute ``source`` in the sandbox and return its ``result`` variable.

    ``extra_globals`` injects the host-controlled API (e.g. a ``call`` bridge).
    Raises ``SandboxError`` on validation failure, timeout, or in-script error.
    """
    if not isinstance(source, str) or not source.strip():
        raise SandboxError('empty source')
    if len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise SandboxError('source too large (>16KB)')
    with _leaked_lock:
        if len(_leaked) >= MAX_LEAKED_THREADS:
            raise SandboxError('sandbox busy — too many runaway scripts; try again later')
    try:
        tree = ast.parse(source, mode='exec')
    except SyntaxError as e:
        raise SandboxError(f'SyntaxError: {e.msg} at line {e.lineno}') from e
    _validate(tree)
    code = compile(tree, '<agent-script>', 'exec')

    namespace: dict[str, Any] = {'__builtins__': _SAFE_BUILTINS, 'result': None}
    namespace.update(extra_globals or {})

    box: dict[str, Any] = {}

    current = threading.current_thread

    def _wrap() -> None:
        try:
            exec(code, namespace, namespace)  # noqa: S102 — curated builtins + AST-validated
            box['result'] = namespace.get('result')
        except BaseException as e:  # noqa: BLE001 — capture in-script failure
            box['err'] = e
        finally:
            # If we were marked leaked (finished late after a timeout), clear it.
            with _leaked_lock:
                _leaked.discard(current())

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    t.join(max(0.05, timeout_ms / 1000.0))
    if t.is_alive():
        # A Python thread can't be force-killed; surface the timeout (the daemon
        # thread dies with the process, or removes itself if it finishes late).
        # Subprocess isolation is the prod upgrade. Track it for the DoS backstop.
        with _leaked_lock:
            _leaked.add(t)
        raise SandboxError(f'script exceeded {timeout_ms}ms timeout')
    if 'err' in box:
        # Truncate to avoid leaking internal paths/queries back to the model.
        raise SandboxError(f'{type(box["err"]).__name__}: {box["err"]}'[:200])
    return box.get('result')
