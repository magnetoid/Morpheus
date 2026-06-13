"""Backfill APIKey.key_hash from the legacy plaintext key, then blank the
plaintext — so a DB dump can't leak live tokens. Existing tokens keep working
(auth now looks up by hash). Self-contained hash (sha256 hex) matches
core.models.hash_api_key."""

from __future__ import annotations

import hashlib

from django.db import migrations


def hash_existing_keys(apps, schema_editor):
    APIKey = apps.get_model('core', 'APIKey')
    for k in APIKey.objects.exclude(key='').filter(key_hash=''):
        raw = k.key or ''
        k.key_hash = hashlib.sha256(raw.encode()).hexdigest()
        k.key_prefix = raw[:12]
        k.key = ''
        k.save(update_fields=['key_hash', 'key_prefix', 'key'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_apikey_key_hash_apikey_key_prefix_alter_apikey_key'),
    ]
    operations = [
        migrations.RunPython(hash_existing_keys, migrations.RunPython.noop),
    ]
