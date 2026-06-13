"""API tokens are stored hashed, never plaintext; auth works by hash."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.test import TestCase
from rest_framework import exceptions

from core.authentication import MorpheusAPIKeyAuthentication
from core.models import APIKey, hash_api_key


class APIKeyHashingTests(TestCase):
    def test_created_token_is_hashed_not_plaintext(self):
        k = APIKey.objects.create(name='headless')
        raw = k._raw_key
        self.assertTrue(raw and len(raw) > 20)
        k.refresh_from_db()
        self.assertEqual(k.key, '')  # plaintext never persisted
        self.assertEqual(k.key_hash, hash_api_key(raw))
        self.assertEqual(k.key_prefix, raw[:12])

    def test_auth_with_raw_token_succeeds(self):
        k = APIKey.objects.create(name='t', scopes=['read:products'])
        raw = k._raw_key
        _user, api_key = MorpheusAPIKeyAuthentication().authenticate_credentials(raw)
        self.assertEqual(api_key.id, k.id)

    def test_auth_with_wrong_token_fails(self):
        APIKey.objects.create(name='t')
        with self.assertRaises(exceptions.AuthenticationFailed):
            MorpheusAPIKeyAuthentication().authenticate_credentials('not-a-real-token')

    def test_inactive_key_fails(self):
        k = APIKey.objects.create(name='t', is_active=False)
        with self.assertRaises(exceptions.AuthenticationFailed):
            MorpheusAPIKeyAuthentication().authenticate_credentials(k._raw_key)

    def test_legacy_plaintext_key_migrates_on_save(self):
        # Simulate a pre-migration row: plaintext key, no hash.
        k = APIKey.objects.create(name='legacy')
        APIKey.objects.filter(id=k.id).update(key='LEGACYTOKEN123', key_hash='', key_prefix='')
        legacy = APIKey.objects.get(id=k.id)
        legacy.save()  # same logic the backfill migration runs
        legacy.refresh_from_db()
        self.assertEqual(legacy.key, '')
        self.assertEqual(legacy.key_hash, hash_api_key('LEGACYTOKEN123'))
        # and it authenticates by the original raw value
        _u, api_key = MorpheusAPIKeyAuthentication().authenticate_credentials('LEGACYTOKEN123')
        self.assertEqual(api_key.id, k.id)
