"""Static safety scan for agent-DRAFTED code (uplift Phase 4).

`scan_source` does AST-only analysis — it NEVER imports or executes the
candidate source. It flags the May-2026 AI-generated-code risks: dangerous
calls (eval/exec/os.system/subprocess/…), hallucinated/slopsquatted imports
(an import that resolves to neither stdlib, an installed package, nor a repo
module), SQL built by f-string, and the wrong shape (a tool draft with no
``@tool``). Findings gate whether a CodeProposal is allowed to proceed to the
(separate, gated) apply step.
"""

from __future__ import annotations

import ast
import importlib.util
import sys

MAX_SOURCE_BYTES = 40_000
_REPO_PREFIXES = ('core', 'plugins', 'morph', 'themes', 'api', 'morpheus')

# Bare names that are dangerous to call in generated module code.
_DANGER_NAMES = frozenset({'eval', 'exec', 'compile', '__import__', 'breakpoint', 'input'})
# dotted calls: <module>.<attr> that reach the OS / deserialise untrusted bytes.
_DANGER_DOTTED = {
    ('os', 'system'),
    ('os', 'popen'),
    ('os', 'remove'),
    ('os', 'rmdir'),
    ('subprocess', 'run'),
    ('subprocess', 'call'),
    ('subprocess', 'Popen'),
    ('subprocess', 'check_output'),
    ('subprocess', 'check_call'),
    ('pickle', 'load'),
    ('pickle', 'loads'),
    ('marshal', 'loads'),
    ('shutil', 'rmtree'),
}


def _finding(severity, code, message):
    return {'severity': severity, 'code': code, 'message': message}


def _imported_top_levels(tree):
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split('.', 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split('.', 1)[0])  # skip relative imports
    return names


def _import_resolves(top: str) -> bool:
    if top in _REPO_PREFIXES or top in getattr(sys, 'stdlib_module_names', ()):
        return True
    try:
        return importlib.util.find_spec(top) is not None
    except Exception:  # noqa: BLE001 — a broken/partial package counts as "present"
        return True


def scan_source(source: str, *, kind: str = 'tool') -> list[dict]:  # noqa: PLR0912 — flat scanner; branches are the checks
    """Return a list of findings (possibly empty). Pure static analysis."""
    findings: list[dict] = []
    if not isinstance(source, str) or not source.strip():
        return [_finding('CRITICAL', 'empty', 'empty source')]
    if len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
        findings.append(_finding('HIGH', 'too_large', 'source exceeds 40KB'))

    try:
        tree = ast.parse(source, mode='exec')
    except SyntaxError as e:
        return [_finding('CRITICAL', 'syntax', f'SyntaxError: {e.msg} at line {e.lineno}')]

    for node in ast.walk(tree):
        # Dangerous bare-name calls.
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _DANGER_NAMES:
                findings.append(_finding('HIGH', 'danger_call', f'forbidden call: {fn.id}()'))
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                pair = (fn.value.id, fn.attr)
                if pair in _DANGER_DOTTED:
                    findings.append(
                        _finding('HIGH', 'danger_call', f'forbidden call: {pair[0]}.{pair[1]}()')
                    )
                # SQL injection: .execute(f"...") / .raw(f"...").
                if fn.attr in ('execute', 'raw', 'extra') and any(
                    isinstance(a, ast.JoinedStr) for a in node.args
                ):
                    findings.append(
                        _finding(
                            'HIGH',
                            'sql_fstring',
                            f'{fn.attr}() built from an f-string (SQL injection risk)',
                        )
                    )
        # XSS: mark_safe on a non-literal.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'mark_safe'
            and node.args
            and not isinstance(node.args[0], ast.Constant)
        ):
            findings.append(
                _finding('HIGH', 'mark_safe', 'mark_safe() on dynamic content (XSS risk)')
            )

    # Hallucinated / slopsquatted imports.
    for top in sorted(_imported_top_levels(tree)):
        if not _import_resolves(top):
            findings.append(
                _finding(
                    'HIGH',
                    'unknown_import',
                    f'import {top!r} resolves to nothing — verify it exists',
                )
            )

    # Shape: a tool draft should define a function decorated with @tool.
    if kind == 'tool':
        has_tool = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    target = dec.func if isinstance(dec, ast.Call) else dec
                    nm = target.id if isinstance(target, ast.Name) else getattr(target, 'attr', '')
                    if nm == 'tool':
                        has_tool = True
        if not has_tool:
            findings.append(_finding('MEDIUM', 'no_tool', 'no @tool-decorated function found'))

    return findings


def passed(findings: list[dict]) -> bool:
    """True when nothing blocking (CRITICAL/HIGH) was found."""
    return not any(f.get('severity') in ('CRITICAL', 'HIGH') for f in (findings or []))
