from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalog', '0008_productimage_webp_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductVideo',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ('title', models.CharField(blank=True, max_length=200)),
                ('url', models.URLField(
                    blank=True,
                    help_text='YouTube, Vimeo, or direct video URL. Auto-converted to an embed.',
                )),
                ('embed_html', models.TextField(
                    blank=True,
                    help_text='Optional raw iframe HTML. Overrides `url` when set.',
                )),
                ('poster_url', models.URLField(
                    blank=True,
                    help_text='Optional poster/thumbnail image URL (used for non-YouTube/Vimeo embeds).',
                )),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='videos',
                    to='catalog.product',
                )),
            ],
            options={
                'ordering': ['sort_order', 'created_at'],
                'indexes': [
                    models.Index(fields=['product', 'is_active', 'sort_order'],
                                 name='pv_product_active_sort_idx'),
                ],
            },
        ),
    ]
