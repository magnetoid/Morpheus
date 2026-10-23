---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/signing.py

Symbols in `core/signing.py`.

- L29 `_b64d(value: str)` (function) — Strict base64 decode. Any malformation raises, and callers treat that as
- L35 `generate_keypair()` (function) — Return `(private_key_b64, public_key_b64)` for a new Ed25519 keypair.
- L61 `sign(payload: bytes, private_key_b64: str)` (function) — Sign `payload`, returning a base64 signature. Publisher-side.
- L69 `verify(payload: bytes, signature_b64: str, public_key_b64: str)` (function) — True only if `signature_b64` is a valid signature over `payload`.
- L102 `canonical_bytes(manifest: dict[str, Any])` (function) — The exact bytes to sign/verify for a manifest, excluding its signature.
- L114 `sign_manifest(manifest: dict[str, Any], private_key_b64: str)` (function) — Return a copy of `manifest` with a `signature` over its canonical form.
- L121 `verify_manifest(manifest: dict[str, Any], public_key_b64: str)` (function) — True only if the manifest carries a valid signature for `public_key_b64`.
