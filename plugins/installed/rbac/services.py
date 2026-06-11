"""RBAC services."""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.rbac')


def has_capability(user, capability: str, *, channel=None) -> bool:
    """True if `user` is granted `capability` (optionally on `channel`).

    - Superusers always pass.
    - Channel-bound role: matches when binding.channel == channel OR binding.channel IS NULL.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    from plugins.installed.rbac.models import RoleBinding

    qs = RoleBinding.objects.filter(user=user).select_related('role')
    if channel is not None:
        from django.db.models import Q

        qs = qs.filter(Q(channel=channel) | Q(channel__isnull=True))
    for binding in qs:  # noqa: SIM110
        if capability in (binding.role.capabilities or []):
            return True
    return False


def capabilities_for(user, *, channel=None) -> set[str]:
    """The full set of capabilities `user` has — useful for menu visibility."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return set()
    if getattr(user, 'is_superuser', False):
        return {'__all__'}
    from plugins.installed.rbac.models import RoleBinding

    qs = RoleBinding.objects.filter(user=user).select_related('role')
    if channel is not None:
        from django.db.models import Q

        qs = qs.filter(Q(channel=channel) | Q(channel__isnull=True))
    out: set[str] = set()
    for binding in qs:
        for cap in binding.role.capabilities or []:
            out.add(cap)
    return out


def grant(user, role_slug: str, *, channel=None, granted_by=None) -> RoleBinding | None:  # noqa: F821
    from core.audit import record
    from plugins.installed.rbac.models import Role, RoleBinding

    role = Role.objects.filter(slug=role_slug).first()
    if not role:
        logger.warning('rbac: unknown role %s', role_slug)
        return None
    binding, created = RoleBinding.objects.get_or_create(
        user=user,
        role=role,
        channel=channel,
        defaults={'granted_by': granted_by},
    )
    if created:
        record(
            event_type='rbac.role_granted',
            actor=granted_by,
            target=f'user/{user.pk}',
            metadata={
                'role': role_slug,
                'channel': getattr(channel, 'slug', None) or str(channel) if channel else None,
            },
        )
    return binding


def revoke(user, role_slug: str, *, channel=None, revoked_by=None) -> int:
    from core.audit import record
    from plugins.installed.rbac.models import RoleBinding

    n, _ = RoleBinding.objects.filter(
        user=user,
        role__slug=role_slug,
        channel=channel,
    ).delete()
    if n:
        record(
            event_type='rbac.role_revoked',
            actor=revoked_by,
            target=f'user/{user.pk}',
            metadata={
                'role': role_slug,
                'channel': getattr(channel, 'slug', None) or str(channel) if channel else None,
                'count': n,
            },
        )
    return n
