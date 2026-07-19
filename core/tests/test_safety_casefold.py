"""Regression: `is_path_protected` must match case-INSENSITIVELY.

On a case-insensitive filesystem (macOS/Windows dev, some CI) a request for
`.ENV` or `CORE/auth/...` resolves to and opens the real protected file, but
the old case-sensitive pattern let it through (hunt #22). The fix compiles the
PROTECTED_PATHS patterns with `re.IGNORECASE`, which only ever widens
protection (fail-closed) and must not over-widen to unrelated paths.

Protected entries asserted below are real members of
`core.safety.PROTECTED_PATHS` ('.env', 'core/auth/'); the negative path
('plugins/installed/catalog/') is deliberately absent from it.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.safety import is_path_protected


class PathProtectionCaseFoldTests(SimpleTestCase):
    def test_exact_lowercase_is_protected(self):
        # Sanity: the canonical lowercase form has always been protected.
        self.assertTrue(is_path_protected('.env'))

    def test_uppercase_secret_is_protected(self):
        # The fix: `.ENV` resolves to `.env` on a case-insensitive FS.
        self.assertTrue(is_path_protected('.ENV'))

    def test_mixed_case_secret_is_protected(self):
        self.assertTrue(is_path_protected('.Env'))

    def test_protected_subtree_lowercase(self):
        self.assertTrue(is_path_protected('core/auth/models.py'))

    def test_protected_subtree_first_segment_case_variance(self):
        # First path segment upper-cased still maps to the protected subtree.
        self.assertTrue(is_path_protected('CORE/auth/models.py'))

    def test_unprotected_path_stays_unprotected_lowercase(self):
        # Case-insensitivity must not over-widen to an unrelated plugin.
        self.assertFalse(is_path_protected('plugins/installed/catalog/models.py'))

    def test_unprotected_path_stays_unprotected_uppercase(self):
        self.assertFalse(is_path_protected('PLUGINS/installed/catalog/models.py'))
