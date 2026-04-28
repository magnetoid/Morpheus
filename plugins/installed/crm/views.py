"""CRM dashboard views."""
from __future__ import annotations

from morpheus.views import staff_member_required
from morpheus.views import render


@staff_member_required
def crm_home(request):
    from plugins.installed.crm.models import CrmTask, Deal, Interaction, Lead

    open_leads = Lead.objects.exclude(status__in=['converted', 'lost']).count()
    open_tasks = CrmTask.objects.filter(completed_at__isnull=True).count()
    overdue_tasks = sum(1 for t in CrmTask.objects.filter(completed_at__isnull=True) if t.is_overdue)
    open_deals = Deal.objects.filter(closed_at__isnull=True).count()
    recent = Interaction.objects.all().order_by('-occurred_at')[:15]

    return render(request, 'crm/home.html', {
        'metrics': {
            'open_leads': open_leads,
            'open_tasks': open_tasks,
            'overdue_tasks': overdue_tasks,
            'open_deals': open_deals,
        },
        'recent_interactions': recent,
        'active_nav': 'crm',
    })


@staff_member_required
def leads_list(request):
    from plugins.installed.crm.models import Lead

    leads = Lead.objects.all().order_by('-created_at')[:200]
    return render(request, 'crm/leads.html', {'leads': leads, 'active_nav': 'crm'})


@staff_member_required
def pipeline_board(request):
    from plugins.installed.crm.models import Deal, Pipeline

    pipeline = Pipeline.objects.filter(is_default=True).first() or Pipeline.objects.first()
    stages = []
    if pipeline:
        for stage in pipeline.stages.all().order_by('order'):
            deals = list(
                Deal.objects.filter(pipeline=pipeline, stage=stage, closed_at__isnull=True)
                .select_related('account', 'owner')
                .order_by('-created_at')[:50]
            )
            stages.append({'stage': stage, 'deals': deals})
    return render(request, 'crm/pipeline.html', {
        'pipeline': pipeline, 'stages': stages, 'active_nav': 'crm',
    })


@staff_member_required
def tasks_list(request):
    from plugins.installed.crm.models import CrmTask

    open_tasks = CrmTask.objects.filter(completed_at__isnull=True).order_by('due_at')[:200]
    return render(request, 'crm/tasks.html', {'tasks': open_tasks, 'active_nav': 'crm'})
