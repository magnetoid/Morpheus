"""Linda's code-proposal approval queue — the human gate of the self-coding
loop (Release 3 of docs/plans/linda-self-learning-2026-07.md, ADR 0014).

Superuser-only. A proposal is drafted by Linda (`code.draft_tool`), reviewed
by the multi-model consensus panel, and sits here until the owner approves or
rejects it. Approving records the binding human decision; the source is only
written to a git branch when `MORPHEUS_SELF_UPDATE_ENABLED` is also set —
never to `main`, never without this page.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.assistant')

_superuser_required = user_passes_test(lambda u: u.is_active and u.is_superuser)


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


@_superuser_required
def proposals_page(request):
    from core.assistant.apply import apply_enabled
    from core.assistant.models import CodeProposal

    return render(
        request,
        'assistant/proposals.html',
        {
            'proposals': CodeProposal.objects.all()[:50],
            'apply_enabled': apply_enabled(),
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
