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

from morpheus.views import HttpRequest, HttpResponse, staff_member_required
from plugins.installed.admin_dashboard.views_split._shared import ajax_or_redirect


@staff_member_required
def my_account(request: HttpRequest) -> HttpResponse:
    """Personal account page for the signed-in staff user.

    Shows profile info + a password-change form. Deliberately does NOT
    expose store-level settings — those live under /dashboard/settings/.
    """
    user = request.user
    pwd_form = PasswordChangeForm(user)

    if request.method == 'POST' and request.POST.get('action') == 'change_password':
        pwd_form = PasswordChangeForm(user, request.POST)
        if pwd_form.is_valid():
            pwd_form.save()
            update_session_auth_hash(request, pwd_form.user)
            messages.success(request, 'Password updated.')
            return ajax_or_redirect(request, '/dashboard/me/')

    recent_logins = []
    try:  # noqa: SIM105
        pass  # not the right place but useful
    except Exception:  # noqa: S110
        pass

    return render(
        request,
        'admin_dashboard/account.html',
        {
            'account_user': user,
            'pwd_form': pwd_form,
            'recent_logins': recent_logins,
            'active_nav': 'account',
        },
    )
