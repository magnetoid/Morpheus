"""Theme sections — composable blocks of presentation that themes ship.

A `Section` is a labelled bundle of:
  * an `id` (stable identifier used in `PageSection.section_id`),
  * a `label` (human-readable name shown in the theme builder),
  * a `template` path the storefront uses to render it,
  * a `schema` describing its editable settings (for the builder UI),
  * an optional `defaults` dict — initial settings when the section is
    added to a page.

Themes register sections at import time via the module-level
`section_registry`. Plugins can also contribute sections — e.g. an
`ai_content` plugin shipping an "AI-curated picks" section.

Usage::

    from themes.sections import Section, section_registry

    @section_registry.register
    class HeroSection(Section):
        id = 'hero'
        label = 'Hero'
        template = 'storefront/sections/_hero.html'
        schema = {
            'fields': [
                {'name': 'eyebrow', 'type': 'string'},
                {'name': 'heading', 'type': 'string', 'required': True},
                {'name': 'cta_label', 'type': 'string'},
                {'name': 'cta_url', 'type': 'url'},
            ],
        }
        defaults = {'eyebrow': '', 'heading': 'Welcome', 'cta_label': '', 'cta_url': '/'}

The storefront then renders any `PageSection` row by looking up its
`section_id` here, merging defaults with the row's `settings`, and
rendering the section's template with that context.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class Section:
    """Subclass and override class attributes (or use as-is)."""

    id: str = ''
    label: str = ''
    description: str = ''
    template: str = ''
    icon: str = 'square'
    schema: dict = field(default_factory=lambda: {'fields': []})
    defaults: dict = field(default_factory=dict)

    def render_context(self, *, page, settings: dict) -> dict:
        """Build the template context for a single render.

        Override when a section needs to fetch related data (e.g. the
        featured-products section calling `Product.objects`). The default
        merges defaults + per-instance settings + a few platform handles.
        """
        merged = dict(self.defaults or {})
        merged.update(settings or {})
        return {
            'section_id': self.id,
            'section_label': self.label,
            'page': page,
            'settings': merged,
        }


class SectionRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, Section] = {}

    def register(self, section_cls: type[Section] | Section):
        """Decorator-friendly registration. Accepts a class or an instance."""
        instance = section_cls() if isinstance(section_cls, type) else section_cls
        if not getattr(instance, 'id', ''):
            raise ValueError(f'Section {section_cls!r} has no id.')
        self._by_id[instance.id] = instance
        return section_cls

    def get(self, section_id: str) -> Section | None:
        return self._by_id.get(section_id)

    def all(self) -> Iterable[Section]:
        return list(self._by_id.values())

    def __contains__(self, section_id: str) -> bool:
        return section_id in self._by_id


section_registry = SectionRegistry()


def render_section(*, page, section_id: str, settings: dict) -> tuple[str, dict] | None:
    """Resolve a section by id and return ``(template, context)`` ready
    for ``render_to_string`` — or ``None`` if the section isn't
    registered (the page might reference a section a removed plugin
    used to ship). Callers fall back to either skipping the row or
    showing a placeholder.
    """
    section = section_registry.get(section_id)
    if section is None:
        return None
    return (section.template, section.render_context(page=page, settings=settings))
