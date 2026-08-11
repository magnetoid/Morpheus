"""Workflows dashboard — list, edit, view runs, dry-run."""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from morpheus.app.views import staff_member_required
from plugins.installed.workflows.engine import run_workflow
from plugins.installed.workflows.models import (
    ACTION_KINDS,
    TRIGGER_CHOICES,
    Workflow,
    WorkflowRun,
)

logger = logging.getLogger('morpheus.workflows.views')


@staff_member_required
def index(request: HttpRequest) -> HttpResponse:
    workflows = list(Workflow.objects.all())
    return render(
        request,
        'workflows/list.html',
        {
            'workflows': workflows,
            'active_nav': 'workflows',
        },
    )


@staff_member_required
def workflow_form(request: HttpRequest, workflow_id=None) -> HttpResponse:
    wf = get_object_or_404(Workflow, pk=workflow_id) if workflow_id else None

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()[:200]
        description = (request.POST.get('description') or '').strip()[:5000]
        trigger = (request.POST.get('trigger') or '').strip()[:80]
        is_active = request.POST.get('is_active') == 'on'
        condition_raw = (request.POST.get('condition') or '').strip()
        actions_raw = (request.POST.get('actions') or '').strip()

        try:
            condition = json.loads(condition_raw) if condition_raw else {}
        except json.JSONDecodeError as e:
            messages.error(request, f'Condition JSON invalid: {e}')
            return (
                redirect('workflows:edit', workflow_id=workflow_id)
                if wf
                else redirect('workflows:create')
            )

        try:
            actions = json.loads(actions_raw) if actions_raw else []
            if not isinstance(actions, list):
                raise ValueError('actions must be a JSON list')
        except (json.JSONDecodeError, ValueError) as e:
            messages.error(request, f'Actions JSON invalid: {e}')
            return (
                redirect('workflows:edit', workflow_id=workflow_id)
                if wf
                else redirect('workflows:create')
            )

        if not (name and trigger):
            messages.error(request, 'Name and trigger are required.')
        else:
            data = {
                'name': name,
                'description': description,
                'trigger': trigger,
                'condition': condition,
                'actions': actions,
                'is_active': is_active,
            }
            try:
                if wf is None:
                    wf = Workflow.objects.create(**data)
                else:
                    for k, v in data.items():
                        setattr(wf, k, v)
                    wf.save()
                messages.success(request, f'Saved workflow "{wf.name}".')
                return redirect('workflows:index')
            except Exception as e:  # noqa: BLE001
                logger.warning('workflow save failed: %s', e, exc_info=True)
                messages.error(request, f'Save failed: {e}')

    return render(
        request,
        'workflows/edit.html',
        {
            'workflow': wf,
            'triggers': TRIGGER_CHOICES,
            'action_kinds': ACTION_KINDS,
            'condition_str': json.dumps(wf.condition, indent=2) if wf and wf.condition else '',
            'actions_str': json.dumps(wf.actions, indent=2) if wf and wf.actions else '[]',
            'active_nav': 'workflows',
        },
    )


@staff_member_required
def runs(request: HttpRequest, workflow_id) -> HttpResponse:
    wf = get_object_or_404(Workflow, pk=workflow_id)
    rows = list(WorkflowRun.objects.filter(workflow=wf).order_by('-created_at')[:100])
    return render(
        request,
        'workflows/runs.html',
        {
            'workflow': wf,
            'runs': rows,
            'active_nav': 'workflows',
        },
    )


@staff_member_required
def dry_run_view(request: HttpRequest, workflow_id) -> HttpResponse:
    """Dry-run a workflow against a sample payload pasted into the form.

    Useful for verifying conditions before flipping the switch on a
    workflow that fires on every order.
    """
    wf = get_object_or_404(Workflow, pk=workflow_id)
    result = None
    payload_str = ''
    if request.method == 'POST':
        payload_str = (request.POST.get('payload') or '').strip()
        try:
            payload = json.loads(payload_str) if payload_str else {}
            run = run_workflow(wf, payload, dry_run=True)
            result = {
                'state': run.state,
                'actions_taken': run.actions_taken,
                'error': run.error,
                'duration_ms': run.duration_ms,
            }
        except json.JSONDecodeError as e:
            messages.error(request, f'Payload JSON invalid: {e}')
        except Exception as e:  # noqa: BLE001
            messages.error(request, f'Dry-run failed: {e}')
    return render(
        request,
        'workflows/test.html',
        {
            'workflow': wf,
            'payload_str': payload_str
            or '{\n  "order": {"total": 100, "payment_status": "paid"}\n}',
            'result': result,
            'active_nav': 'workflows',
        },
    )


@staff_member_required
def delete(request: HttpRequest, workflow_id) -> HttpResponse:
    wf = get_object_or_404(Workflow, pk=workflow_id)
    if request.method == 'POST':
        name = wf.name
        wf.delete()
        messages.success(request, f'Deleted workflow "{name}".')
    return redirect('workflows:index')
