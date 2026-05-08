"""Initial migration for the metafields plugin."""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Metafield',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('object_id', models.CharField(db_index=True, help_text='Stringified primary key — works for ints + UUIDs.', max_length=64)),
                ('namespace', models.CharField(blank=True, default='', help_text='Convention: `<plugin>.<feature>` for plugin-owned, blank for merchant-defined.', max_length=80)),
                ('key', models.CharField(help_text='Snake-case identifier within the namespace.', max_length=120)),
                ('value', models.TextField(blank=True, default='')),
                ('value_type', models.CharField(choices=[('string', 'String'), ('text', 'Long text'), ('integer', 'Integer'), ('number', 'Number'), ('boolean', 'Boolean'), ('json', 'JSON'), ('date', 'Date'), ('datetime', 'Date + time'), ('url', 'URL'), ('email', 'Email'), ('color', 'Colour'), ('file_id', 'Media asset id')], default='string', max_length=20)),
                ('description', models.CharField(blank=True, default='', help_text='Optional — shown in the dashboard editor.', max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'ordering': ['namespace', 'key'],
                'indexes': [
                    models.Index(fields=['content_type', 'object_id'], name='metafields__content_b3f0a2_idx'),
                    models.Index(fields=['namespace', 'key'], name='metafields__namespa_4c19e7_idx'),
                ],
                'unique_together': {('content_type', 'object_id', 'namespace', 'key')},
            },
        ),
    ]
