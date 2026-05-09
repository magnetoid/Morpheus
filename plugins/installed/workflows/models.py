"""Workflow + WorkflowRun — the persistence side of the engine."""
from __future__ import annotations

import uuid

from django.db import models


# The set of trigger events the workflow engine subscribes to. Add a new
# entry here + a corresponding handler in engine.py to expose a new
# trigger to merchants. We keep it explicit rather than auto-deriving
# from MorpheusEvents so a workflow can't accidentally fire on a
# half-private internal event.
TRIGGER_CHOICES = [
    ('order.placed', 'Order placed'),
    ('order.paid', 'Order paid'),
    ('order.fulfilled', 'Order fulfilled'),
    ('order.cancelled', 'Order cancelled'),
    ('return.requested', 'Return requested'),
    ('return.refunded', 'Return refunded'),
    ('product.low_stock', 'Product low stock'),
    ('product.out_of_stock', 'Product out of stock'),
    ('customer.created', 'Customer created'),
    ('cart.abandoned', 'Cart abandoned'),
    ('agent.run_failed', 'Agent run failed'),
]

# Action kinds the engine knows how to execute. v1 list — extend in
# `engine.ACTION_HANDLERS`.
ACTION_KINDS = [
    ('notify_staff', 'Notify staff'),
    ('tag_customer', 'Tag customer'),
    ('add_order_note', 'Add note to order'),
    ('webhook_post', 'POST to webhook'),
    ('agent_skill', 'Invoke agent skill'),
]


class Workflow(models.Model):
    """A merchant-defined automation: trigger + condition + actions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    trigger = models.CharField(
        max_length=80, db_index=True, choices=TRIGGER_CHOICES,
        help_text='Event that fires this workflow.',
    )
    condition = models.JSONField(
        default=dict, blank=True,
        help_text=(
            'Optional condition AST. Supported operators: '
            '`{"all": [...]}`, `{"any": [...]}`, `{"not": ...}`, '
            '`{"==": ["path.to.value", "expected"]}`, '
            '`{">": ["path", 100]}`, `{"in": ["needle", "haystack"]}`. '
            'Empty dict = run every time.'
        ),
    )
    actions = models.JSONField(
        default=list, blank=True,
        help_text='List of {kind, ...kwargs} dicts. See engine.ACTION_HANDLERS.',
    )

    is_active = models.BooleanField(default=True, db_index=True)
    run_count = models.PositiveIntegerField(default=0)
    last_ran_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'{self.name} ({self.trigger})'


class WorkflowRun(models.Model):
    """Audit row for a single workflow execution."""
    STATE_CHOICES = [
        ('matched', 'Matched + ran'),
        ('skipped', 'Skipped (condition false)'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name='runs',
    )
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='matched')
    payload = models.JSONField(default=dict, blank=True,
                               help_text='Snapshot of the event payload at fire time.')
    actions_taken = models.JSONField(default=list, blank=True,
                                     help_text='Per-action {kind, ok, message}.')
    error = models.TextField(blank=True, default='')
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['workflow', '-created_at'])]

    def __str__(self) -> str:
        return f'{self.workflow.name} → {self.state} @ {self.created_at:%Y-%m-%d %H:%M}'
