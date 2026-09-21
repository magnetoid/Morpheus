"""CMS plugin manifest."""
# ruff: noqa: PLC0415, I001 — inline imports are load-order-safe (CRM optional, agent tools lazy).

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

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
        # Parameterised page CRUD under /dashboard/cms/ (new/edit/duplicate/delete).
        # The Pages LIST stays at /dashboard/apps/cms/pages/ via
        # contribute_dashboard_pages; these are the actions it links to.
        self.register_urls(
            'plugins.installed.cms.urls_dashboard',
            prefix='dashboard/cms/',
            namespace='cms_dashboard',
        )
        # Read + write GraphQL surface for Pages/Blocks (gated cms.read / cms.write).
        self.register_graphql_extension('plugins.installed.cms.graphql.queries')
        self.register_hook(events.CMS_FORM_SUBMITTED, self.on_form_submitted, priority=50)
        # Supply merchant-edited transactional-email copy to core.emails.
        self.register_hook(
            events.EMAIL_TEMPLATE_OVERRIDE, self.on_email_template_override, priority=50
        )
        # Supply merchant-edited intro copy for the built-in storefront listing
        # pages (/products/, /vendors/, /journal/) from Block rows.
        self.register_hook(events.STOREFRONT_PAGE_INTRO, self.on_storefront_page_intro, priority=50)

        # FAQPage for a journal article, into the page's one JSON-LD graph —
        # built only from H2s that are genuinely questions (see seo_graph.py).
        from plugins.installed.cms.seo_graph import on_seo_jsonld_graph

        self.register_hook(events.SEO_JSONLD_GRAPH, on_seo_jsonld_graph, priority=50)
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

    def on_storefront_page_intro(self, value, page=None, **kwargs):
        """Supply the intro copy for a built-in storefront listing page.

        Subscribes to ``STOREFRONT_PAGE_INTRO`` (a filter): look up the active
        ``Block`` keyed ``<page>_intro`` and return its body as the page's
        editorial intro, plus an optional ``metadata['meta_description']``
        override. Leaves ``value`` untouched when no row matches, so the theme
        keeps its static fallback copy.
        """
        if not page or (value and value.get('body')):
            return value
        from plugins.installed.cms.models import Block

        try:
            block = Block.objects.filter(key=f'{page}_intro', is_active=True).first()
        except Exception:  # noqa: BLE001 — model not migrated yet, etc.
            return value
        if block is None:
            return value
        meta = block.metadata if isinstance(block.metadata, dict) else {}
        return {
            'body': (block.body or '').strip(),
            'meta_description': (meta.get('meta_description') or '').strip(),
        }

    def on_email_template_override(self, value, key=None, ctx=None, **kwargs):
        """Supply merchant-edited copy for a transactional email.

        Subscribes to ``EMAIL_TEMPLATE_OVERRIDE`` (a filter): look up an
        active ``EmailTemplate`` row for ``key`` and return the rendered
        ``(subject, body_text, body_html)``. Renders through the Django
        engine so the same ``{{ order.... }}`` placeholders work in
        DB-stored copy. Leaves ``value`` untouched when another plugin
        already supplied copy or no row matches.
        """
        if value and any(v is not None for v in value):
            return value
        from django.template import Context, Template
        from plugins.installed.cms.models import EmailTemplate

        try:
            tpl = EmailTemplate.objects.filter(key=key, is_active=True).first()
        except Exception:  # noqa: BLE001 — model not migrated yet, etc.
            return value
        if tpl is None:
            return value
        ctx = ctx or {}
        try:
            d_ctx = Context(ctx, autoescape=False)
            subject = Template(tpl.subject or '').render(d_ctx) if tpl.subject else None
            text = Template(tpl.body_text or '').render(d_ctx) if tpl.body_text else None
            html = (
                Template(tpl.body_html).render(Context(ctx, autoescape=True))
                if tpl.body_html
                else None
            )
        except Exception as e:  # noqa: BLE001 — bad merchant template shouldn't kill the send
            logger.warning('cms: email template %s render failed: %s', key, e)
            return value
        return (subject, text, html)

    def on_form_submitted(self, form, submission, **kwargs):
        """Bridge to CRM if installed: form submission → Lead + Interaction."""
        try:
            from plugins.installed.crm.services import log_interaction, upsert_lead

            email = submission.submitter_email
            if not email:
                return
            lead = upsert_lead(email=email, source='storefront')
            log_interaction(
                subject=lead,
                kind='note',
                direction='inbound',
                summary=f'Form submission: {form.label}',
                body=str(submission.payload)[:2000],
                actor_name='cms',
            )
        except Exception as e:  # noqa: BLE001 — CRM may be inactive
            logger.debug('cms: CRM bridge skipped: %s', e)

    def contribute_agent_tools(self) -> list:
        from plugins.installed.cms.agent_tools import (
            cms_pages_tool,
            cms_publish_page_tool,
            cms_unpublish_page_tool,
            create_page_tool,
            delete_page_tool,
            email_templates_tool,
            get_page_tool,
            list_pages_tool,
            recent_submissions_tool,
            update_page_tool,
            upsert_block_tool,
        )

        return [
            create_page_tool,
            get_page_tool,
            list_pages_tool,
            update_page_tool,
            delete_page_tool,
            upsert_block_tool,
            recent_submissions_tool,
            cms_pages_tool,
            cms_publish_page_tool,
            cms_unpublish_page_tool,
            email_templates_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Pages',
                slug='pages',
                view='plugins.installed.cms.dashboard.pages_list',
                icon='file-text',
                section='cms',
                order=10,
            ),
            DashboardPage(
                label='Blocks',
                slug='blocks',
                view='plugins.installed.cms.dashboard.blocks_list',
                icon='square',
                section='cms',
                order=20,
            ),
            DashboardPage(
                label='Menus',
                slug='menus',
                view='plugins.installed.cms.dashboard.menus_list',
                icon='list',
                section='cms',
                order=30,
            ),
            DashboardPage(
                label='Forms',
                slug='forms',
                view='plugins.installed.cms.dashboard.forms_list',
                icon='inbox',
                section='cms',
                order=40,
            ),
        ]
