"""Initial migration for the notifications center plugin."""
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
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(db_index=True, max_length=80)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField(blank=True)),
                ('action_url', models.CharField(blank=True, max_length=500)),
                ('icon', models.CharField(blank=True, default='bell', help_text='Lucide icon name; falls back to "bell".', max_length=40)),
                ('read_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', '-created_at'], name='notif_cente_user_id_d18e3c_idx'),
                    models.Index(fields=['user', 'read_at'], name='notif_cente_user_id_2b04d6_idx'),
                ],
            },
        ),
    ]
