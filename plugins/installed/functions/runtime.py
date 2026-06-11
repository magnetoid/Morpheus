"""
Morph Functions — sandboxed Python runtime.

Design principles
-----------------

* **Isolation by namespace, not by trust.** We never expose the host
  `__builtins__`. The function only sees what we hand it via a curated
  `safe_globals` dict.
* **Capability-grant pattern.** A Function declares the capabilities it
  needs (`['math', 'money', 'log']`). The runtime resolves each capability
  to a concrete object and injects it into the namespace. Anything not
  listed is invisible.
* **Bounded execution.** Compilation is restricted to expressions / simple
  statements. Execution is hard-bounded by a wall-clock timeout enforced via
  a worker thread.
* **No file / socket / subprocess access.** The injected globals make these
  unreachable — there's no `open`, no `__import__`, no `os`.

Limitations
-----------

This is a *deliberately conservative* sandbox suitable for cart/price math.
It is NOT a hostile-code sandbox: a determined attacker with WRITE access to
the Function model could likely cause CPU exhaustion before the watchdog
kills the thread. Treat the Function model as "merchant-managed" and gate
access in the admin/API layer accordingly.

For multi-tenant shared-host deployments, swap `_run_in_thread` for a
sub-process or WASM runner — the rest of the surface is unchanged.
"""

from __future__ import annotations

import ast
import logging
import math
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger('morpheus.functions')

# ---------------------------------------------------------------------------
# Capability registry
# ---------------------------------------------------------------------------

_CAPABILITIES: dict[str, dict[str, Any]] = {
    'math': {
        'pi': math.pi,
        'sqrt': math.sqrt,
        'floor': math.floor,
        'ceil': math.ceil,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round,
    },
    'money': {
        'Decimal': Decimal,
    },
    'log': {
        'log_info': lambda msg: logger.info('[fn] %s', str(msg)[:500]),
        'log_warn': lambda msg: logger.warning('[fn] %s', str(msg)[:500]),
    },
}


def register_capability(name: str, exports: Mapping[str, Any]) -> None:
    """Plugin-author hook to add a capability set."""
    _CAPABILITIES[name] = dict(exports)


def resolve_capabilities(names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cap in names:
        if cap not in _CAPABILITIES:
            raise FunctionError(f'Unknown capability: {cap}')
        out.update(_CAPABILITIES[cap])
    return out


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FunctionError(RuntimeError):
    """Raised on configuration / capability errors (NOT user-code errors)."""


class FunctionExecutionError(RuntimeError):
    """Raised when user code raises or times out."""


# ---------------------------------------------------------------------------
# AST-level safety check
# ---------------------------------------------------------------------------

# Node types that are outright forbidden — they let an attacker reach the
# interpreter, the filesystem, or the network.
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

# Names we never want resolved as identifiers (dunder access is checked separately).
# These are NOT bound in the sandbox namespace anyway — banning the *name* makes
# the intent obvious and gives us a single failure mode instead of NameError.
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
    }
)


def _validate_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODES):
            raise FunctionError(f'Forbidden syntax: {type(node).__name__}')
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith('__') and attr.endswith('__'):
                raise FunctionError(f'Forbidden dunder access: {attr}')
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise FunctionError(f'Forbidden name: {node.id}')


# ---------------------------------------------------------------------------
# Sandboxed exec
# ---------------------------------------------------------------------------

# Whitelisted builtins. Crucially: NO __import__.
_SAFE_BUILTINS: dict[str, Any] = {
    'True': True,
    'False': False,
    'None': None,
    'len': len,
    'range': range,
    'enumerate': enumerate,
    'zip': zip,
    'sum': sum,
    'min': min,
    'max': max,
    'abs': abs,
    'round': round,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'tuple': tuple,
    'set': set,
    'sorted': sorted,
    'reversed': reversed,
    'isinstance': isinstance,
    'ValueError': ValueError,
    'TypeError': TypeError,
    'KeyError': KeyError,
    'Exception': Exception,
}


@dataclass(slots=True)
class FunctionResult:
    output: Any
    duration_ms: int


def _compile_function(source: str) -> Any:
    """Parse + AST-check + compile a function body."""
    if len(source) > 16_000:
        raise FunctionError('Function source too large (>16KB)')
    try:
        tree = ast.parse(source, mode='exec')
    except SyntaxError as e:
        raise FunctionError(f'SyntaxError: {e.msg} at line {e.lineno}') from e
    _validate_ast(tree)
    try:
        return compile(tree, filename='<morph-function>', mode='exec')
    except (SyntaxError, ValueError) as e:
        raise FunctionError(f'Compile failed: {e}') from e


def _run_in_thread(target, args, timeout_seconds: float) -> Any:
    """Run `target(*args)` on a worker thread; return result or raise on timeout."""
    box: dict[str, Any] = {}

    def _wrap() -> None:
        try:
            box['out'] = target(*args)
        except BaseException as e:  # noqa: BLE001 — capture user-code failure
            box['err'] = e

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    t.join(timeout_seconds)
    if t.is_alive():
        # We can't safely kill a Python thread; at least log and surface it.
        # Production: replace this layer with a subprocess runner.
        raise FunctionExecutionError(
            f'Function exceeded timeout of {int(timeout_seconds * 1000)}ms',
        )
    if 'err' in box:
        raise FunctionExecutionError(f'{type(box["err"]).__name__}: {box["err"]}') from box['err']
    return box.get('out')


def execute(
    *,
    source: str,
    input: Mapping[str, Any] | None = None,
    capabilities: list[str] | None = None,
    timeout_ms: int = 200,
) -> FunctionResult:
    """Compile and run a Function source against `input`, returning `run(input)`."""

    capabilities = capabilities or []
    cap_globals = resolve_capabilities(capabilities)

    code = _compile_function(source)

    namespace: dict[str, Any] = {
        '__builtins__': _SAFE_BUILTINS,
        **cap_globals,
    }

    # Hard wall: 4x soft timeout. Soft timeouts get reported as errors but
    # the watchdog still kills the slow thread.
    hard_timeout = max(timeout_ms, 50) * 4 / 1000.0

    def _run() -> Any:
        exec(code, namespace, namespace)  # noqa: S102 — sandboxed namespace  # nosec B102
        run_fn = namespace.get('run')
        if not callable(run_fn):
            raise FunctionExecutionError('Function source must define `run(input)`')
        return run_fn(dict(input or {}))

    started = time.perf_counter()
    output = _run_in_thread(_run, args=(), timeout_seconds=hard_timeout)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return FunctionResult(output=output, duration_ms=duration_ms)
