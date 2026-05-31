"""Single source of truth for what AI-driven code changes may touch.

Read by:
  - core/self_improvement/ (recommend.py pre-plan filter, heal.py pre-execute)
  - plugins/installed/agent_mcp/ (Bearer-scoped code modification gates)
  - .pre-commit hooks (forbidden-pattern grep on staged diffs)
  - permission-boundary tests (every code-touching surface must assert it
    rejects writes inside PROTECTED_PATHS)

The contract: anything an AI agent might want to modify is checked against
these constants. If a path or diff pattern matches, the change is rejected
*before* it reaches `gh pr create`, not after.

Why a module, not a JSONField: the boundary must be read by static tools
(pre-commit hooks, CI) that cannot import Django. Plain Python tuples +
constants keep this importable from anywhere.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Filesystem boundary
# ---------------------------------------------------------------------------

# Paths the engine refuses to propose changes to. Glob-style — see
# `is_path_protected()` for matcher semantics.
PROTECTED_PATHS: tuple[str, ...] = (
    # Payments + tax + billing — financial correctness
    'plugins/installed/payments/',
    'plugins/installed/tax/',
    'plugins/installed/gift_cards/',
    'plugins/installed/subscriptions/billing',
    # Auth + RBAC — security
    'plugins/installed/rbac/',
    'plugins/installed/customers/auth',
    'core/auth/',
    'core/authentication.py',
    # Compliance + consent — legal
    'plugins/installed/consent/',
    # Core foundational
    'core/',
    'morph/settings.py',
    'morph/celery.py',
    'morph/urls.py',
    'morph/wsgi.py',
    'morph/asgi.py',
    # Migrations — irreversible by nature
    '**/migrations/',
    # Secrets
    '.env',
    '.env.*',
    'secrets/',
    '**/credentials*',
    '**/*.pem',
    '**/*.key',
    # The engine itself can't propose changes to its own safety boundary
    'core/safety.py',
    'core/self_improvement/',
)

# Plugins that cannot be disabled without soft-bricking the system.
# Per MEMORY.md plugin_toggle_softbrick.
PROTECTED_PLUGINS: tuple[str, ...] = (
    'admin_dashboard',
    'agent_core',
    'rbac',
    'customers',
)

# ---------------------------------------------------------------------------
# Diff-pattern boundary
# ---------------------------------------------------------------------------

# Regex patterns that, if matched in a proposed diff, immediately reject it.
# Layered after the path check so even a permitted path can't smuggle in a
# dangerous pattern.
FORBIDDEN_DIFF_PATTERNS: tuple[str, ...] = (
    # Auth / crypto fundamentals
    r'AUTH_PASSWORD_VALIDATORS',
    r'SECRET_KEY\s*=',
    r'ALLOWED_HOSTS\s*=',
    r'CSRF_TRUSTED_ORIGINS\s*=',
    # Payment processor keys
    r'stripe\.api_key\s*=',
    r'STRIPE_SECRET',
    # Destructive SQL / ORM
    r'\.delete\(\)',
    r'DROP\s+TABLE',
    r'TRUNCATE\b',
    r'DELETE\s+FROM',
    # Code execution
    r'\bos\.system\b',
    r'\bsubprocess\.',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'__import__\s*\(',
    # Migration ops (separately gated; never auto-applied)
    r'migrations\.RunSQL',
    r'migrations\.RunPython',
)

# Issue classes the engine refuses to even analyze.
CLASS_BLOCKLIST: frozenset[str] = frozenset(
    {
        'pricing_change',
        'tax_rate_change',
        'legal_copy',
        'terms_of_service',
        'refund_policy',
        'gdpr_consent_flow',
        'auth_logic',
        'crypto_code',
        'permissions_matrix',
    }
)

# ---------------------------------------------------------------------------
# Magnitude limits
# ---------------------------------------------------------------------------

# A proposed change touching more than this many lines or files is
# automatically downgraded to `advise` — too large to auto-apply safely.
LARGE_DIFF_LINE_LIMIT: int = 200
LARGE_DIFF_FILE_LIMIT: int = 5


# ---------------------------------------------------------------------------
# Exception + helpers
# ---------------------------------------------------------------------------


class SafetyViolation(Exception):
    """Raised when a proposed change crosses the safety boundary.

    Carries the list of specific violations so the audit log can record
    every reason a change was rejected, not just the first one.
    """

    def __init__(self, reasons: Iterable[str]):
        self.reasons: list[str] = list(reasons)
        super().__init__('; '.join(self.reasons) or 'safety boundary violated')


_COMPILED_FORBIDDEN = tuple(re.compile(pat) for pat in FORBIDDEN_DIFF_PATTERNS)


def _compile_path_pattern(pat: str) -> re.Pattern[str]:
    """Compile a PROTECTED_PATHS entry to a fullmatch regex.

    Syntax (deterministic, no fnmatch dependency):
      - leading `**/` — match the rest at any depth (`(?:.*/)?` prefix)
      - trailing `/`  — directory prefix; matches any descendant
      - `*` inside    — glob, single path segment only (`[^/]*`)
      - plain entry   — matches the entry itself OR anything under it as a subtree
    """
    if pat.startswith('**/'):
        rest = pat[3:]
        prefix = r'(?:.*/)?'
    else:
        rest = pat
        prefix = r''

    if rest.endswith('/'):
        # directory pattern — match the dir itself or any descendant
        body = re.escape(rest[:-1]).replace(r'\*', r'[^/]*')
        regex = f'^{prefix}{body}(?:/.*)?$'
    else:
        body = re.escape(rest).replace(r'\*', r'[^/]*')
        regex = f'^{prefix}{body}(?:/.+)?$'

    return re.compile(regex)


_COMPILED_PROTECTED = tuple(_compile_path_pattern(p) for p in PROTECTED_PATHS)


def is_path_protected(path: str) -> bool:
    """Return True if `path` falls inside any PROTECTED_PATHS entry.

    Matching uses the compiled regex set above. Patterns are checked in
    PROTECTED_PATHS order; the first match wins.
    """
    norm = path.removeprefix('./')
    return any(p.match(norm) for p in _COMPILED_PROTECTED)


def find_violations(diff_text: str, files_touched: Iterable[str] = ()) -> list[str]:
    """Return human-readable reasons the diff violates the safety boundary.

    Empty list means the diff is safe. Used by both `assert_diff_safe()` and
    the pre-commit / CI hook (which logs reasons without raising).
    """
    reasons: list[str] = []

    # Path check
    for path in files_touched:
        if is_path_protected(path):
            reasons.append(f'protected path: {path}')

    # Pattern check on the diff body
    for compiled in _COMPILED_FORBIDDEN:
        match = compiled.search(diff_text)
        if match:
            reasons.append(f'forbidden pattern: {match.group(0)!r}')

    # Magnitude
    line_count = sum(
        1
        for line in diff_text.splitlines()
        if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))
    )
    if line_count > LARGE_DIFF_LINE_LIMIT:
        reasons.append(f'diff too large: {line_count} lines > {LARGE_DIFF_LINE_LIMIT}')

    file_count = len(set(files_touched))
    if file_count > LARGE_DIFF_FILE_LIMIT:
        reasons.append(f'diff touches too many files: {file_count} > {LARGE_DIFF_FILE_LIMIT}')

    return reasons


def assert_diff_safe(diff_text: str, files_touched: Iterable[str] = ()) -> None:
    """Raise SafetyViolation if the diff crosses the boundary; return None otherwise.

    Use this as the final gate before any `gh pr create` or `git apply` call.
    Layered enforcement (per the architectural plan §10):
      1. Pre-plan filter in recommend.py rejects clusters in PROTECTED_PATHS.
      2. The LLM prompt advises the constraints (advisory only).
      3. *This function* enforces them programmatically after the LLM returns.
      4. Pre-commit / CI hooks re-run this check on staged diffs.
      5. Permission boundary tests verify the rejection path.
    """
    reasons = find_violations(diff_text, files_touched)
    if reasons:
        raise SafetyViolation(reasons)


def is_class_allowed(class_name: str) -> bool:
    """Return True if `class_name` is NOT in the blocklist."""
    return class_name not in CLASS_BLOCKLIST


def is_plugin_protected(plugin_name: str) -> bool:
    """Return True if `plugin_name` cannot be disabled (soft-brick risk)."""
    return plugin_name in PROTECTED_PLUGINS
