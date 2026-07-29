"""CRM dashboard views."""

from __future__ import annotations

from morpheus.plugin.views import render, staff_member_required


@staff_member_required
def crm_home(request):
    from plugins.installed.crm.models import CrmTask, Deal, Interaction, Lead

    open_leads = Lead.objects.exclude(status__in=['converted', 'lost']).count()
    open_tasks = CrmTask.objects.filter(completed_at__isnull=True).count()
    overdue_tasks = sum(
        1 for t in CrmTask.objects.filter(completed_at__isnull=True) if t.is_overdue
    )
    open_deals = Deal.objects.filter(closed_at__isnull=True).count()
    recent = Interaction.objects.all().order_by('-occurred_at')[:15]

    return render(
        request,
        'crm/home.html',
        {
            'metrics': {
                'open_leads': open_leads,
                'open_tasks': open_tasks,
                'overdue_tasks': overdue_tasks,
                'open_deals': open_deals,
            },
            'recent_interactions': recent,
            'active_nav': 'crm',
        },
    )


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
    return render(
        request,
        'crm/pipeline.html',
        {
            'pipeline': pipeline,
            'stages': stages,
            'active_nav': 'crm',
        },
    )


@staff_member_required
def tasks_list(request):
    from plugins.installed.crm.models import CrmTask

    open_tasks = CrmTask.objects.filter(completed_at__isnull=True).order_by('due_at')[:200]
    return render(request, 'crm/tasks.html', {'tasks': open_tasks, 'active_nav': 'crm'})


# ── Inbox (IMAP/SMTP) ─────────────────────────────────────────────────────────


@staff_member_required
def inbox_list(request):
    """Latest messages across every connected mail account."""
    from morpheus.plugin.views import redirect
    from plugins.installed.crm.models import MailAccount, MailMessage

    if request.method == 'POST' and request.POST.get('action') == 'sync':
        from plugins.installed.crm.inbox import fetch_all_active

        try:  # noqa: SIM105
            fetch_all_active()
        except Exception:  # noqa: BLE001, S110
            pass
        return redirect('/dashboard/crm/inbox/')

    accounts = list(MailAccount.objects.all())
    qs = MailMessage.objects.select_related('account', 'customer').order_by(
        '-received_at',
        '-sent_at',
        '-created_at',
    )
    direction = (request.GET.get('dir') or '').lower()
    if direction in ('in', 'out'):
        qs = qs.filter(direction=direction)
    account_id = request.GET.get('account')
    if account_id:
        qs = qs.filter(account_id=account_id)
    search = (request.GET.get('q') or '').strip()
    if search:
        from django.db.models import Q

        qs = qs.filter(
            Q(subject__icontains=search)
            | Q(from_address__icontains=search)
            | Q(to_addresses__icontains=search)
            | Q(body_text__icontains=search)
        )
    messages = list(qs[:200])
    return render(
        request,
        'crm/inbox.html',
        {
            'accounts': accounts,
            'messages': messages,
            'direction': direction,
            'account_id': account_id,
            'search': search,
            'active_nav': 'crm',
        },
    )


@staff_member_required
def inbox_message(request, message_id):
    """Single-message view + reply form."""
    from morpheus.plugin.views import HttpResponseRedirect, get_object_or_404
    from plugins.installed.crm.inbox import send_message
    from plugins.installed.crm.models import MailMessage

    msg = get_object_or_404(
        MailMessage.objects.select_related('account', 'customer'),
        pk=message_id,
    )
    if not msg.is_read and msg.direction == 'in':
        msg.is_read = True
        msg.save(update_fields=['is_read'])

    error = ''
    if request.method == 'POST':
        body = (request.POST.get('body') or '').strip()
        subject = (request.POST.get('subject') or '').strip()
        to = (request.POST.get('to') or msg.from_address or '').strip()
        if not body or not to:
            error = 'Reply needs a recipient and a body.'
        else:
            try:
                send_message(
                    msg.account,
                    to=[a.strip() for a in to.split(',') if a.strip()],
                    subject=subject or f'Re: {msg.subject}',
                    body_text=body,
                    in_reply_to=msg.message_id,
                    customer=msg.customer,
                )
                return HttpResponseRedirect(f'/dashboard/crm/inbox/{msg.pk}/')
            except Exception as e:  # noqa: BLE001
                error = f'Send failed: {e}'

    # Same-thread messages, oldest first.
    thread = []
    if msg.thread_key:
        thread = list(
            MailMessage.objects.filter(thread_key=msg.thread_key)
            .select_related('account', 'customer')
            .order_by('received_at', 'sent_at', 'created_at')
        )
    return render(
        request,
        'crm/inbox_message.html',
        {
            'message': msg,
            'thread': thread,
            'error': error,
            'active_nav': 'crm',
        },
    )


@staff_member_required
def inbox_compose(request):
    """Compose a new outbound email."""
    from morpheus.plugin.views import HttpResponseRedirect
    from plugins.installed.crm.inbox import send_message
    from plugins.installed.crm.models import MailAccount

    accounts = list(MailAccount.objects.filter(is_active=True))
    error = ''
    if request.method == 'POST':
        try:
            account = MailAccount.objects.get(pk=request.POST.get('account'))
        except (MailAccount.DoesNotExist, ValueError, TypeError):
            account = None
        to = (request.POST.get('to') or '').strip()
        subject = (request.POST.get('subject') or '').strip()
        body = (request.POST.get('body') or '').strip()
        if not account or not to or not body:
            error = 'Pick an account and provide a recipient + body.'
        else:
            try:
                sent = send_message(
                    account,
                    to=[a.strip() for a in to.split(',') if a.strip()],
                    subject=subject,
                    body_text=body,
                )
                return HttpResponseRedirect(f'/dashboard/crm/inbox/{sent.pk}/')
            except Exception as e:  # noqa: BLE001
                error = f'Send failed: {e}'
    return render(
        request,
        'crm/inbox_compose.html',
        {
            'accounts': accounts,
            'error': error,
            'active_nav': 'crm',
        },
    )


@staff_member_required
def inbox_accounts(request):
    """List + create/edit MailAccount records."""
    from morpheus.plugin.views import HttpResponseRedirect
    from plugins.installed.crm.models import MailAccount

    error = ''
    if request.method == 'POST':
        action = request.POST.get('action') or 'create'
        if action == 'delete':
            MailAccount.objects.filter(pk=request.POST.get('id')).delete()
            return HttpResponseRedirect('/dashboard/crm/inbox/accounts/')
        if action == 'sync':
            from plugins.installed.crm.inbox import fetch_account

            try:
                acc = MailAccount.objects.get(pk=request.POST.get('id'))
                fetch_account(acc)
            except MailAccount.DoesNotExist:
                pass
            return HttpResponseRedirect('/dashboard/crm/inbox/accounts/')

        data = {
            'label': (request.POST.get('label') or '').strip()[:120],
            'email_address': (request.POST.get('email_address') or '').strip(),
            'provider': (request.POST.get('provider') or 'imap').strip(),
            'imap_host': (request.POST.get('imap_host') or '').strip(),
            'imap_port': int(request.POST.get('imap_port') or 993),
            'imap_use_ssl': request.POST.get('imap_use_ssl') == 'on',
            'imap_username': (request.POST.get('imap_username') or '').strip(),
            'imap_password': request.POST.get('imap_password') or '',
            'imap_folder': (request.POST.get('imap_folder') or 'INBOX').strip(),
            'smtp_host': (request.POST.get('smtp_host') or '').strip(),
            'smtp_port': int(request.POST.get('smtp_port') or 465),
            'smtp_use_ssl': request.POST.get('smtp_use_ssl') == 'on',
            'smtp_use_tls': request.POST.get('smtp_use_tls') == 'on',
            'smtp_username': (request.POST.get('smtp_username') or '').strip(),
            'smtp_password': request.POST.get('smtp_password') or '',
            'is_active': request.POST.get('is_active') == 'on',
        }
        if not (
            data['label'] and data['email_address'] and data['imap_host'] and data['smtp_host']
        ):
            error = 'Label, email, IMAP host, and SMTP host are required.'
        else:
            account_id = (request.POST.get('id') or '').strip()
            if account_id:
                MailAccount.objects.filter(pk=account_id).update(
                    **{
                        # Don't overwrite passwords if blank.
                        k: v
                        for k, v in data.items()
                        if not (k.endswith('_password') and not v)
                    }
                )
            else:
                MailAccount.objects.create(**data)
            return HttpResponseRedirect('/dashboard/crm/inbox/accounts/')

    accounts = list(MailAccount.objects.all().order_by('label'))
    edit_id = (request.GET.get('edit') or '').strip()
    edit_account = None
    if edit_id:
        edit_account = next((a for a in accounts if str(a.pk) == edit_id), None)
    return render(
        request,
        'crm/inbox_accounts.html',
        {
            'accounts': accounts,
            'edit_account': edit_account,
            'error': error,
            'active_nav': 'crm',
        },
    )
