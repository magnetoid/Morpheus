"""Initial PointsTransaction model."""
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
            name='PointsTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('points', models.IntegerField(help_text='Positive = earn, negative = spend.')),
                ('reason', models.CharField(
                    choices=[('earn_order', 'Earned on order'), ('spend_order', 'Redeemed on order'),
                             ('adjust', 'Manual adjustment'), ('expire', 'Expired')],
                    default='earn_order', max_length=16)),
                ('order_number', models.CharField(blank=True, default='', max_length=40)),
                ('note', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='points_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['customer', '-created_at'], name='loyalty_poi_custome_8d5d12_idx')],
            },
        ),
    ]
