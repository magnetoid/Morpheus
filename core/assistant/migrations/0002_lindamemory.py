"""LindaMemory — cross-session preference store."""
from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assistant', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LindaMemory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scope', models.CharField(
                    choices=[('merchant', 'Merchant preference'),
                             ('customer-segment', 'Customer segment'),
                             ('seasonal', 'Seasonal / time-bound')],
                    db_index=True, default='merchant', max_length=24)),
                ('key', models.CharField(db_index=True, max_length=160)),
                ('value', models.TextField()),
                ('source', models.CharField(
                    blank=True, default='', max_length=40,
                    help_text="Free-text source tag — 'user-told' / 'inferred' / etc.")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={
                'ordering': ['-updated_at'],
                'unique_together': {('scope', 'key')},
                'indexes': [models.Index(fields=['scope', '-updated_at'], name='assistant_l_scope_4dfaf8_idx')],
            },
        ),
    ]
