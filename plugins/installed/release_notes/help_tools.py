"""Linda's help tools: the same help staff read on /dashboard/help/.

Read-only and scope-less, like platform.capabilities: every staff member's Linda
reads help in every mode, whatever their role. A storefront agent never gets a
scope-less tool (core/agents/base.py), and the storefront, cart and checkout
agent doors list their tools explicitly, so a shopper's agent never sees these.
They leave with this app.
"""

from __future__ import annotations

import difflib

from core.agents.tools import ToolResult
from morpheus.core import tool
from plugins import app_help
from plugins.installed.release_notes import help_facts, help_render


@tool(
    name='help.apps',
    description=(
        'List every app this store has, with one sentence on what each does, the '
        'dashboard area it lives in and whether it is switched on. Use it to find '
        "the app a merchant's question is about, then read its help with help.read."
    ),
    scopes=[],
)
def help_apps_tool() -> ToolResult:
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    apps = [
        {
            'name': inst.name,
            'label': inst.label or inst.name,
            'summary': app_help.summary(inst.name) or inst.description,
            'area': navigation.describe_app(inst)['area_label'],
            'on': app_registry.is_active(inst.name),
        }
        for inst in sorted(app_registry.all_plugins(), key=lambda p: p.name)
    ]
    return ToolResult(output={'apps': apps, 'count': len(apps)}, display=f'{len(apps)} apps.')


def _closest(name: str) -> list[str]:
    from plugins.registry import app_registry

    choices: dict[str, str] = {}
    for inst in app_registry.all_plugins():
        choices[inst.name] = inst.name
        choices[(inst.label or '').casefold()] = inst.name
    hits = difflib.get_close_matches(name.casefold(), list(choices), n=5, cutoff=0.5)
    return sorted({choices[h] for h in hits})


@tool(
    name='help.read',
    description=(
        "Read one app's help: what it is for, how to set it up, common tasks, where "
        'its screens and settings are (with their paths) and what you can do there. '
        'Read it before answering how to do something in the dashboard.'
    ),
    scopes=[],
    schema={
        'type': 'object',
        'properties': {
            'app': {'type': 'string', 'description': 'The app name from help.apps, e.g. "reviews".'}
        },
        'required': ['app'],
    },
)
def help_read_tool(*, app: str) -> ToolResult:
    name = (app or '').strip()
    found = help_facts.facts(name)
    if found is None:
        return ToolResult(
            output={'error': f'no app named {name!r}', 'closest': _closest(name)},
            display=f'No app named {name!r}.',
        )
    guide = app_help.guide(name)
    parts = [f'# {found["label"]} ({"on" if found["active"] else "off"})']
    summary = guide.summary if guide else found['description']
    if summary:
        parts.append(summary)
    if guide:
        parts.append(help_render.plain(guide.body, app=name))
    where = [f'- {p.label} ({p.url})' if p.url else f'- {p.label}' for p in found['places']]
    where += [f'- {c}' for c in found['cards']]
    where += [f'- In the shop: {s}' for s in found['shop']]
    if where:
        parts.append('Where to find it:\n' + '\n'.join(where))
    if found['tools']:
        parts.append(
            'What you can do here:\n'
            + '\n'.join(
                f'- {t["name"]}{" (asks first)" if t["asks_first"] else ""}: {t["description"]}'
                for t in found['tools']
            )
        )
    return ToolResult(
        output={
            'app': name,
            'label': found['label'],
            'on': found['active'],
            'text': '\n\n'.join(parts),
        },
        display=f'Help for {found["label"]}.',
    )
