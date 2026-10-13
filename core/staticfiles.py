"""Static file storage: hashed names, and never a 500 for a file the manifest lacks.

Every changed file gets a new URL (`refresh.ed381c93aa0c.css`), so a CDN can cache
static files for as long as it likes and still serve the new CSS the moment a deploy
lands. Django's manifest storage raises for a name it cannot find, which turns a
template's reference to a missing file into a failed page; here it is served under its
plain name and logged once instead.
"""

from __future__ import annotations

import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger('morpheus.static')

_warned: set[str] = set()


class HashedStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            if name not in _warned and len(_warned) < 256:
                _warned.add(name)
                logger.warning('static: %s is not among the collected files', name)
            return name
