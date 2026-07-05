"""Seed the demo nightly catalog-hygiene routine — staged-changes design §4
(docs/superpowers/specs/2026-07-05-staged-changes-routines-design.md).

The routine is a ``BackgroundAgent`` that runs the generic worker once a day
with ``context_overrides={'staged': True, 'source': 'routine:catalog-hygiene'}``
— so its write tools STAGE OpsProposals for the ops inbox instead of
executing. It is seeded **paused**: the merchant opts in by resuming it from
/dashboard/agents/background/, and ticks are additionally gated by the
default-off AUTONOMY_ENABLED filter (ADR-0028 posture).

No per-routine token budget is set: ``BackgroundAgent`` has no budget field —
the per-run token cap lives on the agent definition
(``Worker.token_budget``, core/agents/base.py).

Idempotent: keyed on the routine name. An existing row is left exactly as
the merchant configured it (state/interval/prompt edits survive re-runs).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

ROUTINE_NAME = 'Catalog hygiene (nightly)'
ROUTINE_PROMPT = (
    'Scan the 20 most recently added active products for missing meta '
    'descriptions, empty short descriptions, or missing alt text; STAGE '
    'fixes via your write tools; do not modify anything directly.'
)


class Command(BaseCommand):
    help = (
        'Create the demo "catalog hygiene" BackgroundAgent (paused, staged '
        'context) — staged-changes design §4. Idempotent.'
    )

    def handle(self, *args, **options):
        from plugins.installed.agent_core.models import BackgroundAgent

        bg, created = BackgroundAgent.objects.get_or_create(
            name=ROUTINE_NAME,
            defaults={
                'agent_name': 'worker',
                'prompt': ROUTINE_PROMPT,
                'context_overrides': {'staged': True, 'source': 'routine:catalog-hygiene'},
                'interval_seconds': 86400,
                'state': BackgroundAgent.STATE_PAUSED,
                'next_run_at': timezone.now(),
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created routine {ROUTINE_NAME!r} (paused — resume it under '
                    '/dashboard/agents/background/ to opt in).'
                )
            )
        else:
            self.stdout.write(f'Routine {ROUTINE_NAME!r} already exists — left untouched.')
