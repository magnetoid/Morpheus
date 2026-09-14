"""Linda's proposal inbox — staged business changes awaiting a human.

**Ops proposals** (staged-changes design §3, docs/superpowers/specs/
2026-07-05-staged-changes-routines-design.md): staged *business* changes (data
edits) from routines and skills. Staff may approve+apply or reject — superuser
NOT required, since apply runs through class-allowlisted data rails, not code.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.assistant')

_staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


@_staff_required
def proposals_page(request):
    from core.assistant.models import OpsProposal

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
            'ops_proposals': ops_qs[:50],  # Meta.ordering: newest first
            'ops_status': ops_status,
            'active_nav': 'assistant',
        },
    )


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
