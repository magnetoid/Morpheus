"""Linda's proposal inbox — the human gate of the assistant's write loops.

Two queues on one page:

- **Code proposals** (ADR 0014): drafted by Linda (`code.draft_tool`),
  consensus-reviewed, owner-only. Approving records the binding human
  decision; source is only written to a git branch when
  `MORPHEUS_SELF_UPDATE_ENABLED` is also set — never to `main`.
- **Ops proposals** (staged-changes design §3, docs/superpowers/specs/
  2026-07-05-staged-changes-routines-design.md): staged *business* changes
  (data edits) from routines/skills. Staff may approve+apply or reject —
  superuser NOT required, since apply runs through class-allowlisted data
  rails, not code.

The page itself is staff-gated; the code-proposal list and its actions stay
superuser-only.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.assistant')

_superuser_required = user_passes_test(lambda u: u.is_active and u.is_superuser)
_staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


def _audit(request, action: str, proposal, extra: dict | None = None) -> None:
    try:
        from core.audit.services import record

        record(
            event_type=f'assistant.proposal_{action}',
            actor=request.user,
            target=f'code_proposal/{proposal.id}',
            metadata={'name': proposal.name, 'status': proposal.status, **(extra or {})},
        )
    except Exception:  # noqa: BLE001 — audit is best-effort on this surface
        logger.debug('proposals: audit skipped', exc_info=True)


@_staff_required
def proposals_page(request):
    from core.assistant.apply import apply_enabled
    from core.assistant.models import CodeProposal, OpsProposal

    ops_status = (request.GET.get('ops_status') or 'proposed').strip().lower()
    if ops_status not in ('proposed', 'all'):
        ops_status = 'proposed'
    ops_qs = OpsProposal.objects.select_related('agent_run', 'approved_by')
    if ops_status == 'proposed':
        ops_qs = ops_qs.filter(status='proposed')

    return render(
        request,
        'assistant/proposals.html',
        {
            # Code proposals stay owner-only (ADR 0014); staff see ops proposals.
            'proposals': CodeProposal.objects.all()[:50] if request.user.is_superuser else [],
            'apply_enabled': apply_enabled(),
            'ops_proposals': ops_qs[:50],  # Meta.ordering: newest first
            'ops_status': ops_status,
            'active_nav': 'assistant',
        },
    )


@_superuser_required
@require_http_methods(['POST'])
def proposal_action(request, pk):
    """One button = one POST: action ∈ review | approve | reject."""
    from core.assistant.models import CodeProposal

    proposal = get_object_or_404(CodeProposal, pk=pk)
    action = (request.POST.get('action') or '').strip()

    if action == 'review':
        from core.assistant.consensus import evaluate

        result = evaluate(proposal)
        proposal.consensus = result
        proposal.save(update_fields=['consensus', 'updated_at'])
        _audit(request, 'reviewed', proposal, {'decision': result.get('decision', '')})
        messages.info(request, f'Consensus panel: {result.get("decision", "?")}.')

    elif action == 'approve':
        from core.assistant.apply import apply_enabled, apply_proposal

        try:
            proposal.approve(request.user)
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))
            return redirect('assistant:proposals')
        _audit(request, 'approved', proposal)
        if apply_enabled():
            result = apply_proposal(proposal)
            if result.get('applied'):
                messages.success(
                    request,
                    f'Approved and written to branch {result.get("branch", "?")} — '
                    'review + merge it yourself.',
                )
            else:
                messages.warning(
                    request,
                    f'Approved, but apply was blocked: {result.get("reasons") or result}.',
                )
        else:
            messages.success(
                request,
                'Approved. The apply gate (MORPHEUS_SELF_UPDATE_ENABLED) is off, so '
                'nothing was written — your decision is recorded.',
            )

    elif action == 'reject':
        proposal.status = 'rejected'
        proposal.save(update_fields=['status', 'updated_at'])
        _audit(request, 'rejected', proposal)
        messages.info(request, f'Rejected "{proposal.name}".')

    else:
        messages.error(request, f'Unknown action: {action!r}')

    return redirect('assistant:proposals')


def _audit_ops(request, action: str, proposal, extra: dict | None = None) -> None:
    try:
        from core.audit.services import record

        record(
            event_type=f'assistant.ops_proposal_{action}',
            actor=request.user,
            target=f'ops_proposal/{proposal.id}',
            metadata={'title': proposal.title, 'status': proposal.status, **(extra or {})},
        )
    except Exception:  # noqa: BLE001 — audit is best-effort on this surface
        logger.debug('ops proposals: audit skipped', exc_info=True)


@_staff_required
@require_http_methods(['POST'])
def ops_proposal_action(request, proposal_id):
    """One button = one POST: action ∈ approve_apply | reject (staff — ops
    proposals apply through class-allowlisted data rails, not code)."""
    from core.assistant.models import OpsProposal

    proposal = get_object_or_404(OpsProposal, pk=proposal_id)
    action = (request.POST.get('action') or '').strip()

    if action == 'approve_apply':
        try:
            approved = proposal.approve(request.user)
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))
            return redirect('assistant:proposals')
        if not approved:
            _audit_ops(request, 'expired', proposal)
            messages.warning(request, f'"{proposal.title}" had expired — nothing was applied.')
            return redirect('assistant:proposals')
        result = proposal.apply(request.user)
        applied = result.get('applied', 0)
        skipped = len(result.get('skipped') or [])
        errors = len(result.get('errors') or [])
        _audit_ops(
            request,
            'approved',
            proposal,
            {'applied': applied, 'skipped': skipped, 'errors': errors},
        )
        summary = f'"{proposal.title}" — {applied} applied, {skipped} skipped, {errors} failed.'
        if applied and not (skipped or errors):
            messages.success(request, summary)
        elif applied:
            messages.warning(request, summary)
        else:
            messages.error(request, summary)

    elif action == 'reject':
        proposal.status = 'rejected'
        proposal.save(update_fields=['status', 'updated_at'])
        _audit_ops(request, 'rejected', proposal)
        messages.info(request, f'Rejected "{proposal.title}".')

    else:
        messages.error(request, f'Unknown action: {action!r}')

    return redirect('assistant:proposals')
