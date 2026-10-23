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

# core/errors/health.py

Symbols in `core/errors/health.py`.

- L22 `fetch_failures(paths: list[str])` (function) — GET each path on the public site (through the CDN, like a shopper); list failures.
- L49 `_uploads_check()` (function) — Save and delete a tiny file in the media storage, as an upload would.
- L78 `smtp_configured()` (function) — Module-level seam (tests patch it); the import stays lazy.
- L85 `_txt_records(name: str)` (function) — TXT records for ``name`` over DNS-over-HTTPS (no resolver dependency,
- L111 `_sender_domain()` (function) — The domain mail goes out from: the merchant's sender, else the deployment's.
- L129 `_email_auth_check()` (function) — SPF + DMARC published for the sending domain, or the mail is filtered.
- L163 `_core_checks()` (function)
- L194 `run_checks()` (function) — Core checks plus every app's ``HEALTH_CHECKS`` contribution.
- L206 `run_and_report()` (function) — Run every check; record and email the failures. Returns the failures.
