"""Ed25519 signing for release manifests — the integrity half of the updater.

Without this, an update channel trusts whatever the network hands it. Anyone who
compromises the release host, the CDN, or a client's DNS can ship arbitrary code
to every install. A checksum alone does not help: it travels beside the artifact
and an attacker who can replace one can replace the other. A signature is the
only thing that binds an artifact to a key we decided to trust in advance.

**This module fails CLOSED — deliberately the opposite of `core/authz.py`.**
There, an absent answerer falls back to prior behaviour, because locking a
merchant out of their dashboard is worse than a missed permission check. Here,
anything unverified is rejected: running unverified code is worse than not
updating. Every ambiguity resolves to `False`.

The same keypair serves the commercial edition's licence checks, so it is built
once here rather than twice.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

logger = logging.getLogger('morpheus.signing')


def _b64d(value: str) -> bytes:
    """Strict base64 decode. Any malformation raises, and callers treat that as
    "unverified" — never as "close enough"."""
    return base64.b64decode(value.strip().encode('ascii'), validate=True)


def generate_keypair() -> tuple[str, str]:
    """Return `(private_key_b64, public_key_b64)` for a new Ed25519 keypair.

    Publisher-side only. The private key never belongs in this repository, in a
    container image, or in a deployment's environment — it belongs wherever you
    build releases, and nowhere else.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    private = ed25519.Ed25519PrivateKey.generate()
    raw_private = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        base64.b64encode(raw_private).decode('ascii'),
        base64.b64encode(raw_public).decode('ascii'),
    )


def sign(payload: bytes, private_key_b64: str) -> str:
    """Sign `payload`, returning a base64 signature. Publisher-side."""
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = ed25519.Ed25519PrivateKey.from_private_bytes(_b64d(private_key_b64))
    return base64.b64encode(key.sign(payload)).decode('ascii')


def verify(payload: bytes, signature_b64: str, public_key_b64: str) -> bool:
    """True only if `signature_b64` is a valid signature over `payload`.

    Returns False for every failure mode — bad signature, malformed key,
    malformed base64, missing input, or a library error. There is no path that
    raises, because a caller that forgets a try/except must not end up applying
    an unverified update.
    """
    if not (payload and signature_b64 and public_key_b64):
        return False
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519

        key = ed25519.Ed25519PublicKey.from_public_bytes(_b64d(public_key_b64))
        try:
            key.verify(_b64d(signature_b64), payload)
        except InvalidSignature:
            logger.warning('signing: signature did not verify')
            return False
        return True
    except Exception:  # noqa: BLE001 — malformed key/base64/etc: unverified
        logger.warning('signing: verification failed', exc_info=True)
        return False


# ── Manifest canonicalisation ────────────────────────────────────────────────
#
# The bytes that get signed must be reproducible from the parsed document, or a
# publisher and a client will disagree about what was signed over whitespace.
# `sort_keys` + fixed separators + no ASCII escaping gives one canonical form.


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    """The exact bytes to sign/verify for a manifest, excluding its signature.

    The `signature` field is removed first — a document cannot contain a
    signature over itself.
    """
    body = {k: v for k, v in manifest.items() if k != 'signature'}
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(
        'utf-8'
    )


def sign_manifest(manifest: dict[str, Any], private_key_b64: str) -> dict[str, Any]:
    """Return a copy of `manifest` with a `signature` over its canonical form."""
    signed = {k: v for k, v in manifest.items() if k != 'signature'}
    signed['signature'] = sign(canonical_bytes(signed), private_key_b64)
    return signed


def verify_manifest(manifest: dict[str, Any], public_key_b64: str) -> bool:
    """True only if the manifest carries a valid signature for `public_key_b64`."""
    if not isinstance(manifest, dict):
        return False
    signature = manifest.get('signature')
    if not isinstance(signature, str) or not signature:
        logger.warning('signing: manifest carries no signature')
        return False
    return verify(canonical_bytes(manifest), signature, public_key_b64)
