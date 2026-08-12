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
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_ssl_context()) as resp:  # noqa: S310
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


def configured_source() -> UpdateSource | None:
    """Build the source this deployment is configured to use, or None.

    Configuration is read from Django settings (env-backed), not a plugin
    config: the updater must resolve before any app is guaranteed active, and
    `core/updates.py` is permanently core for the same reason.

        MORPHEUS_UPDATE_REPO   e.g. 'magnetoid/morpheus'
        MORPHEUS_UPDATE_TOKEN  optional; required for a private repository
    """
    from django.conf import settings

    repo = str(getattr(settings, 'MORPHEUS_UPDATE_REPO', '') or '').strip()
    if not repo:
        return None
    token = str(getattr(settings, 'MORPHEUS_UPDATE_TOKEN', '') or '').strip()
    return GitHubReleaseSource(repo, token)


def check_for_update(current_version: str) -> dict:
    """Ask the configured source whether something newer exists.

    Returns the same `available ∈ {yes, no, unknown, unavailable}` vocabulary
    `core/updates.py:platform_update_status` uses, so a caller can treat the
    git path and this path identically.
    """
    source = configured_source()
    if source is None:
        return {
            'source': 'none',
            'available': 'unavailable',
            'reason': 'No update source configured (set MORPHEUS_UPDATE_REPO).',
            'current': current_version,
        }

    release = source.latest()
    if release is None:
        return {
            'source': source.name,
            'available': 'unknown',
            'reason': 'Update source unreachable, or its releases are not visible to us.',
            'current': current_version,
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
    }
