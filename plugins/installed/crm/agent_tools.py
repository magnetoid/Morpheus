"""CRM tools the agent layer can call."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='crm.find_leads',
    description='Search leads by free-text query (matches email, name, company). Returns up to `limit`.',
    scopes=['crm.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {'type': 'string'},
            'status': {
                'type': 'string',
                'enum': ['new', 'contacted', 'qualified', 'converted', 'lost'],
            },
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def find_leads_tool(*, query: str = '', status: str = '', limit: int = 20) -> ToolResult:
    from django.db.models import Q

    from plugins.installed.crm.models import Lead

    qs = Lead.objects.all().order_by('-created_at')
    q = (query or '').strip()
    if q:
        qs = qs.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(company__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    leads = [
        {
            'id': str(lead.id),
            'email': lead.email,
            'name': lead.display_name,
            'company': lead.company,
            'status': lead.status,
            'source': lead.source,
            'score': lead.score,
            'created_at': lead.created_at.isoformat(),
        }
        for lead in qs[: max(1, min(int(limit or 20), 50))]
    ]
    return ToolResult(output={'leads': leads}, display=f'{len(leads)} lead(s)')


@tool(
    name='crm.create_lead',
    description='Create or update a lead by email.',
    scopes=['crm.write'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'company': {'type': 'string'},
            'phone': {'type': 'string'},
            'source': {'type': 'string'},
        },
        'required': ['email'],
    },
)
def create_lead_tool(
    *,
    email: str,
    first_name: str = '',
    last_name: str = '',
    company: str = '',
    phone: str = '',
    source: str = 'agent',
) -> ToolResult:
    from plugins.installed.crm.services import upsert_lead

    lead = upsert_lead(
        email=email,
        first_name=first_name,
        last_name=last_name,
        company=company,
        phone=phone,
        source=source,
    )
    return ToolResult(
        output={'lead_id': str(lead.id), 'email': lead.email, 'status': lead.status},
        display=f'Lead {lead.email} {lead.status}',
    )


@tool(
    name='crm.log_interaction',
    description='Log an interaction (note/call/email/meeting) on a customer or lead by email.',
    scopes=['crm.write'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string', 'description': 'Lead or customer email.'},
            'kind': {'type': 'string', 'enum': ['note', 'call', 'email', 'meeting', 'sms']},
            'summary': {'type': 'string'},
            'body': {'type': 'string'},
            'direction': {'type': 'string', 'enum': ['inbound', 'outbound', 'internal']},
        },
        'required': ['email', 'kind', 'summary'],
    },
)
def log_interaction_tool(
    *,
    email: str,
    kind: str,
    summary: str,
    body: str = '',
    direction: str = 'internal',
) -> ToolResult:
    from django.contrib.auth import get_user_model

    from plugins.installed.crm.models import Lead
    from plugins.installed.crm.services import log_interaction

    User = get_user_model()
    subject = User.objects.filter(email__iexact=email).first()
    if subject is None:
        subject = Lead.objects.filter(email__iexact=email).first()
    if subject is None:
        raise ToolError(f'No customer or lead with email {email}')
    interaction = log_interaction(
        subject=subject,
        kind=kind,
        summary=summary,
        body=body,
        direction=direction,
        actor_name='agent',
    )
    return ToolResult(
        output={'interaction_id': str(interaction.id), 'subject_email': email},
        display=f'Logged {kind} on {email}',
    )


@tool(
    name='crm.list_open_tasks',
    description='List open follow-up tasks. Optionally filter by assignee email.',
    scopes=['crm.read'],
    schema={
        'type': 'object',
        'properties': {
            'assignee_email': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 25},
        },
    },
)
def list_open_tasks_tool(*, assignee_email: str = '', limit: int = 25) -> ToolResult:
    from django.contrib.auth import get_user_model

    from plugins.installed.crm.services import list_open_tasks

    assignee = None
    if assignee_email:
        User = get_user_model()
        assignee = User.objects.filter(email__iexact=assignee_email).first()
    tasks = list_open_tasks(assignee=assignee, limit=int(limit or 25))
    return ToolResult(
        output={
            'tasks': [
                {
                    'id': str(t.id),
                    'title': t.title,
                    'priority': t.priority,
                    'due_at': t.due_at.isoformat(),
                    'assignee': getattr(t.assignee, 'email', '') if t.assignee_id else '',
                    'overdue': t.is_overdue,
                }
                for t in tasks
            ],
        }
    )


@tool(
    name='crm.advance_deal',
    description='Move a deal to a new stage in its pipeline.',
    scopes=['crm.write'],
    schema={
        'type': 'object',
        'properties': {
            'deal_id': {'type': 'string'},
            'stage': {'type': 'string', 'description': "Target stage name in the deal's pipeline."},
            'note': {'type': 'string'},
        },
        'required': ['deal_id', 'stage'],
    },
    requires_approval=True,
)
def advance_deal_tool(*, deal_id: str, stage: str, note: str = '') -> ToolResult:
    from plugins.installed.crm.models import Deal
    from plugins.installed.crm.services import advance_deal

    try:
        deal = Deal.objects.get(id=deal_id)
    except Deal.DoesNotExist as e:
        raise ToolError(f'Unknown deal: {deal_id}') from e
    advance_deal(deal=deal, target_stage=stage, note=note)
    return ToolResult(
        output={'deal_id': str(deal.id), 'stage': deal.stage.name},
        display=f'Deal {deal.name} → {deal.stage.name}',
    )


@tool(
    name='crm.customer_timeline',
    description='Read all CRM interactions logged against a customer (by email).',
    scopes=['crm.read'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 30},
        },
        'required': ['email'],
    },
)
def customer_timeline_tool(*, email: str, limit: int = 30) -> ToolResult:
    from django.contrib.auth import get_user_model

    from plugins.installed.crm.services import customer_timeline

    User = get_user_model()
    customer = User.objects.filter(email__iexact=email).first()
    if customer is None:
        raise ToolError(f'No customer with email {email}')
    rows = customer_timeline(customer, limit=int(limit or 30))
    return ToolResult(
        output={
            'customer': email,
            'interactions': [
                {
                    'kind': r.kind,
                    'summary': r.summary,
                    'direction': r.direction,
                    'occurred_at': r.occurred_at.isoformat(),
                    'actor': getattr(r.actor, 'email', '') if r.actor_id else r.actor_name,
                }
                for r in rows
            ],
        }
    )


@tool(
    name='crm.support_threads',
    description='List customer support-chat threads (default open ones), newest '
    'first, with the unread count so you can triage what needs a reply.',
    scopes=['crm.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string', 'description': 'open | closed | all (default open)'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def crm_support_threads_tool(*, status: str = 'open', limit: int = 20) -> ToolResult:
    from plugins.installed.crm.models import ChatThread

    qs = ChatThread.objects.select_related('customer').all()
    if status in ('open', 'closed'):
        qs = qs.filter(status=status)
    try:
        n = max(1, min(int(limit or 20), 50))
    except (TypeError, ValueError):
        n = 20
    rows = [
        {
            'thread_id': str(t.id),
            'from': t.display_name(),
            'status': t.status,
            'unread': t.unread_staff,
            'last_activity': t.last_message_at.isoformat() if t.last_message_at else None,
        }
        for t in qs[:n]
    ]
    return ToolResult(
        output={'threads': rows, 'count': len(rows)}, display=f'{len(rows)} thread(s).'
    )


@tool(
    name='crm.reply_support',
    description='Reply to a customer in a support-chat thread (sent as staff; the '
    'customer sees it in their chat widget). Optionally close the thread after.',
    scopes=['crm.write'],
    schema={
        'type': 'object',
        'properties': {
            'thread_id': {'type': 'string'},
            'message': {'type': 'string'},
            'close': {'type': 'boolean', 'default': False},
        },
        'required': ['thread_id', 'message'],
    },
)
def crm_reply_support_tool(*, thread_id: str, message: str, close: bool = False) -> ToolResult:
    from plugins.installed.crm.chat import post_staff_reply, thread_by_id

    thread = thread_by_id(thread_id)
    if thread is None:
        return ToolResult(output={'error': f'no support thread {thread_id!r}'})
    body = (message or '').strip()
    if not body:
        return ToolResult(output={'error': 'message is required'})
    post_staff_reply(thread, body, staff_user=None)
    if close:
        thread.status = 'closed'
        thread.save(update_fields=['status'])
    return ToolResult(
        output={'thread_id': str(thread.id), 'replied': True, 'closed': bool(close)},
        display=f'Replied to {thread.display_name()}.',
    )
