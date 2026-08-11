"""Morpheus Brain — a read-only intelligence console under Settings.

Aggregates every analysis / evaluation / health signal the platform already
produces (plugin registry, the self-improvement loop, code proposals, the SEO
audit, Core Web Vitals, merchant insights) into one tabbed page. It owns no
data and writes nothing — every source is read defensively, so a disabled
plugin or a missing engine degrades to "unavailable" rather than breaking the
page. Future plugins can surface extra cards here via a BRAIN_PANELS filter
(see views._extension_panels) without editing this plugin.
"""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events


class MorpheusBrainPlugin(Plugin):
    name = 'morpheus_brain'
    label = 'Morpheus Brain'
    version = '1.0.0'
    description = (
        'The central intelligence console for the platform. Aggregates code '
        'quality, system errors, SEO health, and daily AI-driven industry reports '
        'into one view, plus a long-form AI advisory briefing on the whole site.'
    )
    has_models = True

    def ready(self) -> None:
        # Contribute the daily AI reports to the core Brain signal snapshot.
        # DailyReport is THIS plugin's data; the aggregator that renders it
        # lives in core/brain/ (the kernel owns the console, the plugin owns
        # the reports). Disable this plugin → the Reports panel goes away.
        self.register_hook(events.BRAIN_SIGNALS, self.on_brain_signals, priority=50)
        # The Brain *engine* lives in core/brain/ (core, non-disableable). This
        # surface schedules its continuous AI analysis (Celery beat) and imports
        # the task so Celery discovers it. No cost when no AI is configured.
        from django.conf import settings

        import core.brain.tasks  # noqa: F401 — registers @shared_task
        import plugins.installed.morpheus_brain.tasks  # noqa: F401 — registers @shared_task

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None)
        if isinstance(schedule, dict):
            schedule.setdefault(
                'brain.refresh_analysis',
                {'task': 'core.brain.refresh_analysis', 'schedule': 60 * 60 * 6},
            )
            # Long-form advisory briefing — once daily (it's a heavier LLM call
            # than the structured analysis and doesn't need 6-hour freshness;
            # the "Regenerate briefing" button covers on-demand).
            schedule.setdefault(
                'brain.generate_briefing',
                {'task': 'morpheus_brain.generate_briefing', 'schedule': 60 * 60 * 24},
            )

    def on_brain_signals(self, value, **kwargs):
        """Merge the daily AI reports into the Brain snapshot (→ reports). Core
        seeds reports={'available': False}; publishing them here flips it to
        available so a disabled plugin shows 'Reports service unavailable'."""
        from contextlib import suppress  # noqa: PLC0415

        reports = value.setdefault('reports', {})
        reports['available'] = True
        reports['reports'] = []
        with suppress(Exception):
            from plugins.installed.morpheus_brain.models import DailyReport  # noqa: PLC0415

            rows = DailyReport.objects.filter(is_published=True).order_by('-published_at')[:10]
            reports['reports'] = [
                {
                    'id': str(r.id),
                    'title': r.title,
                    'category': r.get_category_display(),
                    'summary': r.summary,
                    'content': r.content,
                    'published_at': r.published_at,
                    'references': [
                        {'title': ref.title, 'url': ref.url} for ref in r.references.all()
                    ],
                }
                for r in rows
            ]
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Morpheus Brain',
                slug='brain',
                view='plugins.installed.morpheus_brain.views.brain',
                icon='brain',
                section='settings',
                order=90,
                nav='settings',
            ),
        ]
