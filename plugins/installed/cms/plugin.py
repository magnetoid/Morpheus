"""CMS plugin manifest."""
from __future__ import annotations

import logging

from morpheus import Plugin
from morpheus import DashboardPage

logger = logging.getLogger('morpheus.cms')


class CmsPlugin(Plugin):
    name = 'cms'
    label = 'CMS'
    version = '1.0.0'
    description = (
        'Pages, reusable Blocks, named Menus, merchant-defined Forms. '
        'Storefront resolver at /p/<slug>/. Theme-overridable templates: '
        'cms/page.html, cms/_block.html, cms/_menu.html, cms/_form.html. '
        'Form submissions auto-fan-out to CRM as Lead+Interaction.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls('plugins.installed.cms.urls', prefix='', namespace='cms')
        self.register_hook('cms.form_submitted', self.on_form_submitted, priority=50)
        # Theme sections register on import. Pull the active theme's
        # section bundle so the section_registry is populated before
        # any page render tries to look up a section_id. Other themes
        # can opt in the same way; CMS doesn't care which theme is
        # active — it just imports whichever module exists.
        try:
            import importlib
            from django.conf import settings as dj_settings
            theme = getattr(dj_settings, 'MORPHEUS_ACTIVE_THEME', 'dot_books')
            importlib.import_module(f'themes.library.{theme}.sections')
        except Exception as exc:  # noqa: BLE001 — theme may not ship sections
            logger.debug('cms: no sections module for theme: %s', exc)

    def on_form_submitted(self, form, submission, **kwargs):
        """Bridge to CRM if installed: form submission → Lead + Interaction."""
        try:
            from plugins.installed.crm.services import log_interaction, upsert_lead
            email = submission.submitter_email
            if not email:
                return
            lead = upsert_lead(email=email, source='storefront')
            log_interaction(
                subject=lead, kind='note', direction='inbound',
                summary=f'Form submission: {form.label}',
                body=str(submission.payload)[:2000],
                actor_name='cms',
            )
        except Exception as e:  # noqa: BLE001 — CRM may be inactive
            logger.debug('cms: CRM bridge skipped: %s', e)

    def contribute_agent_tools(self) -> list:
        from plugins.installed.cms.agent_tools import (
            create_page_tool, list_pages_tool,
            recent_submissions_tool, upsert_block_tool,
        )
        return [create_page_tool, list_pages_tool,
                upsert_block_tool, recent_submissions_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Pages', slug='pages',
                view='plugins.installed.cms.dashboard.pages_list',
                icon='file-text', section='cms', order=10,
            ),
            DashboardPage(
                label='Blocks', slug='blocks',
                view='plugins.installed.cms.dashboard.blocks_list',
                icon='square', section='cms', order=20,
            ),
            DashboardPage(
                label='Menus', slug='menus',
                view='plugins.installed.cms.dashboard.menus_list',
                icon='list', section='cms', order=30,
            ),
            DashboardPage(
                label='Forms', slug='forms',
                view='plugins.installed.cms.dashboard.forms_list',
                icon='inbox', section='cms', order=40,
            ),
        ]
