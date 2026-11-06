"""The dashboard's CSP allows no eval and no CDN that compiles styles in the page.

The self-hosted, eval-free Lexical bundle replaced the esm.sh-loaded TipTap, so
esm.sh left the dashboard CSP. Tailwind is a stylesheet built ahead of time
(v0.136.0), so the Play CDN and the `'unsafe-eval'` it needed left too.
"""

import re
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase, override_settings

_REPO = Path(__file__).resolve().parents[2]
# htmx turns these into code with Function(), which a CSP without 'unsafe-eval'
# refuses: a trigger filter (`every 30s [cond]`), an `hx-on` handler, `js:` values.
_HTMX_EVAL = re.compile(
    r'hx-trigger="[^"]*\[|hx-on[:-]|hx-(?:vals|headers)=["\']\s*(?:js|javascript):|hx-vars='
)


class NoEvalInTemplatesTests(SimpleTestCase):
    def test_no_template_asks_htmx_to_evaluate_code(self):
        found = []
        for root in (_REPO / 'plugins', _REPO / 'core', _REPO / 'templates'):
            for path in root.rglob('*.html'):
                for n, line in enumerate(path.read_text(errors='ignore').splitlines(), 1):
                    if _HTMX_EVAL.search(line):
                        found.append(f'{path.relative_to(_REPO)}:{n}')
        self.assertEqual(found, [], 'use data-poll-when-visible or a script in dashboard.js')


@override_settings(CSP_DASHBOARD_ENFORCE=True)
class DashboardCspTests(TestCase):
    def _dashboard_csp(self):
        # Any /dashboard/ path — the middleware sets the header regardless of auth.
        resp = Client().get('/dashboard/')
        return resp.headers.get('Content-Security-Policy', '')

    def test_esm_sh_dropped_from_dashboard_csp(self):
        self.assertNotIn('esm.sh', self._dashboard_csp())

    def test_no_eval_in_the_dashboard(self):
        csp = self._dashboard_csp()
        self.assertTrue(csp, 'the dashboard sent no CSP')
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertNotIn('cdn.tailwindcss.com', csp)
