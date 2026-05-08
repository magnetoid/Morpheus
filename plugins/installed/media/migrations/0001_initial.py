"""Initial migration for the media plugin."""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import plugins.installed.media.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MediaAsset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to=plugins.installed.media.models._upload_path)),
                ('filename', models.CharField(blank=True, help_text='Original filename, preserved for display.', max_length=300)),
                ('mime_type', models.CharField(blank=True, max_length=100)),
                ('kind', models.CharField(choices=[('image', 'Image'), ('video', 'Video'), ('audio', 'Audio'), ('document', 'Document'), ('other', 'Other')], db_index=True, default='other', max_length=20)),
                ('size_bytes', models.PositiveBigIntegerField(default=0)),
                ('alt_text', models.CharField(blank=True, help_text='Used for image accessibility; safe to leave blank for non-images.', max_length=300)),
                ('tags', models.JSONField(blank=True, default=list, help_text='Flat list of strings. Used for filtering the library.')),
                ('width', models.PositiveIntegerField(blank=True, null=True)),
                ('height', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['kind', '-created_at'], name='media_media_kind_b8f31a_idx')],
            },
        ),
    ]
