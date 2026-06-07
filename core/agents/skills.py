"""Skills — labeled bundles of agent tools + a system-prompt prelude.

A `Skill` is a reusable, named capability pack — a tools-tuple + a
system-prompt prelude — that the generic `Worker` opts into at spawn time:

    storefront_skill = Skill(
        name='storefront',
        label='Storefront Browsing',
        description='Read-only access to catalog, cart, recommendations.',
        tools=(search_products_tool, get_product_tool, recommend_tool),
        system_prompt_prelude='You can browse the catalog and recommend products.',
    )

Linda passes the skill name through `delegate.spawn_workers`:

    delegate.spawn_workers(jobs=[{
        'objective': 'Help this shopper find a poetry book',
        'skills': ['storefront'],
    }])

When the runtime resolves the Worker's tool list it concatenates each
opted-in Skill's tools, and `get_system_prompt()` prepends each Skill's
`system_prompt_prelude`.

Skills are registered by plugins via `contribute_skills()` and live in
a process-wide `skill_registry`. They're the canonical specialization
mechanism — adding a per-role `MorpheusAgent` subclass is now blocked
by the pre-commit hook (see `.githooks/pre-commit`).
"""

# ruff: noqa: UP035 — typing.Iterable kept for consistency with the package.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from core.agents.tools import Tool


@dataclass(frozen=True)
class Skill:
    name: str
    label: str
    description: str = ''
    tools: tuple[Tool, ...] = field(default_factory=tuple)
    system_prompt_prelude: str = ''

    def __post_init__(self):
        if not self.name:
            raise ValueError('Skill.name is required')
        if not self.label:
            object.__setattr__(self, 'label', self.name.replace('_', ' ').title())
        if isinstance(self.tools, list):
            object.__setattr__(self, 'tools', tuple(self.tools))


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if not isinstance(skill, Skill):
            raise TypeError(f'expected Skill, got {type(skill).__name__}')
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def resolve(self, names: Iterable[str]) -> list[Skill]:
        out: list[Skill] = []
        for name in names or []:
            s = self._skills.get(name)
            if s is not None:
                out.append(s)
        return out


skill_registry = SkillRegistry()
