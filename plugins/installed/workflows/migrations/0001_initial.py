"""Initial migration for the workflows plugin."""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Workflow',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('trigger', models.CharField(choices=[('order.placed', 'Order placed'), ('order.paid', 'Order paid'), ('order.fulfilled', 'Order fulfilled'), ('order.cancelled', 'Order cancelled'), ('return.requested', 'Return requested'), ('return.refunded', 'Return refunded'), ('product.low_stock', 'Product low stock'), ('product.out_of_stock', 'Product out of stock'), ('customer.created', 'Customer created'), ('cart.abandoned', 'Cart abandoned'), ('agent.run_failed', 'Agent run failed')], db_index=True, help_text='Event that fires this workflow.', max_length=80)),
                ('condition', models.JSONField(blank=True, default=dict, help_text='Optional condition AST.')),
                ('actions', models.JSONField(blank=True, default=list, help_text='List of {kind, ...kwargs} dicts.')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('run_count', models.PositiveIntegerField(default=0)),
                ('last_ran_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='WorkflowRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('state', models.CharField(choices=[('matched', 'Matched + ran'), ('skipped', 'Skipped (condition false)'), ('failed', 'Failed')], default='matched', max_length=12)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('actions_taken', models.JSONField(blank=True, default=list)),
                ('error', models.TextField(blank=True, default='')),
                ('duration_ms', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='workflows.workflow')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['workflow', '-created_at'], name='workflows_w_workflo_e9c1f5_idx')],
            },
        ),
    ]
