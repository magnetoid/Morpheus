"""Linda's self-authored skills (Phase 1 of the self-learning uplift).

`skills.distill` lets Linda turn a workflow she just completed into a reusable
``Skill`` — a named bundle of EXISTING tools + a system-prompt prelude — so a
future Worker opts into it (`skills=["<name>"]`) instead of re-deriving the
approach. The skill is persisted (`LearnedSkill`) and registered in the
``skill_registry`` at runtime + at boot.

Safety: a skill grants NO new privilege. It only references tools already in
Linda's catalog, and each tool still checks its own scopes at call time — so
distilling a skill cannot escalate capability. Unknown tool names are rejected.
"""

# ruff: noqa: PLC0415, S110 — lazy imports + fail-soft catalog reads (mirrors siblings).
from __future__ import annotations

import logging

from core.assistant.tools.filesystem import ToolError, ToolResult, tool

logger = logging.getLogger('morpheus.assistant.skills')


def all_resolvable_tools() -> dict:
    """Every tool resolvable by name = Linda's default catalog ∪ plugin-registered
    tools. Linda's defaults win on a name clash. Fail-soft (empty on any error)."""
    catalog: dict = {}
    try:
        from core.agents.registry import agent_registry

        for t in agent_registry.platform_tools():
            catalog[t.name] = t
    except Exception:  # noqa: BLE001
        pass
    try:
        from core.assistant.tools import get_default_tools

        for t in get_default_tools():
            catalog[t.name] = t
    except Exception:  # noqa: BLE001
        pass
    return catalog


def load_learned_skills() -> int:
    """Register every enabled LearnedSkill into the skill_registry. Called at boot
    (AssistantConfig.ready) and after distill. Fail-soft — returns count loaded,
    0 if the DB isn't ready (fresh install / early boot / tests)."""
    try:
        from core.agents.skills import skill_registry
        from core.assistant.models import LearnedSkill

        n = 0
        for row in LearnedSkill.objects.filter(enabled=True):
            try:
                skill_registry.register(row.to_skill())
                n += 1
            except Exception as e:  # noqa: BLE001
                logger.debug('skip learned skill %s: %s', row.name, e)
        return n
    except Exception as e:  # noqa: BLE001 — DB not ready yet
        logger.debug('load_learned_skills skipped: %s', e)
        return 0


@tool(
    name='skills.distill',
    description=(
        'Save a reusable SKILL from what you just did: a named bundle of EXISTING '
        'tools + a short system-prompt prelude, so a future Worker can opt into it '
        'with skills=["<name>"] instead of re-deriving the approach. Grants no new '
        'privilege — each tool still checks its own scopes. Use after completing a '
        'non-trivial, repeatable workflow. tool_names must be tools you actually used.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'kebab-case unique id, e.g. "restock-low-inventory".',
            },
            'label': {'type': 'string'},
            'description': {'type': 'string', 'default': ''},
            'system_prompt_prelude': {
                'type': 'string',
                'description': 'The reusable know-how: how to perform this skill.',
                'default': '',
            },
            'tool_names': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Names of registered tools this skill bundles.',
            },
            'examples': {'type': 'array', 'items': {'type': 'string'}, 'default': []},
        },
        'required': ['name', 'label', 'tool_names'],
    },
)
def skills_distill_tool(
    *,
    name: str,
    label: str,
    tool_names: list,
    description: str = '',
    system_prompt_prelude: str = '',
    examples: list | None = None,
) -> ToolResult:
    from django.utils.text import slugify

    from core.agents.skills import skill_registry
    from core.assistant.models import LearnedSkill

    slug = slugify(name)[:120]
    if not slug:
        raise ToolError('name must be a non-empty kebab-case identifier')
    if not tool_names:
        raise ToolError('a skill needs at least one tool')
    catalog = all_resolvable_tools()
    unknown = [n for n in tool_names if n not in catalog]
    if unknown:
        raise ToolError(f"unknown tools (not in Linda's catalog): {', '.join(unknown)}")

    obj, created = LearnedSkill.objects.get_or_create(name=slug)
    obj.label = (label or slug)[:160]
    obj.description = description
    obj.system_prompt_prelude = system_prompt_prelude
    obj.tool_names = list(tool_names)
    obj.examples = list(examples or [])
    obj.source = 'distilled'
    obj.enabled = True
    if not created:
        obj.version = (obj.version or 1) + 1
    obj.save()

    # Register immediately so this session can use it.
    skill_registry.register(obj.to_skill())
    return ToolResult(
        output={
            'name': slug,
            'created': created,
            'version': obj.version,
            'tools': list(tool_names),
        },
        display=(
            f'{"Learned" if created else "Updated"} skill "{obj.label}" '
            f'({len(tool_names)} tools) — Workers can now opt in with skills=["{slug}"].'
        ),
    )
