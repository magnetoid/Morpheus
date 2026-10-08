"""Feedback — staff bug reports that arrive with their own evidence.

A "Send feedback" entry in the dashboard's account dropdown opens a modal that
takes a message, offers to capture the screen, and attaches the JavaScript
errors `core/errors` has already collected. The result is a ticket in
Dashboard → Settings → Feedback.

Both surfaces are **contributions**, never edits to the shell: the menu entry
rides `DASHBOARD_USER_MENU` and the modal rides `DASHBOARD_BODY_END`. The hook
bus skips handlers whose plugin is inactive, so disabling this app removes the
entry and the modal with it (ADR 0024) — there is nothing hardcoded in
admin_dashboard pointing back here.

Plan + decisions: `docs/plans/feedback-tickets-2026-08.md`.
"""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import MorpheusEvents


class FeedbackPlugin(Plugin):
    name = 'feedback'
    label = 'Feedback'
    version = '1.0.0'
    # Declared: views import admin_dashboard's paginate_and_sort, and every
    # surface here (pages, modal, menu entry) renders inside its shell — the
    # app is meaningless without it. Declaring keeps the boundary ratchet green.
    requires = ['admin_dashboard']
    description = (
        'Staff bug reports with a screen capture, the recent JavaScript errors '
        'and page context attached, collected as tickets under Settings.'
    )

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.feedback.urls',
            prefix='dashboard/apps/feedback/',
            namespace='feedback',
        )
        self.register_hook(MorpheusEvents.DASHBOARD_USER_MENU, self.on_user_menu)
        self.register_hook(MorpheusEvents.DASHBOARD_BODY_END, self.on_body_end)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Feedback',
                slug='tickets',
                view='plugins.installed.feedback.views.ticket_list',
                icon='message-square-warning',
                section='developer',
                order=96,
                nav='settings',
                hint='Bug reports staff sent from the dashboard',
            ),
        ]

    # ── contributions ────────────────────────────────────────────────────────

    def on_user_menu(self, value, **kwargs):
        """Append the dropdown entry.

        `href='#'` with a data attribute: the modal is opened by this app's own
        script, so the entry is inert if the script fails rather than navigating
        somewhere that cannot collect a screenshot.
        """
        value.append(
            {
                'label': 'Send feedback',
                'url': '#',
                'icon': 'message-square-warning',
                'order': 50,
                'attrs': {'data-feedback-open': '1'},
            }
        )
        return value

    def on_body_end(self, value, **kwargs):
        value.append('feedback/_modal.html')
        return value
