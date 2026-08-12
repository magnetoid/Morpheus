"""Release-manifest signing.

The property under test is that **everything ambiguous is rejected**. This is
deliberately the opposite posture to `core/authz.py`, which fails open so a
missing answerer cannot lock a merchant out of their dashboard. Here, running
unverified code is worse than not updating, so every failure mode — bad
signature, wrong key, missing signature, malformed base64, absent library —
must resolve to False rather than raise or pass.
"""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.signing import (
    canonical_bytes,
    generate_keypair,
    sign,
    sign_manifest,
    verify,
    verify_manifest,
)


class KeypairTests(SimpleTestCase):
    def test_round_trip(self):
        private, public = generate_keypair()
        sig = sign(b'hello', private)
        self.assertTrue(verify(b'hello', sig, public))

    def test_a_different_payload_does_not_verify(self):
        private, public = generate_keypair()
        self.assertFalse(verify(b'goodbye', sign(b'hello', private), public))

    def test_a_different_key_does_not_verify(self):
        private, _ = generate_keypair()
        _, other_public = generate_keypair()
        self.assertFalse(verify(b'hello', sign(b'hello', private), other_public))


class VerifyFailsClosedTests(SimpleTestCase):
    def test_every_empty_input_is_false(self):
        _, public = generate_keypair()
        self.assertFalse(verify(b'', 'sig', public))
        self.assertFalse(verify(b'x', '', public))
        self.assertFalse(verify(b'x', 'sig', ''))

    def test_malformed_base64_is_false_not_an_exception(self):
        _, public = generate_keypair()
        self.assertFalse(verify(b'x', '!!!not base64!!!', public))
        self.assertFalse(verify(b'x', 'AAAA', '!!!not base64!!!'))

    def test_a_library_failure_is_false_not_an_exception(self):
        """A caller that forgot a try/except must not end up applying an update."""
        _, public = generate_keypair()
        with mock.patch('core.signing._b64d', side_effect=RuntimeError('boom')):
            self.assertFalse(verify(b'x', 'AAAA', public))


class CanonicalFormTests(SimpleTestCase):
    def test_key_order_does_not_change_the_signed_bytes(self):
        self.assertEqual(canonical_bytes({'b': 1, 'a': 2}), canonical_bytes({'a': 2, 'b': 1}))

    def test_the_signature_field_is_excluded(self):
        """A document cannot contain a signature over itself."""
        self.assertEqual(canonical_bytes({'a': 1}), canonical_bytes({'a': 1, 'signature': 'x'}))


class ManifestTests(SimpleTestCase):
    def setUp(self):
        self.private, self.public = generate_keypair()
        self.manifest = {'channel': 'stable', 'core': {'version': 'v0.43.2'}}

    def test_signed_manifest_verifies(self):
        signed = sign_manifest(self.manifest, self.private)
        self.assertTrue(verify_manifest(signed, self.public))

    def test_tampering_with_any_field_breaks_it(self):
        signed = sign_manifest(self.manifest, self.private)
        signed['core']['artifact'] = 'https://evil.invalid/x.tar.gz'
        self.assertFalse(verify_manifest(signed, self.public))

    def test_an_unsigned_manifest_is_rejected(self):
        self.assertFalse(verify_manifest(self.manifest, self.public))

    def test_a_non_dict_is_rejected(self):
        self.assertFalse(verify_manifest(['not', 'a', 'dict'], self.public))


class SignedManifestSourceTests(SimpleTestCase):
    def setUp(self):
        self.private, self.public = generate_keypair()

    def _source(self, url='https://morpheus.direct/updates/stable.json', key=None):
        from core.update_sources import SignedManifestSource

        return SignedManifestSource(url, self.public if key is None else key)

    def _serve(self, doc):
        """Patch the network read so only verification is under test."""
        import json

        return mock.patch(
            'urllib.request.urlopen',
            return_value=mock.MagicMock(
                __enter__=lambda s: mock.MagicMock(read=lambda: json.dumps(doc).encode()),
                __exit__=lambda *a: False,
            ),
        )

    def test_a_valid_manifest_yields_the_version(self):
        doc = sign_manifest({'core': {'version': 'v9.0.0'}}, self.private)
        with self._serve(doc):
            rel = self._source().latest()
        self.assertIsNotNone(rel)
        self.assertEqual(rel.version, 'v9.0.0')

    def test_a_tampered_manifest_is_ignored_entirely(self):
        doc = sign_manifest({'core': {'version': 'v9.0.0'}}, self.private)
        doc['core']['version'] = 'v99.0.0'
        with self._serve(doc):
            self.assertIsNone(self._source().latest())

    def test_no_public_key_means_no_trust(self):
        doc = sign_manifest({'core': {'version': 'v9.0.0'}}, self.private)
        with self._serve(doc):
            self.assertIsNone(self._source(key='').latest())

    def test_a_non_https_url_is_refused_before_any_request(self):
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('must not fetch')):
            self.assertIsNone(self._source(url='http://insecure.invalid/m.json').latest())


class SourceSelectionTests(SimpleTestCase):
    @override_settings(
        MORPHEUS_UPDATE_MANIFEST_URL='https://morpheus.direct/updates/stable.json',
        MORPHEUS_UPDATE_PUBLIC_KEY='abc',
        MORPHEUS_UPDATE_REPO='magnetoid/morpheus',
    )
    def test_a_signed_manifest_wins_over_the_github_source(self):
        """The GitHub source proves only that we reached a server."""
        from core.update_sources import configured_source

        self.assertEqual(configured_source().name, 'manifest')

    @override_settings(MORPHEUS_UPDATE_MANIFEST_URL='', MORPHEUS_UPDATE_REPO='magnetoid/morpheus')
    def test_falls_back_to_github_when_no_manifest_is_configured(self):
        from core.update_sources import configured_source

        self.assertEqual(configured_source().name, 'github')
