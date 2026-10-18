---
summary: Issues the tokens outside systems and AI agents use to read or change your store, and the files AI shopping agents use to find it.
---

## What it's for

This app is how anything outside the dashboard reaches your store: another system you connect, or an AI agent acting for a customer or for you. It issues the tokens those connections use, and it automatically publishes the files an AI shopping agent reads to discover your store and how to talk to it. Browsing your storefront, adding to a cart and checking out need no token at all; only the full admin connection and asking Linda do.

## Set it up

Create an [API token](page:tokens) for anything that needs one: another system, or an agent working on your behalf. Pick what it is for, then copy its connection details before you leave the page — the secret part is shown only once.

## Common tasks

- Create a token for a purpose and hand its connection details to the other party.
- Turn on more permissions for a token, or tick the extra sensitive actions it may take.
- Make a new secret for a token that may have leaked, without changing anything else about it.
- Revoke a token that should no longer be able to reach the store.

## Good to know

A token's full secret is shown once, when it is created or given a new secret; afterwards the page only shows its last few characters. A handful of sensitive actions — hard-deleting products, reading system diagnostics, changing system settings, completing a checkout — are never switched on by a preset and must be ticked by hand. Orders placed by a recognised AI agent are stamped with which one placed them; this is only a record and does not give that agent any extra permission.
