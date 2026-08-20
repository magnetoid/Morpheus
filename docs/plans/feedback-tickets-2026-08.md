# Feedback tickets — staff bug reports with screenshot + logs

**Asked for (2026-08-20):** a Feedback link in the dashboard's top-right user
dropdown. Clicking it opens a modal that takes a message from the user, captures
a full-screen snapshot, attaches error logs, and opens a **ticket**. Tickets are
listed in **admin Settings** (not superadmin).

## Shape

A new app, `plugins/installed/feedback/` — nothing about this is required for
catalog → cart → checkout → fulfilment, so it is a plugin (CLAUDE.md).

```
dashboard user dropdown  ──DASHBOARD_USER_MENU──▶  "Send feedback"
        │ (click)
        ▼
  modal (contributed via DASHBOARD_BODY_END)
   ├─ message  (required, the only thing the human types)
   ├─ screenshot   navigator.mediaDevices.getDisplayMedia → canvas → JPEG
   ├─ client errors  the ring buffer core/static/core/error-capture.js already feeds
   └─ context      url, viewport, user-agent, MORPHEUS_VERSION, request_id
        │ POST (staff-only, CSRF, data-ajax JSON contract)
        ▼
  FeedbackTicket ──▶ Dashboard → Settings → Feedback (list + detail)
```

## Two new core seams

The dashboard shell must not import an optional app (ADR 0023), and there is no
user-menu or body-end hook today. Core fires, the app answers:

- `DASHBOARD_USER_MENU` — filter, `value=list[dict]`
  `{label, url, icon, order, attrs}`; mirrors the `DASHBOARD_KPIS` accumulator
  shape. Fired by `admin_dashboard/context_processors.py`.
- `DASHBOARD_BODY_END` — filter, `value=list[str]` of template paths, included
  at the end of `<body>`. The dashboard's equivalent of the storefront's
  `global_below_body` slot; this is what lets an app ship a modal.

Both are gated by the hook bus's active-check, so **disabling `feedback` removes
the menu item and the modal for free** (the ADR 0024 property).

## Model

`FeedbackTicket` — `user` FK (nullable on delete), `message`, `status`
(`open`/`in_progress`/`closed`), `screenshot` ImageField (nullable — capture can
be declined), `screenshot_skipped_reason`, `page_url`, `page_title`, `viewport`,
`user_agent`, `client_errors` JSON, `context` JSON, `created_at`, `updated_at`.

`migrations/__init__.py` **must exist** or the table is never created on prod
while every local test passes (the v0.41.1 landmine).

## Decisions taken

- **Screenshot via `getDisplayMedia`, not a JS library.** It is a native browser
  API, so this adds zero dependencies — html2canvas/dom-to-image would mean
  vendoring ~150KB into a dashboard that has no JS build step. Cost: the browser
  shows its own picker/permission prompt. Capture is therefore **best-effort** —
  if it is denied or unsupported the ticket still submits, and the reason is
  recorded rather than silently dropped.
- Downscale to ≤1600px wide and encode JPEG q0.75 before upload; a raw PNG of a
  1440×900 screen blows past `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5MB).
- **Errors come from `core/errors.ErrorEvent`**, which already ingests client JS
  errors via `/api/errors/client/` and server exceptions. The ticket snapshots
  the recent ones rather than starting a second pipeline.
- **Gate on the existing `system.read` / `system.write` capabilities.** Inventing
  `feedback.*` would be the "capability no role holds denies everyone once
  enforcement is on" landmine, since no role template would grant it.
- Submitting is allowed for any signed-in staff member (`@staff_member_required`)
  — reporting a bug must not require the permission to read the queue.

## Verification

- permission triplet on both dashboard views; submit endpoint rejects anonymous
- disable `feedback` → dropdown item gone, modal gone, both pages 404
- `migrations/__init__.py` present; `makemigrations --check` clean
- ticket created with message only (capture declined) and with a screenshot
- every changed template compiled via `get_template()`
