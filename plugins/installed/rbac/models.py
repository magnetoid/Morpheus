"""RBAC — role definitions + role bindings.

Wraps Django's auth Group with merchant-friendly Role + RoleBinding models.

A `Role` is a named bundle of capability strings (`catalog.write`,
`orders.refund`, `analytics.read`). A `RoleBinding` maps a User to one
or more Roles (optionally scoped to a single channel).

The `has_capability(user, cap)` helper is the runtime check.
Capability strings are the same shape that agent tools use, so the
RBAC layer is consistent with the agent kernel.
"""

from __future__ import annotations

import uuid

from django.conf import settings

from morpheus.plugin import models

_DEFAULT_TEMPLATES = {
    'admin': [
        'catalog.read',
        'catalog.write',
        'orders.read',
        'orders.write',
        'orders.refund',
        'inventory.read',
        'inventory.write',
        'analytics.read',
        'cms.read',
        'cms.write',
        'crm.read',
        'crm.write',
        'seo.read',
        'seo.write',
        'tax.read',
        'tax.write',
        'shipping.read',
        'shipping.write',
        'payments.read',
        'payments.write',
        'b2b.read',
        'b2b.write',
        'gift_cards.read',
        'gift_cards.write',
        'affiliates.read',
        'affiliates.write',
        'system.read',
        'system.write',
    ],
    'marketing_manager': [
        'catalog.read',
        'analytics.read',
        'cms.read',
        'cms.write',
        'crm.read',
        'crm.write',
        'seo.read',
        'seo.write',
    ],
    'inventory_manager': [
        'catalog.read',
        'inventory.read',
        'inventory.write',
    ],
    'support_agent': [
        'orders.read',
        'orders.write',
        'orders.refund',
        'crm.read',
        'crm.write',
    ],
    'analyst': [
        'catalog.read',
        'orders.read',
        'analytics.read',
        'crm.read',
    ],
    'content_editor': [
        'cms.read',
        'cms.write',
        'seo.read',
        'seo.write',
        'content.read',
        'content.write',
    ],
}


class Role(models.Model):
    """Named bundle of capability strings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    capabilities = models.JSONField(
        default=list, help_text='List of capability strings, e.g. ["catalog.read"]'
    )
    is_system = models.BooleanField(
        default=False, help_text='Bootstrapped role; protected from delete.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    @classmethod
    def ensure_system_roles(cls):
        """Create the standard role templates if missing."""
        for slug, caps in _DEFAULT_TEMPLATES.items():
            cls.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': slug.replace('_', ' ').title(),
                    'capabilities': caps,
                    'is_system': True,
                },
            )


class RoleBinding(models.Model):
    """Assign a User to a Role, optionally scoped to a channel."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_bindings',
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='bindings')
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Optional channel scope; null = applies on every channel.',
    )
    note = models.CharField(max_length=200, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_bindings',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role', 'channel')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'role'])]
