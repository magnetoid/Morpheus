---
summary: Lets staff sign in through your company's own identity provider instead of an email code.
---

## What it's for
This lets your team sign in through your company's own identity provider — Okta, Microsoft Entra, Google Workspace, or any OIDC or SAML 2.0 provider — instead of the email sign-in code. The first sign-in from an allowed account creates their staff account automatically.

## Set it up
Off by default. For OIDC, fill in the issuer address, client ID and client secret in [](settings:staff_sso). For SAML, turn on [](field:staff_sso.saml_enabled) and either give its metadata address or enter the entity ID, sign-in address and certificate by hand. Either way, set [](field:staff_sso.allowed_domains) so only people with an email at those domains can sign in this way, or [](field:staff_sso.staff_groups) to admit specific groups from your provider regardless of domain.

## Common tasks
- Connect your identity provider's details in [](settings:staff_sso).
- Restrict who may sign in this way by email domain, or by a group your provider sends.
- Turn on SAML sign-in alongside, or instead of, OIDC.
- Turn the whole thing off to return everyone to the plain email sign-in code.

## Good to know
A team member who already has two-factor sign-in set up is still asked for their code after signing in this way — this cannot be used to skip it. Signing in this way never creates a shopper account; it only ever provisions staff. Turning this app off removes the sign-in button and puts sign-in back exactly the way it was before.
