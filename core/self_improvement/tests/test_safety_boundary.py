"""Safety boundary contract tests.

These tests are the system's contract with itself. They must pass on every
commit — if a refactor of `core/safety.py` weakens a guard, these tests
go red and the commit is blocked at pre-commit time.

What's verified here:
  1. PROTECTED_PATHS — every category (payments, auth, tax, RBAC, consent,
     migrations, secrets, core, settings, the engine itself) is rejected.
  2. FORBIDDEN_DIFF_PATTERNS — SECRET_KEY/stripe key/destructive SQL/exec.
  3. Magnitude limits — diffs over the line/file thresholds are flagged.
  4. CLASS_BLOCKLIST — pricing/tax/legal/auth/crypto classes refused.
  5. PROTECTED_PLUGINS — soft-brick guard for admin_dashboard/agent_core/rbac.
  6. assert_diff_safe raises on every violation class, with reasons listed.

If a test here goes red, do NOT relax the test — fix the boundary.
"""

from __future__ import annotations

import pytest

from core.safety import (
    CLASS_BLOCKLIST,
    FORBIDDEN_DIFF_PATTERNS,
    LARGE_DIFF_FILE_LIMIT,
    LARGE_DIFF_LINE_LIMIT,
    PROTECTED_PATHS,
    PROTECTED_PLUGINS,
    SafetyViolation,
    assert_diff_safe,
    find_violations,
    is_class_allowed,
    is_path_protected,
    is_plugin_protected,
)

# ---------------------------------------------------------------------------
# Path protection — every category in the boundary contract
# ---------------------------------------------------------------------------


class TestProtectedPaths:
    """Every entry in PROTECTED_PATHS must produce True for at least one
    representative path it should cover."""

    @pytest.mark.parametrize(
        'path',
        [
            # Payments + tax + billing
            'plugins/installed/payments/views.py',
            'plugins/installed/payments/services/stripe.py',
            'plugins/installed/tax/models.py',
            'plugins/installed/gift_cards/views.py',
            'plugins/installed/subscriptions/billing/services.py',
            # Auth + RBAC
            'plugins/installed/rbac/permissions.py',
            'plugins/installed/customers/auth/__init__.py',
            'plugins/installed/customers/auth/views.py',
            'core/auth/views.py',
            'core/auth/services.py',
            'core/authentication.py',
            # Compliance + consent
            'plugins/installed/consent/views.py',
            'plugins/installed/consent/models.py',
            # Core foundational
            'core/hooks.py',
            'core/security_headers.py',
            'core/observability.py',
            'morph/settings.py',
            'morph/celery.py',
            'morph/urls.py',
            'morph/wsgi.py',
            'morph/asgi.py',
            # Migrations — both core and plugin
            'core/migrations/0001_initial.py',
            'core/self_improvement/migrations/0001_initial.py',
            'plugins/installed/storefront/migrations/0042_x.py',
            'foo/bar/migrations/0001.py',
            # Secrets
            '.env',
            '.env.production',
            '.env.local',
            'secrets/oauth.json',
            'plugins/installed/foo/credentials.json',
            'plugins/installed/foo/credentials_token.txt',
            'core/keys/server.pem',
            'core/keys/auth.key',
            # The engine itself (recursive self-protection)
            'core/safety.py',
            'core/self_improvement/recommend.py',
            'core/self_improvement/healers/dep_bump.py',
        ],
    )
    def test_path_is_rejected(self, path: str) -> None:
        assert is_path_protected(path), f'safety boundary failed to protect: {path}'


class TestAllowedPaths:
    """Paths that should slip past the boundary so legitimate AI proposals
    can target them. If one of these starts getting rejected, the boundary
    has grown too wide."""

    @pytest.mark.parametrize(
        'path',
        [
            'plugins/installed/storefront/views.py',
            'plugins/installed/storefront/services.py',
            'plugins/installed/storefront/templates/storefront/cart.html',
            'plugins/installed/seo/services.py',
            'plugins/installed/customers/services.py',
            'plugins/installed/customers/models.py',
            'plugins/installed/marketplace/views.py',
            'themes/library/dot_books/templates/storefront/home.html',
            'themes/library/dot_books/static/css/x.css',
            'docs/plans/whatever.md',
            'README.md',
            # Edge cases — close to protected but not actually protected
            'coreutils/foo.py',
            'submigrations/x.py',
            'plugins/installed/payments_widgets/views.py',  # not payments/
        ],
    )
    def test_path_is_allowed(self, path: str) -> None:
        assert not is_path_protected(path), f'safety boundary over-blocked: {path}'


# ---------------------------------------------------------------------------
# Diff-pattern boundary
# ---------------------------------------------------------------------------


class TestForbiddenDiffPatterns:
    """Every FORBIDDEN_DIFF_PATTERNS entry must catch at least one
    representative diff snippet."""

    @pytest.mark.parametrize(
        ('diff', 'expected_substr'),
        [
            ('+AUTH_PASSWORD_VALIDATORS = []', 'AUTH_PASSWORD_VALIDATORS'),
            ('+SECRET_KEY = "x"', 'SECRET_KEY'),
            ('+ALLOWED_HOSTS = ["*"]', 'ALLOWED_HOSTS'),
            ('+CSRF_TRUSTED_ORIGINS = ["evil.com"]', 'CSRF_TRUSTED_ORIGINS'),
            ('+stripe.api_key = "sk_live_xxx"', 'stripe.api_key'),
            ('+STRIPE_SECRET_KEY = config(...)', 'STRIPE_SECRET'),
            ('+    qs.delete()', '.delete()'),
            ('+DROP TABLE users', 'DROP'),
            ('+TRUNCATE orders', 'TRUNCATE'),
            ('+DELETE FROM x WHERE 1=1', 'DELETE'),
            ('+os.system("rm -rf /")', 'os.system'),
            ('+subprocess.run(cmd)', 'subprocess.'),
            ('+eval(user_input)', 'eval('),
            ('+exec(some_string)', 'exec('),
            ('+__import__("os").system("x")', '__import__'),
            ('+migrations.RunSQL("DROP TABLE x")', 'RunSQL'),
            ('+migrations.RunPython(forwards)', 'RunPython'),
        ],
    )
    def test_pattern_is_flagged(self, diff: str, expected_substr: str) -> None:
        reasons = find_violations(diff, ['plugins/installed/storefront/views.py'])
        assert any(expected_substr.lower() in r.lower() for r in reasons), (
            f'pattern {expected_substr!r} not flagged in {diff!r}; got: {reasons}'
        )


# ---------------------------------------------------------------------------
# Magnitude limits
# ---------------------------------------------------------------------------


class TestMagnitudeLimits:
    def test_line_limit_flagged(self) -> None:
        big = '\n'.join(['+x = 1'] * (LARGE_DIFF_LINE_LIMIT + 1))
        reasons = find_violations(big, ['plugins/installed/storefront/views.py'])
        assert any('too large' in r for r in reasons)

    def test_file_limit_flagged(self) -> None:
        files = [
            f'plugins/installed/storefront/views{i}.py' for i in range(LARGE_DIFF_FILE_LIMIT + 1)
        ]
        reasons = find_violations('+x = 1', files)
        assert any('too many files' in r for r in reasons)

    def test_small_diff_passes(self) -> None:
        small = '\n'.join(['+x = 1'] * 10)
        reasons = find_violations(small, ['plugins/installed/storefront/views.py'])
        assert reasons == []

    def test_file_limit_flagged_for_generator_input(self) -> None:
        # Regression: a one-shot generator was exhausted by the path loop, so
        # the file-count gate silently saw zero files. It must be materialized.
        files = (
            f'plugins/installed/storefront/views{i}.py' for i in range(LARGE_DIFF_FILE_LIMIT + 1)
        )
        reasons = find_violations('+x = 1', files)
        assert any('too many files' in r for r in reasons)


# ---------------------------------------------------------------------------
# Class blocklist
# ---------------------------------------------------------------------------


class TestClassBlocklist:
    @pytest.mark.parametrize('blocked', sorted(CLASS_BLOCKLIST))
    def test_blocked_class_refused(self, blocked: str) -> None:
        assert not is_class_allowed(blocked)

    @pytest.mark.parametrize(
        'allowed',
        ['seo_gap', 'dep_bump', 'cve_patch', 'csp_drift', 'style_fix', 'upstream_sync'],
    )
    def test_allowed_class_passes(self, allowed: str) -> None:
        assert is_class_allowed(allowed)


# ---------------------------------------------------------------------------
# Plugin protection (soft-brick guard)
# ---------------------------------------------------------------------------


class TestPluginProtection:
    @pytest.mark.parametrize('protected', PROTECTED_PLUGINS)
    def test_protected_plugin(self, protected: str) -> None:
        assert is_plugin_protected(protected)

    @pytest.mark.parametrize(
        'togglable', ['storefront', 'seo', 'marketplace', 'flipbook', 'webstories']
    )
    def test_togglable_plugin(self, togglable: str) -> None:
        assert not is_plugin_protected(togglable)


# ---------------------------------------------------------------------------
# assert_diff_safe — the final gate
# ---------------------------------------------------------------------------


class TestAssertDiffSafe:
    def test_safe_diff_passes(self) -> None:
        # Should NOT raise.
        assert_diff_safe(
            '+def hello(): return "hi"',
            ['plugins/installed/storefront/views.py'],
        )

    def test_protected_path_raises(self) -> None:
        with pytest.raises(SafetyViolation) as exc:
            assert_diff_safe('+x = 1', ['plugins/installed/payments/services.py'])
        assert any('payments' in r for r in exc.value.reasons)

    def test_forbidden_pattern_raises(self) -> None:
        with pytest.raises(SafetyViolation) as exc:
            assert_diff_safe('+SECRET_KEY = "x"', ['plugins/installed/storefront/foo.py'])
        assert any('SECRET_KEY' in r for r in exc.value.reasons)

    def test_multiple_reasons_all_listed(self) -> None:
        # Path is protected AND pattern is forbidden — both reasons must appear.
        with pytest.raises(SafetyViolation) as exc:
            assert_diff_safe(
                '+SECRET_KEY = "x"',
                ['plugins/installed/payments/foo.py'],
            )
        joined = ' '.join(exc.value.reasons)
        assert 'payments' in joined
        assert 'SECRET_KEY' in joined


# ---------------------------------------------------------------------------
# Boundary-completeness invariants — guard against accidental shrinkage
# ---------------------------------------------------------------------------


class TestBoundaryInvariants:
    """If someone deletes a PROTECTED_PATHS entry, these tests notice."""

    def test_payments_protected(self) -> None:
        assert any('payments' in p for p in PROTECTED_PATHS)

    def test_auth_protected(self) -> None:
        # At least one of: core/auth/, customers/auth, core/authentication.py
        joined = ' '.join(PROTECTED_PATHS)
        assert 'auth' in joined

    def test_migrations_protected(self) -> None:
        assert any('migrations' in p for p in PROTECTED_PATHS)

    def test_engine_self_protected(self) -> None:
        assert any('self_improvement' in p for p in PROTECTED_PATHS)
        assert any(p == 'core/safety.py' for p in PROTECTED_PATHS)

    def test_no_forbidden_patterns_removed(self) -> None:
        # Every category of dangerous pattern must still be represented.
        # Matched against the raw regex strings (so dots etc. appear escaped).
        joined = ' '.join(FORBIDDEN_DIFF_PATTERNS)
        for required in (
            'SECRET_KEY',
            'stripe',
            'DROP',
            r'os\.system',
            'eval',
            'exec',
            'RunSQL',
        ):
            assert required in joined, f'forbidden pattern lost: {required}'


class TestExtraProtectedPaths:
    """settings.SELF_IMPROVEMENT['extra_protected_paths'] extends (never
    relaxes) the static boundary — it was a dead knob until July 2026."""

    def test_extra_paths_are_honored(self) -> None:
        from django.test import override_settings

        from core.safety import is_path_protected

        assert not is_path_protected('plugins/installed/payments_v2/models.py')
        with override_settings(
            SELF_IMPROVEMENT={'extra_protected_paths': ('plugins/installed/payments_v2/',)}
        ):
            assert is_path_protected('plugins/installed/payments_v2/models.py')
        # Back out of the override → protection gone again (no sticky cache).
        assert not is_path_protected('plugins/installed/payments_v2/models.py')

    def test_static_boundary_unaffected_by_settings(self) -> None:
        from django.test import override_settings

        from core.safety import is_path_protected

        with override_settings(SELF_IMPROVEMENT={'extra_protected_paths': ()}):
            assert is_path_protected('core/safety.py')


class TestPrecommitSubset:
    """PRECOMMIT_FORBIDDEN_PATTERNS — the human-applicable subset enforced
    by scripts/check_forbidden_diff.py on staged added lines."""

    def test_catches_hardcoded_secrets_and_destructive_sql(self) -> None:
        import re

        from core.safety import PRECOMMIT_FORBIDDEN_PATTERNS

        compiled = [re.compile(p) for p in PRECOMMIT_FORBIDDEN_PATTERNS]

        def hits(line: str) -> bool:
            return any(p.search(line) for p in compiled)

        assert hits("SECRET_KEY = 'django-insecure-abc123'")
        assert hits('stripe.api_key = "sk_live_x"')
        assert hits('cursor.execute("DROP TABLE orders")')
        assert hits("os.system('rm -rf /tmp/x')")
        # …but everyday idioms humans legitimately commit stay allowed:
        assert not hits("SECRET_KEY = config('SECRET_KEY')")
        assert not hits('stale_rows.delete()')
        assert not hits('subprocess.run([...], check=False)')
        assert not hits('parse_llm_json = eval_safe(text)')

    def test_precommit_script_parses_added_lines(self) -> None:
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            'check_forbidden_diff',
            Path(__file__).resolve().parents[3] / 'scripts' / 'check_forbidden_diff.py',
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        diff = (
            'diff --git a/x.py b/x.py\n'
            '--- a/x.py\n'
            '+++ b/x.py\n'
            '@@ -1 +1,2 @@\n'
            '+added = 1\n'
            '-removed = 2\n'
        )
        assert mod.added_lines(diff) == [('x.py', 'added = 1')]
