# C1 — Post-purchase emails that actually send (design, short)

Approved by the owner 2026-11-23 ("go", option 1: the review request and the NPS
survey are marketing; "did it arrive" is service).

## Why

`docs/plans/platform-gap-analysis-2026-11.md` row 9: mail is the channel the store
owns, and the post-purchase journey was nearly built. Nothing ever sent it:
`post_purchase.process_due_steps` was never in the beat schedule, so every order on
every store queued steps that sat in the database.

## What exists today (read 2026-11-23, main c85b8a3f)

- Handlers queue four steps per order (tracking, delivered follow-up, review request,
  NPS), reading config keys the settings schema never declared (defaults: all on).
- The sender is a bare `send_mail` to the account's address, with hand-written text
  signed "The dot books team" and an NPS link built from `ALLOWED_HOSTS[0]`.
- The tracking step duplicates core's "on its way" email, which already carries
  tracking for every parcel.

## Approaches

1. **Wire the existing journey through `core.emails` (picked).** Keep `JourneyStep`
   as the ledger; templated emails; settings in the schema; marketing steps gated.
2. Move the journey into `notifications`/`marketing`. Rejected: post_purchase owns
   the ledger and the NPS report; a move is churn with no gain.
3. Only add the beat entry. Rejected: it would mail the whole backlog, unbranded,
   to the wrong address, with no consent check.

## Design

- **Beat:** `post_purchase:process_due_steps` every 15 minutes, by its registered
  name, through `register_celery_beat`.
- **Settings** (post_purchase schema, each read by the handlers and the sender):
  `delivered_followup_enabled` / `_delay_hours` (24), `review_request_enabled` /
  `_delay_days` (14), `nps_survey_enabled` / `_delay_days` (30). **Every step defaults
  to off**, because today nothing is sent (owner rule: default = what the store did).
  Linda reads and changes them with the generic `settings.describe` / `settings.set`.
- **Tracking step dropped:** no longer scheduled; a queued one is skipped (core sends it).
- **Late steps skipped, never sent:** a step more than 3 days past its due time is
  skipped (`error='late'`), so switching a step on never mails the backlog. So is a
  step whose kind is switched off, or whose order was cancelled or refunded.
- **Templated emails** (`core.emails`, editable on the dashboard):
  `post_purchase_delivered`, `post_purchase_review`, `post_purchase_nps`, sent to
  `order.email`, signed with the store's name.
- **Marketing gate** (review request, NPS): `core.consent.allowed('marketing',
  order=order)` and the address not opted out; otherwise skipped (`error='no consent'`
  / `'opted out'`). The delivered follow-up is service and goes to everyone.
- **One-click unsubscribe:** a signed token over the address; `JourneyOptOut(email)`;
  RFC 8058 `List-Unsubscribe` + `List-Unsubscribe-Post` headers and a footer link.
  GET shows a confirm button (link scanners prefetch GETs), POST records the opt-out.
- **Report clicks and orders, not opens:** every link carries
  `utm_source=post_purchase&utm_medium=email&utm_campaign=<step>`, so the existing
  Attribution report counts the visits and the orders. No open pixel.

## Left to the builder

Template wording; the confirm page's look (theme base, `noindex`).
