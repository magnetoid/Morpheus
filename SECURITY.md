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

## Role-based access control (enforcement is opt-in)

Morpheus ships roles and capabilities (`rbac` app: 26 capabilities, six built-in
role templates, optionally scoped per sales channel). **Enforcement defaults to
log-only**, so installing an update never changes who can do what.

The three modes live in **Settings → Other apps → Roles & permissions**:

| Mode | Behaviour |
|---|---|
| `off` | No capability check runs. |
| `log` *(default)* | Every check runs and records what it **would** have denied, then allows it. |
| `enforce` | Failed checks are denied — 403, or a JSON error for dashboard fetch endpoints. |

**Recommended rollout.** Leave it on `log`, assign roles to your staff, then
read the audit log for `authz.would_deny` events. Each one is an action someone
performs today that enforcement would block. When that list contains only things
you *want* blocked, switch to `enforce`.

Two properties worth knowing before you flip it:

- **Superusers always pass**, so you cannot lock yourself out of your own store.
- **Staff users with no role hold no capabilities.** In `enforce` mode a staff
  account without a role binding loses access to every gated action. Assign
  roles *before* switching.

If the `rbac` app is absent or fails to answer, the check falls back to the
historical `is_staff` behaviour rather than denying — an authorization layer
that failed closed on its own absence would lock every merchant out on a single
hiccup. Denial is always an explicit choice.

Coverage today is **partial and expanding**: the money and destructive paths
(order refunds and state changes, product/variant/media writes and deletes,
customer and collection deletes) are gated. Read-only list views and the
remaining settings surfaces are not yet. Ungated actions behave exactly as they
did before, i.e. staff-only.

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
- Staff sign-in can require a second factor (`staff_mfa` plugin):
  TOTP after the email-OTP succeeds, via the `AUTH_SECOND_FACTOR`
  core hook. Recovery codes are SHA-256 hashed and single-use,
  enforcement is opt-in (`require_for_staff`), the challenge is
  rate-limited, and resets are audited (`mfa.*`). Disabling the
  plugin reverts sign-in to single-factor email-OTP.
- Federated staff SSO (`staff_sso` plugin, OFF by default): OIDC +
  SAML 2.0 via `django-allauth`, with email-domain allowlist /
  group-claim staff-gating and JIT provisioning that links existing
  customers only on a *verified* IdP email. **SSO does not bypass
  MFA** — the adapter runs the same `staff_mfa` second-factor gate
  on the SSO path (allauth's `login()` doesn't fire
  `AUTH_SECOND_FACTOR`, so the adapter calls into `staff_mfa` and
  redirects to the TOTP challenge). SAML trusts email only from a
  signature-validated (signed) assertion; email-OTP stays available
  as the break-glass path.
- Plugin settings-panel secrets (API keys, the SSO client secret,
  etc.) are write-only: the shared panel renderer masks
  `format: password` JSON-schema fields, never pre-fills the stored
  value, and a blank submit preserves the existing secret rather
  than echoing it back in cleartext.
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
