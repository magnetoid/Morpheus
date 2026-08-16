"""The per-app / per-theme update channel.

Two properties carry the whole design and every test here is about one of
them: nothing is *believed* unless the publisher signed it (manifest entry →
sha256 → artifact bytes → inspected archive), and nothing is *left broken* —
a refused artifact leaves no file behind, a failed apply restores the tree it
replaced.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core.component_updates import (
    ArtifactError,
    _protected,
    _ships_with_core,
    apply_component_update,
    extract_component,
    fetch_artifact,
    inspect_archive,
)
from core.signing import generate_keypair, sign_manifest, verify_manifest
from core.update_sources import (
    ComponentRelease,
    GitHubReleaseSource,
    SignedManifestSource,
    UpdateSource,
    check_for_update,
    component_updates,
)

# ── helpers ────────────────────────────────────────────────────────────────────


class _Resp(io.BytesIO):
    """A urlopen() response: bytes + context-manager protocol."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _tar_bytes(members: dict[str, bytes | None], *, links: dict[str, str] | None = None) -> bytes:
    """Build a .tar.gz in memory. `None` content = directory. `links` adds
    symlinks name→target."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            if content is None:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tf.addfile(info)
            else:
                info.size = len(content)
                info.mode = 0o644
                tf.addfile(info, io.BytesIO(content))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tf.addfile(info)
    return buf.getvalue()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_tar(tmp: Path, data: bytes, name: str = 'a.tar.gz') -> Path:
    p = tmp / name
    p.write_bytes(data)
    return p


GOOD_APP = {
    'my_app-1.4.0/': None,
    'my_app-1.4.0/app.py': b'# manifest\n',
    'my_app-1.4.0/migrations/': None,
    'my_app-1.4.0/migrations/__init__.py': b'',
    'my_app-1.4.0/migrations/0001_initial.py': b'# m\n',
}
GOOD_THEME = {
    'my_theme/': None,
    'my_theme/theme.py': b'# theme\n',
    'my_theme/templates/x.html': b'<b>new</b>',
}


class _FakeSource(UpdateSource):
    name = 'fake'

    def __init__(self, releases):
        self._releases = list(releases)

    def latest(self):
        return None

    def components(self):
        return self._releases


# ── manifest → components ──────────────────────────────────────────────────────


class ManifestComponentsTests(SimpleTestCase):
    def setUp(self):
        self.private, self.public = generate_keypair()
        self.doc = sign_manifest(
            {
                'channel': 'stable',
                'core': {'version': 'v0.44.0'},
                'apps': {
                    'my_app': {
                        'version': '1.4.0',
                        'artifact': 'https://x/my_app-1.4.0.tar.gz',
                        'sha256': 'AB' * 32,
                        'min_core': 'v0.44.0',
                    }
                },
                'themes': {'my_theme': {'version': '2.0.0', 'artifact': 'https://x/t.tgz'}},
            },
            self.private,
        )

    def _source(self, doc=None):
        payload = json.dumps(doc if doc is not None else self.doc).encode()
        src = SignedManifestSource('https://updates.example/stable.json', self.public)
        patcher = mock.patch(
            'core.update_sources.urllib.request.urlopen', return_value=_Resp(payload)
        )
        return src, patcher

    def test_verified_manifest_yields_app_and_theme_entries(self):
        src, p = self._source()
        with p:
            comps = {(c.kind, c.name): c for c in src.components()}
        self.assertEqual(set(comps), {('app', 'my_app'), ('theme', 'my_theme')})
        app = comps[('app', 'my_app')]
        self.assertEqual(app.version, '1.4.0')
        self.assertEqual(app.sha256, 'ab' * 32, 'checksums are normalised to lowercase')
        self.assertEqual(app.min_core, 'v0.44.0')

    def test_tampered_manifest_yields_nothing_at_all(self):
        """Editing one entry after signing must invalidate the whole channel —
        not just that entry — because the signature is over the document."""
        tampered = json.loads(json.dumps(self.doc))
        tampered['apps']['my_app']['sha256'] = 'cd' * 32
        src, p = self._source(tampered)
        with p:
            self.assertEqual(src.components(), [])
            self.assertIsNone(src.latest())

    def test_one_fetch_serves_latest_and_components(self):
        src, p = self._source()
        with p as urlopen:
            src.latest()
            src.components()
            src.components()
        self.assertEqual(urlopen.call_count, 1)

    def test_github_source_publishes_no_components(self):
        """Transport-authenticated only — it may not vouch for arbitrary code."""
        self.assertEqual(GitHubReleaseSource('a/b').components(), [])


class ComponentUpdatesTests(SimpleTestCase):
    RELEASES = [
        ComponentRelease('app', 'my_app', '1.4.0', min_core='v0.44.0', sha256='ab' * 32),
        ComponentRelease('app', 'other_app', '9.9.9'),
        ComponentRelease('theme', 'my_theme', '2.0.0', min_core='v0.50.0'),
        ComponentRelease('theme', 'same_theme', '1.0.0'),
    ]
    INSTALLED = {
        ('app', 'my_app'): '1.3.2',
        ('theme', 'my_theme'): '1.9.0',
        ('theme', 'same_theme'): '1.0.0',
        ('app', 'downgrade'): '3.0.0',
    }

    def test_lists_only_installed_and_newer(self):
        out = component_updates(_FakeSource(self.RELEASES), self.INSTALLED, core_version='v0.44.0')
        by = {(c['kind'], c['name']): c for c in out}
        self.assertEqual(set(by), {('app', 'my_app'), ('theme', 'my_theme')})
        self.assertEqual(by[('app', 'my_app')]['current'], '1.3.2')
        self.assertEqual(by[('app', 'my_app')]['latest'], '1.4.0')

    def test_core_ok_reflects_min_core(self):
        out = component_updates(_FakeSource(self.RELEASES), self.INSTALLED, core_version='v0.44.0')
        by = {c['name']: c for c in out}
        self.assertTrue(by['my_app']['core_ok'])
        self.assertFalse(by['my_theme']['core_ok'], 'needs v0.50.0, running v0.44.0')

    def test_no_source_is_empty(self):
        with override_settings(MORPHEUS_UPDATE_MANIFEST_URL='', MORPHEUS_UPDATE_REPO=''):
            self.assertEqual(component_updates(), [])

    def test_check_for_update_carries_components(self):
        private, public = generate_keypair()
        doc = sign_manifest(
            {
                'core': {'version': 'v0.44.0'},
                'apps': {'my_app': {'version': '1.4.0'}},
                'themes': {},
            },
            private,
        )
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL='https://u.example/s.json',
                MORPHEUS_UPDATE_PUBLIC_KEY=public,
            ),
            mock.patch(
                'core.update_sources.urllib.request.urlopen',
                return_value=_Resp(json.dumps(doc).encode()),
            ),
            mock.patch(
                'core.update_sources.installed_components',
                return_value={('app', 'my_app'): '1.0.0'},
            ),
        ):
            status = check_for_update('v0.43.3')
        self.assertEqual(status['available'], 'yes')
        self.assertEqual([c['name'] for c in status['components']], ['my_app'])


# ── fetch + verify ─────────────────────────────────────────────────────────────


class FetchArtifactTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = _tar_bytes(GOOD_THEME)

    def _urlopen(self, data=None):
        return mock.patch(
            'core.component_updates.urllib.request.urlopen',
            return_value=_Resp(self.data if data is None else data),
        )

    def _leftovers(self):
        return sorted(p.name for p in self.tmp.iterdir())

    def test_matching_checksum_lands_the_bytes(self):
        with self._urlopen():
            path = fetch_artifact('https://x/a.tgz', _sha(self.data), self.tmp)
        self.assertEqual(path.read_bytes(), self.data)

    def test_mismatched_checksum_is_refused_and_leaves_nothing(self):
        with self._urlopen(), self.assertRaises(ArtifactError):
            fetch_artifact('https://x/a.tgz', 'ab' * 32, self.tmp)
        self.assertEqual(self._leftovers(), [])

    def test_missing_checksum_is_refused_before_any_network(self):
        with self._urlopen() as urlopen, self.assertRaises(ArtifactError):
            fetch_artifact('https://x/a.tgz', '', self.tmp)
        urlopen.assert_not_called()

    def test_plain_http_is_refused_before_any_network(self):
        with self._urlopen() as urlopen, self.assertRaises(ArtifactError):
            fetch_artifact('http://x/a.tgz', _sha(self.data), self.tmp)
        urlopen.assert_not_called()

    def test_oversize_is_refused_and_leaves_nothing(self):
        with self._urlopen(), self.assertRaises(ArtifactError):
            fetch_artifact('https://x/a.tgz', _sha(self.data), self.tmp, max_bytes=10)
        self.assertEqual(self._leftovers(), [])

    def test_network_failure_is_an_artifact_error_not_a_crash(self):
        with (
            mock.patch(
                'core.component_updates.urllib.request.urlopen', side_effect=OSError('down')
            ),
            self.assertRaises(ArtifactError),
        ):
            fetch_artifact('https://x/a.tgz', _sha(self.data), self.tmp)
        self.assertEqual(self._leftovers(), [])


# ── inspect + extract ──────────────────────────────────────────────────────────


class ArchiveSafetyTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _refused(self, members, links=None, msg=''):
        archive = _write_tar(self.tmp, _tar_bytes(members, links=links))
        with self.assertRaises(ArtifactError, msg=msg):
            inspect_archive(archive)

    def test_good_archive_reports_its_single_top_dir(self):
        archive = _write_tar(self.tmp, _tar_bytes(GOOD_APP))
        self.assertEqual(inspect_archive(archive), 'my_app-1.4.0')

    def test_parent_traversal_refused(self):
        self._refused({'a/': None, 'a/../../evil.py': b'x'})

    def test_absolute_path_refused(self):
        self._refused({'a/': None, '/etc/passwd': b'x'})

    def test_symlink_refused(self):
        self._refused({'a/': None, 'a/app.py': b'x'}, links={'a/link': '/etc'})

    def test_two_top_level_entries_refused(self):
        self._refused({'a/': None, 'a/app.py': b'x', 'b/': None, 'b/app.py': b'y'})

    def test_loose_root_file_refused(self):
        self._refused({'a/': None, 'a/app.py': b'x', 'README': b'y'})

    def test_not_a_tarball_refused(self):
        p = self.tmp / 'junk.tar.gz'
        p.write_bytes(b'this is not gzip')
        with self.assertRaises(ArtifactError):
            inspect_archive(p)


class ExtractComponentTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / 'staging'

    def _extract(self, members, kind, name):
        archive = _write_tar(self.tmp, _tar_bytes(members))
        return extract_component(archive, self.staging, kind, name)

    def test_app_tree_is_normalised_to_its_name(self):
        out = self._extract(GOOD_APP, 'app', 'my_app')
        self.assertEqual(out, self.staging / 'my_app')
        self.assertTrue((out / 'app.py').is_file())
        self.assertTrue((out / 'migrations' / '__init__.py').is_file())
        self.assertFalse((self.staging / 'my_app-1.4.0').exists())

    def test_theme_tree_extracts(self):
        out = self._extract(GOOD_THEME, 'theme', 'my_theme')
        self.assertEqual((out / 'templates' / 'x.html').read_bytes(), b'<b>new</b>')

    def test_app_without_manifest_refused(self):
        with self.assertRaises(ArtifactError):
            self._extract({'a/': None, 'a/models.py': b'x'}, 'app', 'a')

    def test_theme_without_theme_py_refused(self):
        with self.assertRaises(ArtifactError):
            self._extract({'t/': None, 't/templates/x.html': b'x'}, 'theme', 't')

    def test_app_with_invisible_migrations_package_refused(self):
        """A migrations/ dir without __init__.py is the landmine that left five
        plugins without tables on prod while every local test passed."""
        bad = {
            'a/': None,
            'a/app.py': b'x',
            'a/migrations/': None,
            'a/migrations/0001_initial.py': b'x',
        }
        with self.assertRaises(ArtifactError):
            self._extract(bad, 'app', 'a')


# ── gates ──────────────────────────────────────────────────────────────────────


class ShipsWithCoreTests(SimpleTestCase):
    def test_a_default_app_is_refused(self):
        from django.conf import settings

        root = Path(settings.BASE_DIR)
        reason = _ships_with_core('app', 'catalog', root / 'plugins' / 'installed' / 'catalog')
        self.assertIsNotNone(reason)
        self.assertIn('with core', reason)

    def test_a_git_tracked_theme_is_refused_when_git_is_present(self):
        from django.conf import settings

        root = Path(settings.BASE_DIR)
        if not (root / '.git').exists():
            self.skipTest('no git checkout here')
        reason = _ships_with_core('theme', 'dot_books', root / 'themes' / 'library' / 'dot_books')
        self.assertIsNotNone(reason)
        self.assertIn('git', reason)

    def test_an_out_of_tree_component_is_allowed(self):
        tmp = Path(tempfile.mkdtemp()) / 'my_theme'
        tmp.mkdir()
        self.assertIsNone(_ships_with_core('theme', 'my_theme', tmp))

    def test_protected_paths_are_refused(self):
        from django.conf import settings

        root = Path(settings.BASE_DIR)
        self.assertTrue(_protected(root / 'plugins' / 'installed' / 'payments'))
        self.assertFalse(_protected(Path(tempfile.mkdtemp())))


# ── apply ──────────────────────────────────────────────────────────────────────


class ApplyComponentUpdateTests(SimpleTestCase):
    """End to end on a temp theme dir: real fetch (mocked socket), real
    verify, real extract, real swap; the boot probe and Django commands are
    stubbed because they would exercise this repo, not the temp tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.target = self.tmp / 'my_theme'
        self.target.mkdir()
        (self.target / 'theme.py').write_text('# old\n')
        (self.target / 'keep.txt').write_text('old')
        self.data = _tar_bytes(GOOD_THEME)
        self.release = ComponentRelease(
            'theme', 'my_theme', '2.0.0', artifact='https://x/t.tgz', sha256=_sha(self.data)
        )
        # `installed_components` and `call_command` are imported inside the
        # function, so they are patched where they live, not on this module.
        self.patches = [
            mock.patch(
                'core.update_sources.installed_components',
                return_value={('theme', 'my_theme'): '1.0.0'},
            ),
            mock.patch('core.component_updates.find_component_release', return_value=self.release),
            mock.patch('core.component_updates.component_dir', return_value=self.target),
            mock.patch('django.core.management.call_command'),
            mock.patch(
                'core.component_updates.urllib.request.urlopen',
                side_effect=lambda *a, **k: _Resp(self.data),
            ),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def _probe(self, ok=True):
        return mock.patch(
            'core.updates._boot_probe', return_value=(ok, '' if ok else 'ImportError')
        )

    def _siblings(self):
        return sorted(p.name for p in self.tmp.iterdir())

    def test_dry_run_changes_nothing(self):
        with self._probe():
            res = apply_component_update('theme', 'my_theme')
        self.assertEqual(res['status'], 'dry_run')
        self.assertEqual(res['plan']['to'], '2.0.0')
        self.assertEqual((self.target / 'theme.py').read_text(), '# old\n')

    def test_confirm_without_opt_in_is_disabled(self):
        with self._probe(), override_settings(MORPHEUS_SELF_UPDATE_ENABLED=False):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'disabled')
        self.assertEqual((self.target / 'theme.py').read_text(), '# old\n')

    def test_needs_newer_core_is_blocked(self):
        rel = ComponentRelease('theme', 'my_theme', '2.0.0', min_core='v99.0.0', sha256='ab' * 32)
        with (
            mock.patch('core.component_updates.find_component_release', return_value=rel),
            override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True),
        ):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'blocked')
        self.assertIn('v99.0.0', res['reason'])

    def test_missing_checksum_is_verify_failed_before_download(self):
        rel = ComponentRelease('theme', 'my_theme', '2.0.0', artifact='https://x/t.tgz')
        with (
            mock.patch('core.component_updates.find_component_release', return_value=rel),
            override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True),
        ):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'verify_failed')

    @override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
    def test_happy_path_swaps_the_tree_and_cleans_up(self):
        with self._probe(True):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'applied', res)
        self.assertTrue(res['restart_required'])
        self.assertEqual((self.target / 'templates' / 'x.html').read_bytes(), b'<b>new</b>')
        self.assertFalse(
            (self.target / 'keep.txt').exists(), 'the old tree is replaced, not merged'
        )
        self.assertEqual(self._siblings(), ['my_theme'], 'no staging/previous dirs left behind')

    @override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
    def test_boot_probe_failure_restores_the_previous_tree(self):
        with self._probe(False):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'rolled_back', res)
        self.assertEqual((self.target / 'theme.py').read_text(), '# old\n')
        self.assertTrue((self.target / 'keep.txt').exists())
        self.assertEqual(self._siblings(), ['my_theme'])

    @override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
    def test_checksum_mismatch_never_touches_the_tree(self):
        rel = ComponentRelease(
            'theme', 'my_theme', '2.0.0', artifact='https://x/t.tgz', sha256='ab' * 32
        )
        with (
            mock.patch('core.component_updates.find_component_release', return_value=rel),
            self._probe(True),
        ):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'verify_failed')
        self.assertEqual((self.target / 'theme.py').read_text(), '# old\n')
        self.assertEqual(self._siblings(), ['my_theme'])

    def test_not_installed_here_is_unavailable(self):
        with mock.patch('core.update_sources.installed_components', return_value={}):
            res = apply_component_update('theme', 'my_theme', confirm=True)
        self.assertEqual(res['status'], 'unavailable')

    def test_unknown_kind_is_unavailable(self):
        self.assertEqual(apply_component_update('gadget', 'x')['status'], 'unavailable')


# ── publisher CLI ──────────────────────────────────────────────────────────────


class SignManifestComponentsTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.private, self.public = generate_keypair()

    def _run(self, components: dict) -> dict:
        cfile = self.tmp / 'components.json'
        cfile.write_text(json.dumps(components))
        out = self.tmp / 'stable.json'
        with mock.patch.dict('os.environ', {'MORPHEUS_SIGNING_KEY': self.private}):
            call_command(
                'morph_sign_manifest',
                '--components',
                str(cfile),
                '--out',
                str(out),
                stdout=io.StringIO(),
            )
        return json.loads(out.read_text())

    def test_components_are_signed_into_the_manifest(self):
        doc = self._run(
            {
                'apps': {
                    'my_app': {
                        'version': '1.4.0',
                        'artifact': 'https://x/my_app.tgz',
                        'sha256': 'AB' * 32,
                        'min_core': 'v0.44.0',
                    }
                },
                'themes': {
                    'my_theme': {
                        'version': '2.0.0',
                        'artifact': 'https://x/t.tgz',
                        'sha256': 'cd' * 32,
                    }
                },
            }
        )
        self.assertTrue(verify_manifest(doc, self.public))
        self.assertEqual(doc['apps']['my_app']['sha256'], 'ab' * 32)
        self.assertEqual(doc['themes']['my_theme']['version'], '2.0.0')
        # And a client reads them back as components.
        src = SignedManifestSource('https://u/s.json', self.public)
        with mock.patch(
            'core.update_sources.urllib.request.urlopen',
            return_value=_Resp(json.dumps(doc).encode()),
        ):
            names = {(c.kind, c.name) for c in src.components()}
        self.assertEqual(names, {('app', 'my_app'), ('theme', 'my_theme')})

    def test_entry_without_checksum_is_rejected_at_publish_time(self):
        with self.assertRaises(CommandError):
            self._run({'apps': {'my_app': {'version': '1.0.0', 'artifact': 'https://x/a.tgz'}}})

    def test_plain_http_artifact_is_rejected_at_publish_time(self):
        with self.assertRaises(CommandError):
            self._run(
                {
                    'apps': {
                        'my_app': {'version': '1', 'artifact': 'http://x/a', 'sha256': 'ab' * 32}
                    }
                }
            )

    def test_bad_component_name_is_rejected(self):
        with self.assertRaises(CommandError):
            self._run(
                {
                    'apps': {
                        'My App': {'version': '1', 'artifact': 'https://x/a', 'sha256': 'ab' * 32}
                    }
                }
            )
