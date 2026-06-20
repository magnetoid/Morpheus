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

from morpheus import DashboardPage, Plugin


class MorpheusBrainPlugin(Plugin):
    name = 'morpheus_brain'
    label = 'Morpheus Brain'
    version = '1.0.0'
    description = (
        'Settings → Morpheus Brain: a unified, tabbed view of plugin health, '
        'code analysis, content & SEO, storefront performance, and improvement '
        'recommendations — aggregated read-only from existing engines.'
    )
    has_models = False

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
