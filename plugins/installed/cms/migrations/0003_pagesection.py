"""Add PageSection — ordered theme-builder sections under a Page."""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0002_emailtemplate'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageSection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('section_id', models.CharField(db_index=True, help_text='Identifier registered in themes.sections.section_registry.', max_length=80)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('settings', models.JSONField(blank=True, default=dict, help_text='Per-instance settings; merged with the section defaults at render time.')),
                ('is_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='cms.page')),
            ],
            options={
                'ordering': ['sort_order', 'created_at'],
                'indexes': [models.Index(fields=['page', 'sort_order'], name='cms_pagesec_page_id_4be1c2_idx')],
            },
        ),
    ]
