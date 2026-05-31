"""csp collector — subscribes to a new MorpheusEvents.CSP_VIOLATION_REPORTED.

The existing CSP report endpoint at `/api/csp-report/` only logs the
violation today. We add a hook fire there so this collector can
subscribe — that keeps the endpoint stable and lets other plugins
(e.g. a future security-alerts plugin) listen to the same stream.

Fingerprint shape: SOURCE:directive:blocked_uri:document_uri. The
analyzer turns a cluster of identical violations into a recommendation
to either allowlist the origin (if reputable) or tighten the policy
(if zero legit traffic).
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from core.self_improvement.services import emit_signal, fingerprint_for

logger = logging.getLogger('morpheus.self_improvement.csp')

SOURCE = 'csp'


def _normalise_uri(uri: str) -> str:
    """Strip path/query so different paths under the same origin dedup."""
    if not uri or uri in ('?', 'self', 'inline'):
        return uri
    try:
        parsed = urlparse(uri)
        if parsed.scheme and parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}'
    except Exception:  # noqa: BLE001, S110 — never break collection on a parse error
        pass
    return uri[:200]


def on_csp_violation_reported(
    *,
    directive: str = '',
    blocked_uri: str = '',
    document_uri: str = '',
    line: Any = None,
    source_file: str = '',
    **_: Any,
) -> None:
    """Hook handler — kwargs match what api/views.csp_report fires."""
    if not directive and not blocked_uri:
        return

    blocked_origin = _normalise_uri(blocked_uri)
    document_origin = _normalise_uri(document_uri)

    fp = fingerprint_for(SOURCE, directive, blocked_origin, document_origin)
    severity = _severity_for(directive, blocked_origin)

    try:
        emit_signal(
            source=SOURCE,
            fingerprint=fp,
            severity=severity,
            payload={
                'directive': directive[:64],
                'blocked_uri': blocked_uri[:300],
                'document_uri': document_uri[:300],
                'source_file': str(source_file or '')[:300],
                'line': str(line) if line is not None else '',
            },
        )
    except Exception:  # noqa: BLE001 — never break the CSP endpoint
        logger.exception('csp: emit_signal failed for %s/%s', directive, blocked_origin)


def _severity_for(directive: str, blocked: str) -> int:
    """Heuristic severity. script-src violations are higher than style-src
    (XSS surface vs. visual breakage). Known-bad blocked URIs spike to 80.
    """
    base = 40
    if 'script' in directive:
        base = 65
    elif 'frame' in directive or 'object' in directive:
        base = 70
    if 'data:' in blocked or 'javascript:' in blocked:
        base = max(base, 80)
    return base
