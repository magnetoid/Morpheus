from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ErrorEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ('kind', models.CharField(
                    choices=[('server', 'Server'), ('client', 'Client (JS)')],
                    db_index=True, default='server', max_length=10)),
                ('level', models.CharField(
                    choices=[('error', 'Error'), ('warning', 'Warning'), ('info', 'Info')],
                    db_index=True, default='error', max_length=10)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('exception_class', models.CharField(blank=True, max_length=200)),
                ('message', models.TextField(blank=True)),
                ('traceback', models.TextField(blank=True)),
                ('path', models.CharField(blank=True, db_index=True, max_length=500)),
                ('method', models.CharField(blank=True, max_length=10)),
                ('status_code', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('request_id', models.CharField(blank=True, db_index=True, max_length=64)),
                ('user_agent', models.CharField(blank=True, max_length=400)),
                ('ip_hash', models.CharField(blank=True, max_length=64)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['fingerprint', '-created_at'],
                                 name='err_fp_created_idx'),
                    models.Index(fields=['kind', 'level', '-created_at'],
                                 name='err_kind_level_idx'),
                ],
            },
        ),
    ]
