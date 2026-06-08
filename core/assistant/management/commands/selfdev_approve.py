"""Owner approval for a Linda self-dev code proposal (ADR 0014, Phase 4).

The binding human step: only a superuser may approve. Shell access = operator =
owner, but we still require an explicit `--user <username>` so the approval is
attributed and `CodeProposal.approve()` can enforce `is_superuser`.

    python manage.py selfdev_approve --id <uuid> --user <username>
    python manage.py selfdev_approve --id <uuid> --user <username> --apply

`--apply` additionally invokes the gated apply engine (writes the source to a
selfdev/* branch) — still inert unless MORPHEUS_SELF_UPDATE_ENABLED is set.
"""

# Lazy imports keep apply-engine (git/subprocess) cost off the --apply=False path.
# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Owner-approve (and optionally apply) a Linda self-dev code proposal.'

    def add_arguments(self, parser):
        parser.add_argument('--id', required=True, help='CodeProposal UUID.')
        parser.add_argument('--user', required=True, help='Approving superuser username.')
        parser.add_argument('--apply', action='store_true', help='Also run the gated apply engine.')

    def handle(self, *args, **opts):
        from core.assistant.models import CodeProposal

        proposal = CodeProposal.objects.filter(id=opts['id']).first()
        if proposal is None:
            raise CommandError(f'no proposal with id {opts["id"]!r}')

        user = get_user_model().objects.filter(username=opts['user']).first()
        if user is None:
            raise CommandError(f'no user {opts["user"]!r}')

        try:
            proposal.approve(user)
        except PermissionError as e:
            raise CommandError(str(e)) from e
        self.stdout.write(
            self.style.SUCCESS(f'Approved {proposal.name} ({proposal.id}) by {proposal.approver}.')
        )

        if opts['apply']:
            from core.assistant.apply import apply_proposal

            result = apply_proposal(proposal)
            if result.get('applied'):
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Applied to branch {result["branch"]} (commit {result["commit"][:8]}).'
                    )
                )
            else:
                self.stdout.write(self.style.WARNING(f'Apply blocked: {result.get("reason")}'))
