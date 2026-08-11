"""
Morph Functions — merchant-defined sandboxed code.

Each Function is a small Python snippet that runs in an isolated namespace at
specific extension points (cart total, product price, order validation, etc).
A Function is identified by `(channel, target, name)` and ships with a list
of granted capabilities — the runtime refuses to expose anything else.
"""

from __future__ import annotations

import uuid

from morpheus.app import models


class Function(models.Model):
    """A merchant-defined function that runs at a specific extension point."""

    TARGET_CHOICES = [
        ('cart.calculate_breakdown', 'Cart Breakdown'),
        ('cart.calculate_total', 'Cart Total (deprecated)'),
        ('product.calculate_price', 'Product Price'),
        ('order.validate', 'Order Validation'),
        ('shipping.rate', 'Shipping Rate'),
        ('discount.apply', 'Discount Application'),
        ('custom', 'Custom'),
    ]
    LANGUAGE_CHOICES = [
        ('python_safe', 'Sandboxed Python'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='functions',
        help_text='Channel this function applies to. Null = applies to all channels.',
    )
    target = models.CharField(max_length=50, choices=TARGET_CHOICES, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='python_safe')
    source = models.TextField(help_text='Function body. Must define `run(input)`.')
    capabilities = models.JSONField(
        default=list,
        help_text='Capability strings the runtime exposes to this function.',
    )
    timeout_ms = models.PositiveIntegerField(
        default=200,
        help_text='Soft execution time limit. Hard kill at 4x this value.',
    )
    is_enabled = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveSmallIntegerField(
        default=50,
        help_text='Lower runs first when multiple functions target the same hook.',
    )
    last_error = models.TextField(blank=True)
    last_run_ms = models.PositiveIntegerField(null=True, blank=True)
    invocation_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target', 'priority', 'name']
        unique_together = ('channel', 'target', 'name')
        indexes = [
            models.Index(fields=['target', 'is_enabled']),
            models.Index(fields=['channel', 'target', 'is_enabled']),
        ]

    def __str__(self) -> str:
        return f'Function({self.target}/{self.name})'


class FunctionInvocation(models.Model):
    """Audit record for every Function execution."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    function = models.ForeignKey(
        Function,
        on_delete=models.CASCADE,
        related_name='invocations',
    )
    duration_ms = models.PositiveIntegerField()
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    input_summary = models.JSONField(default=dict)
    output_summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['function', '-created_at']),
        ]
