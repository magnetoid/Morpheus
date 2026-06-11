"""RBAC agent tools."""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='rbac.list_roles',
    description='List configured roles + their capabilities.',
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_roles_tool() -> ToolResult:
    from plugins.installed.rbac.models import Role

    rows = list(Role.objects.all().order_by('slug'))
    return ToolResult(
        output={
            'roles': [
                {
                    'slug': r.slug,
                    'name': r.name,
                    'capabilities': r.capabilities,
                    'is_system': r.is_system,
                }
                for r in rows
            ],
        }
    )


@tool(
    name='rbac.grant_role',
    description='Grant a role to a user by email.',
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'role_slug': {'type': 'string'},
            'channel_slug': {'type': 'string', 'description': 'Optional channel scope.'},
        },
        'required': ['email', 'role_slug'],
    },
    requires_approval=True,
)
def grant_role_tool(*, email: str, role_slug: str, channel_slug: str = '') -> ToolResult:
    from django.contrib.auth import get_user_model

    from plugins.installed.rbac.services import grant

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise ToolError(f'No user with email {email}')
    channel = None
    if channel_slug:
        from core.models import StoreChannel

        channel = StoreChannel.objects.filter(slug=channel_slug).first()
    binding = grant(user, role_slug, channel=channel)
    if binding is None:
        raise ToolError(f'Unknown role: {role_slug}')
    return ToolResult(
        output={
            'user': email,
            'role': role_slug,
            'channel': channel_slug if channel_slug else None,
        },
        display=f'Granted {role_slug} to {email}',
    )


@tool(
    name='rbac.revoke_role',
    description='Revoke a role from a user.',
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'role_slug': {'type': 'string'},
            'channel_slug': {'type': 'string'},
        },
        'required': ['email', 'role_slug'],
    },
    requires_approval=True,
)
def revoke_role_tool(*, email: str, role_slug: str, channel_slug: str = '') -> ToolResult:
    from django.contrib.auth import get_user_model

    from plugins.installed.rbac.services import revoke

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise ToolError(f'No user with email {email}')
    channel = None
    if channel_slug:
        from core.models import StoreChannel

        channel = StoreChannel.objects.filter(slug=channel_slug).first()
    n = revoke(user, role_slug, channel=channel)
    return ToolResult(output={'revoked': n}, display=f'Revoked {n} binding(s)')
