"""Linda-branded settings page. Janus fields are the agent; Linda is identity."""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

_staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)

_ENGINE = ('', 'janus', 'legacy')


class JanusDashboardForm(forms.Form):
    engine = forms.ChoiceField(
        choices=[('', 'Server default'), ('janus', 'Janus'), ('legacy', 'In-process fallback')],
        required=False,
    )
    model = forms.CharField(max_length=120, required=False)
    timeout_s = forms.IntegerField(min_value=5, max_value=55, required=False)
    mcp_url = forms.CharField(max_length=400, required=False)
    mcp_token = forms.CharField(max_length=400, required=False)
    auto_approve = forms.BooleanField(required=False)
    ai_page_help = forms.BooleanField(required=False)
    ai_daily_briefing = forms.BooleanField(required=False)

    def clean_engine(self) -> str:
        value = (self.cleaned_data.get('engine') or '').strip()
        return value if value in _ENGINE else ''

    def apply(self, row, store) -> None:
        data = self.cleaned_data
        row.engine = data['engine']
        row.model = (data.get('model') or '').strip()[:120]
        row.auto_approve = bool(data.get('auto_approve'))
        row.timeout_s = data.get('timeout_s')
        row.mcp_url = (data.get('mcp_url') or '').strip()[:400]
        token = (data.get('mcp_token') or '').strip()
        if token:
            row.mcp_token = token[:400]
        row.save()
        store.ai_page_help = bool(data.get('ai_page_help'))
        store.ai_daily_briefing = bool(data.get('ai_daily_briefing'))
        store.save(update_fields=['ai_page_help', 'ai_daily_briefing', 'updated_at'])


@_staff_required
@require_http_methods(['GET', 'POST'])
def assistant_settings(request):
    from core.assistant.janus_config import status_snapshot
    from core.assistant.models import JanusSettings
    from core.models import StoreSettings

    row = JanusSettings.load()
    store = StoreSettings.objects.first()
    if store is None:
        store = StoreSettings(store_name='Morpheus Store')

    if request.method == 'POST':
        form = JanusDashboardForm(request.POST)
        if form.is_valid():
            if store.pk is None:
                store.save()
            form.apply(row, store)
            messages.success(request, 'Janus settings saved.')
            return redirect('assistant:settings')
        messages.error(request, 'Could not save Janus settings.')
    else:
        form = JanusDashboardForm(
            initial={
                'engine': row.engine,
                'model': row.model,
                'timeout_s': row.timeout_s,
                'mcp_url': row.mcp_url,
                'auto_approve': row.auto_approve,
                'ai_page_help': bool(getattr(store, 'ai_page_help', False)),
                'ai_daily_briefing': bool(getattr(store, 'ai_daily_briefing', False)),
            }
        )

    return render(
        request,
        'assistant/settings.html',
        {
            'active_nav': 'assistant',
            'row': row,
            'store': store,
            'form': form,
            'status': status_snapshot(),
            'has_mcp_token': bool(row.mcp_token),
        },
    )
