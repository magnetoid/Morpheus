"""Linda chat layout — the pinned composer and the one-line chip row.

The layout is CSS, but the two things that actually broke in review are
server-rendered template facts and they are cheap to pin:

1. The transcript must be its own scroll container with the composer as a
   sibling flex child, NOT inside the scroller — a composer inside the
   scrolling element scrolls away with the messages.
2. The floating "Open Linda" launcher must not render on Linda's own page,
   where the full composer is already on screen.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

LINDA_URL = '/dashboard/assistant/'


def _staff():
    user = get_user_model().objects.create_user(
        username='linda-layout', email='linda@example.com', password='x'
    )
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user


class LindaChatLayoutTests(TestCase):
    def setUp(self):
        self.client.force_login(_staff())

    def _html(self) -> str:
        resp = self.client.get(LINDA_URL)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_the_composer_is_a_sibling_of_the_scroll_container(self):
        html = self._html()
        log_open = html.index('id="linda-log"')
        log_close = html.index('</div>', html.index('class="linda-empty"'))
        dock = html.index('class="linda-dock"')
        form = html.index('id="linda-form"')
        # The dock and the form both come after the log block closes.
        self.assertGreater(dock, log_close)
        self.assertGreater(form, dock)
        self.assertLess(log_open, dock)

    def test_the_chip_row_is_a_single_scrolling_line(self):
        html = self._html()
        # nowrap + horizontal overflow is what keeps it to one line.
        self.assertIn('id="linda-suggested"', html)
        self.assertIn('flex-wrap: nowrap', html)
        self.assertIn('overflow-x: auto', html)

    def test_the_floating_launcher_is_not_rendered_on_lindas_own_page(self):
        html = self._html()
        self.assertNotIn('id="morph-assistant"', html)
        self.assertNotIn('id="morph-assistant-toggle"', html)

    def test_the_floating_launcher_is_still_rendered_on_other_admin_pages(self):
        """Hiding it must be scoped to Linda's page, not the whole dashboard."""
        resp = self.client.get(reverse('admin_dashboard:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="morph-assistant"', resp.content.decode())

    def test_desktop_sidebar_is_viewport_bounded_not_page_height(self):
        """An expanded nav group must not grow the page and push the composer off-screen.

        The desktop sidebar is ``lg:static`` inside a ``min-h-screen flex`` body,
        so without a height bound a tall (expanded) nav rail stretches the content
        column; the chat composer — an ``absolute; inset:0`` child of #main-content
        — then sits below the fold. The shell pins the rail to the viewport
        (``100dvh``) so its own nav scrolls instead of growing the page.
        """
        import re

        html = self._html()
        rules = ' '.join(re.findall(r'#sidebar\s*\{([^}]*)\}', html))
        self.assertIn('position: sticky', rules)
        self.assertRegex(rules, r'height:\s*100dvh')

    def test_no_django_comment_leaks_into_the_page(self):
        """A multi-line ``{# … #}`` is not a comment and renders as literal text."""
        html = self._html()
        self.assertNotIn('{#', html)
        self.assertNotIn('{% endcomment %}', html)
