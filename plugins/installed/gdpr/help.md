---
summary: Gives shoppers a page to export or delete their data, and seeds your store's legal pages.
---

## What it's for

This app adds a "Privacy & data" page to the customer account area, where a signed-in shopper can download a copy of their own data or ask to have their account deleted and their personal details scrubbed. It also writes six legal pages for your storefront footer — Privacy Policy, Terms & Conditions, Cookie Policy, Imprint, Accessibility, and FAQ — and keeps them from going missing. Cookie consent itself is handled by a separate app.

## Set it up

Fill in [](field:gdpr.data_controller_name) and [](field:gdpr.data_controller_email) in [Settings](settings:gdpr) — they are written into the Privacy Policy and the other legal pages. You can also write your own notice about AI use, with [](field:gdpr.ai_disclosure_text), for AI features that shoppers use; no storefront page shows that notice yet.

## Common tasks

- Edit the wording of a seeded legal page like your Privacy Policy from [Pages](page:cms/pages), the same way you'd edit any other page.

## Good to know

This whole area can be switched off from the general store settings, in which case it answers "not found" everywhere a shopper would reach it. A deletion request scrubs the shopper's name, email and addresses and signs them out; it cannot be undone. Every export and deletion request is recorded, but there is currently no dashboard screen to review that record.
