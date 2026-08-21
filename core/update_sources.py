"""Where update information comes from — the pluggable half of the updater.

`core/updates.py` orchestrates (compare → back up → apply → probe → roll back).
This module answers the prior question: *what is the latest version, and where
is its artifact?* Keeping them apart is what lets one deployment resolve
against git, another against GitHub Releases, and a commercial app against a
licensed channel, with one apply engine underneath.

Why this exists
---------------
The original source was "git fast-forward from the deployment's own upstream",
which is inert wherever there is no `.git` — including this project's own
production container. A deployment that cannot even *ask* whether an update
exists is not an update system. See `docs/UPDATING.md`.

Everything here is **read-only and fail-soft**. A source that is unreachable,
rate-limited, or misconfigured returns `None`, and the caller reports
"unknown" — never an error page, never a false "up to date".
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger('morpheus.updates')

_TIMEOUT = 10  # seconds; an update check must never hold a request open
_USER_AGENT = 'morpheus-updater'


def _ssl_context():
    """Verify TLS against certifi's bundle when available.

    `urllib` uses the interpreter's default trust store, which is empty on a
    python.org macOS build unless `Install Certificates.command` was ever run —
    so every request dies with CERTIFICATE_VERIFY_FAILED and the source looks
    "unreachable". certifi ships transitively (via requests) and gives a
    consistent bundle across dev machines and containers alike. Falls back to
    the platform default if it is somehow absent, and **never** disables
    verification: an unverified update channel is worse than no update channel.
    """
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — no certifi: use whatever the platform has
        return ssl.create_default_context()


@dataclass(frozen=True)
class ReleaseInfo:
    """One published version, as a source reports it."""

    version: str
    notes: str = ''
    url: str = ''
    artifact: str = ''
    sha256: str = ''
    signature: str = ''
    prerelease: bool = False


COMPONENT_KINDS = ('app', 'theme')


@dataclass(frozen=True)
class ComponentRelease:
    """One published version of an *app* or *theme* — the per-component channel.

    Apps and themes that ship inside the platform tree are versioned and updated
    with core. This describes the others: an app or theme installed on its own
    (a commercial app, a third-party theme) that needs a channel of its own,
    because a merchant must be able to update one of them without redeploying
    the whole platform.
    """

    kind: str  # 'app' | 'theme'
    name: str
    version: str
    artifact: str = ''
    sha256: str = ''
    min_core: str = ''  # oldest core this version runs on; '' = any
    notes: str = ''


def parse_version(value: str) -> tuple[int, ...]:
    """`'v1.2.3'` → `(1, 2, 3)`. Unparseable → `()`, which sorts lowest.

    Deliberately strict about the numeric core and forgiving about the rest:
    a tag may be `v1.2.3`, `1.2.3`, or `v1.2.3-rc1`, and all compare on
    `(1, 2, 3)`. Returning `()` rather than raising means a junk tag can never
    make the whole check fail.
    """
    m = re.match(r'^v?(\d+(?:\.\d+)*)', (value or '').strip())
    if not m:
        return ()
    return tuple(int(p) for p in m.group(1).split('.'))


def is_newer(candidate: str, current: str) -> bool:
    """True if `candidate` is a strictly higher version than `current`.

    An unparseable *candidate* is never newer — refusing to offer an update we
    cannot reason about is the safe direction. An unparseable *current* (a dev
    checkout reporting 'unknown') also yields False, so a working install is
    never told to "update" onto something we cannot compare it against.
    """
    c, n = parse_version(candidate), parse_version(current)
    if not c or not n:
        return False
    return c > n


class UpdateSource:
    """Interface. Implementations must be read-only and must not raise."""

    name = 'base'

    def latest(self) -> ReleaseInfo | None:  # pragma: no cover - interface
        raise NotImplementedError

    def components(self) -> list[ComponentRelease]:
        """Per-app / per-theme releases this source publishes. Default: none.

        Only a source that can *prove* who published an entry may offer one —
        an app update is arbitrary code that will be imported at boot, so the
        GitHub source (transport-authenticated only) deliberately returns
        nothing here.
        """
        return []


class GitHubReleaseSource(UpdateSource):
    """Resolve the latest release from the GitHub Releases API.

    Works for a public repository anonymously, and for a private one with a
    token. **A private repository answers 404 to an anonymous client**, which
    is indistinguishable from "no releases yet" — so a 404 without a token is
    reported as unknown-with-a-reason rather than "up to date". Silently
    telling a merchant they are current when we simply cannot see the releases
    would be the worst possible failure mode for an updater.
    """

    name = 'github'

    def __init__(self, repo: str, token: str = '') -> None:
        self.repo = (repo or '').strip().removeprefix('https://github.com/').strip('/')
        self.token = (token or '').strip()

    def _get(self, path: str):
        url = f'https://api.github.com/repos/{self.repo}{path}'
        # S310: the scheme is a literal https on a fixed host — only `path` and
        # the repo slug vary, and neither can introduce a scheme.
        req = urllib.request.Request(  # noqa: S310
            url,
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': _USER_AGENT,
                **({'Authorization': f'Bearer {self.token}'} if self.token else {}),
            },
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_ssl_context()) as resp:  # noqa: S310  # nosec B310 — fixed https host (line 158)
            return json.loads(resp.read().decode('utf-8'))

    def latest(self) -> ReleaseInfo | None:
        if not self.repo:
            return None
        try:
            data = self._get('/releases/latest')
        except urllib.error.HTTPError as e:
            if e.code == 404 and not self.token:
                logger.info(
                    'updates: %s returned 404 without a token — the repository is '
                    'private or has no releases; cannot distinguish. Reporting unknown.',
                    self.repo,
                )
            else:
                logger.warning('updates: github %s -> HTTP %s', self.repo, e.code)
            return None
        except Exception:  # noqa: BLE001 — network/DNS/JSON: never propagate
            logger.warning('updates: github source unreachable for %s', self.repo, exc_info=True)
            return None

        tag = str(data.get('tag_name') or '').strip()
        if not tag:
            return None
        assets = data.get('assets') or []
        artifact = next(
            (
                a.get('browser_download_url', '')
                for a in assets
                if a.get('name', '').endswith(('.tar.gz', '.zip'))
            ),
            '',
        )
        return ReleaseInfo(
            version=tag,
            notes=str(data.get('body') or ''),
            url=str(data.get('html_url') or ''),
            artifact=artifact,
            prerelease=bool(data.get('prerelease')),
        )


class SignedManifestSource(UpdateSource):
    """Resolve the latest release from a signed manifest at a fixed URL.

    This is the channel an open-core distribution actually needs: a stable,
    brandable URL the publisher controls, carrying artifacts, checksums and —
    critically — an Ed25519 signature verified against a key compiled into this
    deployment.

    **Fails closed.** An unsigned manifest, a bad signature, a wrong key, or no
    configured public key all yield `None`. The transport is not trusted: HTTPS
    proves you reached *a* server, not that the publisher wrote the bytes.
    """

    name = 'manifest'

    def __init__(self, url: str, public_key_b64: str) -> None:
        self.url = (url or '').strip()
        self.public_key = (public_key_b64 or '').strip()
        self._doc: dict | None = None
        self._fetched = False

    def _verified_document(self) -> dict | None:  # noqa: PLR0911 — flat guard clauses
        """Fetch the manifest once and return it only if its signature verifies.

        Memoised per instance so `latest()` and `components()` — which a single
        check calls back to back — read one verified document rather than
        fetching twice and risking a mid-check swap between them.
        """
        if self._fetched:
            return self._doc
        self._fetched = True
        if not self.url:
            return None
        if not self.url.lower().startswith('https://'):
            logger.error('updates: refusing a non-HTTPS manifest URL')
            return None
        if not self.public_key:
            logger.error(
                'updates: a manifest URL is set but no public key — refusing to '
                'trust an unverifiable manifest. Set MORPHEUS_UPDATE_PUBLIC_KEY.'
            )
            return None
        try:
            req = urllib.request.Request(  # noqa: S310 — https enforced above
                self.url, headers={'User-Agent': _USER_AGENT, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 — https enforced at line 245
                req, timeout=_TIMEOUT, context=_ssl_context()
            ) as resp:
                doc = json.loads(resp.read().decode('utf-8'))
        except Exception:  # noqa: BLE001 — unreachable/malformed: unknown, not "no"
            logger.warning('updates: manifest unreachable at %s', self.url, exc_info=True)
            return None

        from core.signing import verify_manifest

        if not verify_manifest(doc, self.public_key):
            logger.error(
                'updates: manifest at %s failed signature verification — ignoring it '
                'entirely. This is either a misconfigured key or a tampered channel.',
                self.url,
            )
            return None
        self._doc = doc
        return doc

    def latest(self) -> ReleaseInfo | None:
        doc = self._verified_document()
        if doc is None:
            return None
        core = doc.get('core') or {}
        version = str(core.get('version') or '').strip()
        if not version:
            return None
        return ReleaseInfo(
            version=version,
            notes=str(core.get('notes') or ''),
            url=str(core.get('notes') or ''),
            artifact=str(core.get('artifact') or ''),
            sha256=str(core.get('sha256') or ''),
            signature=str(doc.get('signature') or ''),
        )

    def components(self) -> list[ComponentRelease]:
        """Every app/theme entry of a *verified* manifest — nothing otherwise.

        The signature covers the whole document, so each entry's `sha256` is
        bound to the publisher's key: an artifact that hashes to it is one the
        publisher vouched for, not merely one a server handed us.
        """
        doc = self._verified_document()
        if doc is None:
            return []
        out: list[ComponentRelease] = []
        for kind, key in (('app', 'apps'), ('theme', 'themes')):
            entries = doc.get(key) or {}
            if not isinstance(entries, dict):
                continue
            for name, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                version = str(entry.get('version') or '').strip()
                if not name or not version:
                    continue
                out.append(
                    ComponentRelease(
                        kind=kind,
                        name=str(name),
                        version=version,
                        artifact=str(entry.get('artifact') or ''),
                        sha256=str(entry.get('sha256') or '').lower(),
                        min_core=str(entry.get('min_core') or ''),
                        notes=str(entry.get('notes') or ''),
                    )
                )
        return out


def configured_source() -> UpdateSource | None:
    """Build the source this deployment is configured to use, or None.

    Configuration is read from Django settings (env-backed), not a plugin
    config: the updater must resolve before any app is guaranteed active, and
    `core/updates.py` is permanently core for the same reason.

        MORPHEUS_UPDATE_MANIFEST_URL  a signed manifest (preferred)
        MORPHEUS_UPDATE_PUBLIC_KEY    base64 Ed25519 key that must sign it
        MORPHEUS_UPDATE_REPO          e.g. 'magnetoid/morpheus' (fallback)
        MORPHEUS_UPDATE_TOKEN         optional; required for a private repository

    The signed manifest wins when configured: it is the only source that proves
    the publisher produced the bytes. The GitHub source is a convenience for a
    deployment tracking its own repository, and carries no such proof.
    """
    from django.conf import settings

    manifest_url = str(getattr(settings, 'MORPHEUS_UPDATE_MANIFEST_URL', '') or '').strip()
    if manifest_url:
        public_key = str(getattr(settings, 'MORPHEUS_UPDATE_PUBLIC_KEY', '') or '').strip()
        return SignedManifestSource(manifest_url, public_key)

    repo = str(getattr(settings, 'MORPHEUS_UPDATE_REPO', '') or '').strip()
    if not repo:
        return None
    token = str(getattr(settings, 'MORPHEUS_UPDATE_TOKEN', '') or '').strip()
    return GitHubReleaseSource(repo, token)


def installed_components() -> dict[tuple[str, str], str]:
    """`{(kind, name): version}` for every registered app and discovered theme."""
    from core.versioning import plugin_versions, theme_versions

    out: dict[tuple[str, str], str] = {}
    for p in plugin_versions():
        out[('app', p['name'])] = str(p.get('version') or '')
    for t in theme_versions():
        out[('theme', t['name'])] = str(t.get('version') or '')
    return out


def component_updates(
    source: UpdateSource | None = None,
    installed: dict[tuple[str, str], str] | None = None,
    core_version: str | None = None,
) -> list[dict]:
    """Apps/themes the source publishes a newer version of than what's installed.

    Only components that are *installed here* are reported — a manifest may
    list a hundred apps; a merchant cares about the three they run. Each entry
    is `{kind, name, current, latest, artifact, sha256, min_core, notes,
    core_ok}`, where `core_ok` is False when the release needs a newer core
    than this deployment runs: still shown (so the merchant learns core is the
    blocker), but `apply` refuses it.
    """
    source = source if source is not None else configured_source()
    if source is None:
        return []
    installed = installed if installed is not None else installed_components()
    if core_version is None:
        from core.versioning import core_version as _core

        core_version = _core()

    out: list[dict] = []
    for rel in source.components():
        current = installed.get((rel.kind, rel.name))
        if current is None or not is_newer(rel.version, current):
            continue
        out.append(
            {
                'kind': rel.kind,
                'name': rel.name,
                'current': current,
                'latest': rel.version,
                'artifact': rel.artifact,
                'sha256': rel.sha256,
                'min_core': rel.min_core,
                'notes': rel.notes,
                'core_ok': not rel.min_core or not is_newer(rel.min_core, core_version),
            }
        )
    return out


def check_for_update(current_version: str) -> dict:
    """Ask the configured source whether something newer exists.

    Returns the same `available ∈ {yes, no, unknown, unavailable}` vocabulary
    `core/updates.py:platform_update_status` uses, so a caller can treat the
    git path and this path identically. `components` lists per-app/theme
    updates (see `component_updates`); it is empty for a source that cannot
    vouch for component artifacts.
    """
    source = configured_source()
    if source is None:
        return {
            'source': 'none',
            'available': 'unavailable',
            'reason': 'No update source configured (set MORPHEUS_UPDATE_REPO).',
            'current': current_version,
            'components': [],
        }

    release = source.latest()
    if release is None:
        return {
            'source': source.name,
            'available': 'unknown',
            'reason': 'Update source unreachable, or its releases are not visible to us.',
            'current': current_version,
            'components': [],
        }

    newer = is_newer(release.version, current_version)
    return {
        'source': source.name,
        'available': 'yes' if newer else 'no',
        'current': current_version,
        'latest': release.version,
        'notes_url': release.url,
        'artifact': release.artifact,
        'prerelease': release.prerelease,
        'components': component_updates(source, core_version=current_version),
    }
