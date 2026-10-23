---
summary: Adds an authenticator-app code as a second step when staff sign in.
---

## What it's for
This adds a second step to staff sign-in: after the usual email code or password, an enrolled team member also enters a code from an authenticator app. It applies only to staff accounts, not shoppers.

## Set it up
Turn on [](field:staff_mfa.require_for_staff) to make this mandatory for every staff account; left off, each person can still choose to enroll for themselves. Set the issuer name shown inside the authenticator app in [](field:staff_mfa.issuer).

## Common tasks
- Scan the QR code and confirm it in [](page:enroll) to turn on two-factor sign-in for yourself.
- Save the one-time recovery codes shown right after you confirm — they're the only way back in if you ever lose your device.
- Turn two-factor off for your own account from the same page.
- Require it for every staff account at once in [](field:staff_mfa.require_for_staff).

## Good to know
The very first admin account gets a grace period, so turning this on can never lock everyone out before anyone has enrolled. If someone loses their device and has no recovery codes left, only a developer with server access can clear their enrollment so they can set it up again — there is no self-service reset for that from the dashboard.
