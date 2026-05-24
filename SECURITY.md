# Security policy

If you've found a security issue in Morpheus, please report it
**privately** — do not open a public GitHub issue.

## Where to send reports

Email: **marko.tiosavljevic@gmail.com**

Subject line prefix: `[security][morpheus]`

Include, if you can:

- A short description of the issue and the affected component.
- Exact reproduction steps (URL paths, payloads, request method,
  whether authentication is required).
- The commit SHA or version where you observed the issue.
- Impact assessment (data exposed, privilege boundary crossed,
  availability impact).
- Any proof-of-concept code or screenshots, in a private gist or
  encrypted attachment if sensitive.

If the issue is critical (RCE, auth bypass, full data exposure),
mark it `[security][critical][morpheus]` so it gets triaged ahead
of normal mail.

## Response timeline

| Severity | First response | Patch target |
|---|---|---|
| Critical (RCE, auth bypass) | 24 hours | 72 hours |
| High (privilege escalation, sensitive data leak) | 72 hours | 14 days |
| Medium (XSS, CSRF on non-critical path) | 7 days | 30 days |
| Low (info disclosure, hardening gaps) | 14 days | next minor |

We'll acknowledge receipt, confirm the issue, agree on a coordinated
disclosure date, and credit the reporter in the release notes
(unless you ask to stay anonymous).

## Supported versions

Only the `main` branch and the most-recent tagged release are
actively patched. Earlier tags will not receive backports unless
the issue is critical.

## Scope

In scope:

- Core platform (`core/`, `morph/`).
- Plugins shipped under `plugins/installed/`.
- Default theme (`themes/library/dot_books/`).
- The Cloudflare admin app (`plugins/installed/cloudflare/`).

Out of scope:

- Third-party services we depend on (Stripe, Cloudflare, GitHub) —
  report those upstream.
- Bugs in user-installed third-party plugins not shipped in this repo.
- Issues that require an attacker to already control the admin user
  or to have shell access to the host.
- Self-XSS, missing security headers in headers that browsers
  no longer enforce (e.g. X-XSS-Protection on modern browsers).
- Social engineering, phishing of maintainers, physical attacks.

## What we already do

- `SecurityHeadersMiddleware` emits HSTS, X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy, and a strict Permissions-Policy
  on every response.
- All write-endpoints require CSRF except where explicitly exempted
  (Stripe webhook, public newsletter, the rate-limited error
  ingestor at `/api/errors/client/`).
- GraphQL mutations go through `core.audit` for AI-decision sites
  that bypass the normal permission boundary.
- Plugin / admin code is gated by pre-commit hooks that block
  obvious AI-generated landmines: `f"..."` SQL interpolation,
  `mark_safe` on untrusted input, missing `@require_http_methods`,
  hallucinated `requirements.txt` lines.
- Server / TLS configuration is documented for self-hosters in
  `docs/`.

## Coordinated disclosure

We follow a 90-day default disclosure window. If a fix is shipped
sooner, we will publish a CVE + release notes at the patch release;
if a fix is delayed past 90 days, we'll work with the reporter on a
mutually-agreed schedule rather than force-disclosing.

Reporters are credited unless they prefer anonymity.

## PGP

If you'd prefer encrypted email, request a PGP key in your initial
plaintext message — we'll send a fresh key for the disclosure
thread.
