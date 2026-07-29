"""Staff "your account" view — the user-menu dropdown's Settings link
points here so staff have a private, personal page instead of being
dropped into the global store-wide settings hub.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView  # noqa: F401 — re-exported for convenience
from django.shortcuts import render

from morpheus.plugin.views import HttpRequest, HttpResponse, staff_member_required
from plugins.installed.admin_dashboard.views_split._shared import ajax_form_errors, ajax_or_redirect


@staff_member_required
def my_account(request: HttpRequest) -> HttpResponse:
    """Personal account page for the signed-in staff user.

    Shows an editable profile, a password-change form, security options, and
    the user's own recent activity. Deliberately does NOT expose store-level
    settings — those live under /dashboard/settings/.
    """
    user = request.user
    pwd_form = PasswordChangeForm(user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'change_password':
            pwd_form = PasswordChangeForm(user, request.POST)
            if pwd_form.is_valid():
                pwd_form.save()
                update_session_auth_hash(request, pwd_form.user)
                messages.success(request, 'Password updated.')
                return ajax_or_redirect(request, '/dashboard/me/')
            if (error_response := ajax_form_errors(request, pwd_form)) is not None:
                return error_response
        elif action == 'update_profile':
            _apply_profile_update(user, request.POST)
            messages.success(request, 'Profile updated.')
            return ajax_or_redirect(request, '/dashboard/me/')

    return render(
        request,
        'admin_dashboard/account.html',
        {
            'account_user': user,
            'pwd_form': pwd_form,
            'recent_activity': _account_recent_activity(user),
            'active_nav': 'account',
        },
    )


def _apply_profile_update(user, post) -> None:
    """Persist the editable profile fields from the POST onto the user.

    first_name/last_name are on every AUTH_USER_MODEL; phone/company are
    Customer extras — set fail-soft so a swapped user model can't 500 here.
    """
    user.first_name = (post.get('first_name') or '').strip()[:150]
    user.last_name = (post.get('last_name') or '').strip()[:150]
    fields = ['first_name', 'last_name']
    for extra in ('phone', 'company'):
        if hasattr(user, extra):
            setattr(user, extra, (post.get(extra) or '').strip()[:200])
            fields.append(extra)
    user.save(update_fields=fields)


def _account_recent_activity(user, limit: int = 8) -> list:
    """The signed-in user's own recent audit trail (fail-soft).

    Reads core.audit (core, not a plugin) so a personal activity list needs
    no cross-plugin coupling. Empty list if the table is unavailable.
    """
    rows: list = []
    try:
        from core.audit.models import AuditEvent

        for ev in AuditEvent.objects.filter(actor=user).order_by('-created_at')[:limit]:
            rows.append(
                {
                    'event_type': ev.event_type,
                    'label': ev.event_type.replace('.', ' › ').replace('_', ' '),
                    'target': ev.target,
                    'at': ev.created_at,
                    'ip': ev.ip_address,
                    'severity': ev.severity,
                }
            )
    except Exception:  # noqa: BLE001, S110 — audit table may be empty / pre-migration
        pass
    return rows
