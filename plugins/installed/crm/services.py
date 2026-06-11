"""CRM services — the operations the rest of the platform calls."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.crm')


def upsert_lead(
    *,
    email: str,
    first_name: str = '',
    last_name: str = '',
    phone: str = '',
    company: str = '',
    source: str = 'other',
    metadata: dict[str, Any] | None = None,
) -> Lead:  # noqa: F821
    """Idempotent lead create-or-update by email."""
    from plugins.installed.crm.models import Lead

    email = (email or '').strip().lower()
    if not email:
        raise ValueError('upsert_lead: email required')
    defaults = {
        'first_name': first_name[:100],
        'last_name': last_name[:100],
        'phone': phone[:40],
        'company': company[:200],
        'source': source,
        'metadata': metadata or {},
    }
    lead, _created = Lead.objects.update_or_create(email=email, defaults=defaults)
    return lead


def convert_lead(*, lead, customer) -> None:
    """Mark a lead as converted to a customer."""
    if lead.converted_customer_id:
        return
    lead.converted_customer = customer
    lead.status = 'converted'
    lead.converted_at = timezone.now()
    lead.save(update_fields=['converted_customer', 'status', 'converted_at', 'updated_at'])


def log_interaction(
    *,
    subject,
    kind: str,
    summary: str = '',
    body: str = '',
    direction: str = 'internal',
    actor=None,
    actor_name: str = '',
    occurred_at=None,
    metadata: dict[str, Any] | None = None,
) -> Interaction:  # noqa: F821
    """Append an interaction to a subject's timeline."""
    from plugins.installed.crm.models import Interaction

    ct = ContentType.objects.get_for_model(subject.__class__)
    return Interaction.objects.create(
        subject_type=ct,
        subject_id=str(subject.pk),
        kind=kind,
        direction=direction,
        summary=summary[:240],
        body=body,
        actor=actor,
        actor_name=actor_name[:120],
        occurred_at=occurred_at or timezone.now(),
        metadata=metadata or {},
    )


def list_open_tasks(*, assignee=None, limit: int = 25) -> list[CrmTask]:  # noqa: F821
    from plugins.installed.crm.models import CrmTask

    qs = CrmTask.objects.filter(completed_at__isnull=True).order_by('due_at')
    if assignee is not None:
        qs = qs.filter(assignee=assignee)
    return list(qs[:limit])


def create_followup_task(
    *,
    subject,
    title: str,
    due_in_hours: int = 24,
    priority: str = 'normal',
    assignee=None,
    description: str = '',
) -> CrmTask:  # noqa: F821
    from plugins.installed.crm.models import CrmTask

    ct = ContentType.objects.get_for_model(subject.__class__)
    return CrmTask.objects.create(
        title=title[:200],
        description=description,
        priority=priority,
        due_at=timezone.now() + timedelta(hours=max(1, int(due_in_hours))),
        subject_type=ct,
        subject_id=str(subject.pk),
        assignee=assignee,
    )


def advance_deal(*, deal, target_stage: str, actor=None, note: str = '') -> Deal:  # noqa: F821
    """Move a deal to the named stage in the same pipeline. Logs an interaction."""
    from plugins.installed.crm.models import PipelineStage

    try:
        stage = PipelineStage.objects.get(pipeline=deal.pipeline, name=target_stage)
    except PipelineStage.DoesNotExist as e:
        raise ValueError(f'Unknown stage in pipeline {deal.pipeline.name}: {target_stage}') from e

    if deal.stage_id == stage.id:
        return deal

    previous = deal.stage.name
    with transaction.atomic():
        deal.stage = stage
        if stage.is_won or stage.is_lost:
            deal.closed_at = timezone.now()
        deal.save(update_fields=['stage', 'closed_at', 'updated_at'])
        log_interaction(
            subject=deal,
            kind='system',
            summary=f'Stage: {previous} → {stage.name}',
            body=note,
            actor=actor,
            actor_name='' if actor else 'system',
        )
    return deal


def ensure_default_pipeline() -> Pipeline:  # noqa: F821
    """Create + return the default pipeline (idempotent)."""
    from plugins.installed.crm.models import Pipeline, PipelineStage

    try:
        with transaction.atomic():
            pipeline, created = Pipeline.objects.get_or_create(
                name='Default',
                defaults={'is_default': True, 'description': 'Default sales pipeline.'},
            )
            if created:
                stages = [
                    ('Qualified', 0, 0.20, False, False),
                    ('Demo', 1, 0.40, False, False),
                    ('Proposal', 2, 0.60, False, False),
                    ('Negotiation', 3, 0.80, False, False),
                    ('Won', 4, 1.00, True, False),
                    ('Lost', 5, 0.00, False, True),
                ]
                for name, order, prob, is_won, is_lost in stages:
                    PipelineStage.objects.create(
                        pipeline=pipeline,
                        name=name,
                        order=order,
                        win_probability=prob,
                        is_won=is_won,
                        is_lost=is_lost,
                    )
    except DatabaseError as e:
        logger.warning('crm: ensure_default_pipeline failed: %s', e)
        raise
    return pipeline


def customer_timeline(customer, *, limit: int = 50) -> list[Interaction]:  # noqa: F821
    """All interactions where the subject is this customer."""
    from plugins.installed.crm.models import Interaction

    ct = ContentType.objects.get_for_model(customer.__class__)
    return list(
        Interaction.objects.filter(subject_type=ct, subject_id=str(customer.pk)).order_by(
            '-occurred_at'
        )[:limit]
    )
