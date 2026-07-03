"""Dashboard CSP after the TipTap→Lexical (richtext plugin) cutover.

The self-hosted, eval-free Lexical bundle replaced the esm.sh-loaded TipTap, so
esm.sh is dropped from the dashboard CSP. `'unsafe-eval'` stays — the Tailwind
Play CDN JIT is its remaining owner (precompile-Tailwind follow-up).
"""

from django.test import Client, TestCase, override_settings


@override_settings(CSP_DASHBOARD_ENFORCE=True)
class DashboardCspTests(TestCase):
    def _dashboard_csp(self):
        # Any /dashboard/ path — the middleware sets the header regardless of auth.
        resp = Client().get('/dashboard/')
        return resp.headers.get('Content-Security-Policy', '')

    def test_esm_sh_dropped_from_dashboard_csp(self):
        self.assertNotIn('esm.sh', self._dashboard_csp())

    def test_unsafe_eval_retained_for_tailwind(self):
        self.assertIn("'unsafe-eval'", self._dashboard_csp())
