"""RBAC dashboard."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.authz import require_capability


@staff_member_required
@require_capability('system.write')
def roles_page(request):
    from plugins.installed.rbac.models import Role, RoleBinding

    roles = list(Role.objects.all().order_by('slug'))
    bindings = list(
        RoleBinding.objects.select_related('user', 'role', 'channel').order_by('-created_at')[:200]
    )
    return render(
        request,
        'rbac/roles.html',
        {
            'roles': roles,
            'bindings': bindings,
            'active_nav': 'settings',
        },
    )
