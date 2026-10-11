# Detailed error capture (owner's ask, 2026-10-11)

> "There should be an option for more extended error logging: a button in the
> error log that turns it on, so later I can point Claude Code at each platform
> and resolve the errors. Very detailed, collecting errors from everywhere."

## What already exists (standard capture, always on)

`core/errors` stores `ErrorEvent` rows, grouped by fingerprint on
`/dashboard/errors/`: unhandled view exceptions (middleware), ERROR+ log records
(`core/brain/log_handler.py`, one row per fingerprint per minute), Celery task
failures (`morph/celery.py`), health-check failures, and browser errors
(`core/static/core/error-capture.js` → `/api/errors/client/`). A daily digest
emails new errors; rows are pruned after 30 days.

## Detailed capture (a switch with an end time)

One switch on the error log page: **Turn on for 24 hours / 7 days**, **Turn off**.
It switches itself off at the end time, so a forgotten switch never leaves a store
logging every warning for months. Stored in `ErrorCaptureMode` (one row), read
through `core/errors/mode.py` with a 10-second in-process memo (web and worker
see a change within seconds; the hot path never queries per log line). Turning it
on or off writes an audit event.

While it is on, the store also records:

| Source | What | Level |
|---|---|---|
| Logs | WARNING records from the app, request, security and Celery loggers (plus `py.warnings`) | warning |
| Requests | rejected requests: 400, 403 (CSRF included), 405, 429 | warning |
| Requests | a 404 reached from a page on the same site (a broken internal link) | warning |
| Requests | a 5xx answered without an exception | error |
| Requests | a response slower than 3 s | warning |
| Celery | a task retry | warning |
| Browser | `console.error`, failed `fetch`/XHR (5xx or network), a missing image, script or stylesheet | warning |

and every event (old kinds included) carries request context: method, path,
view name, status, timing, query parameter names (values only for harmless keys),
same-site referer, language, user id and staff flag, store version, active theme.
Never stored: cookies, authorization headers, request bodies, secret-looking query
values. The PII scrubber already applied to messages and traces still runs.

Throttle: one row per fingerprint per minute per process, as the log handler does,
so a crawler walking 10,000 broken URLs cannot flood the table.

## Resolving

`ErrorGroup` (one row per fingerprint, created on first decision) records
`resolved` with who and when. The list shows open groups by default; a resolved
group that fires again after its resolution is open again ("regressed").

## Handing errors to Claude Code

* **Copy for Claude Code** on the error log page: one Markdown report of the open
  groups in the window, newest first, each with counts, first/last seen, paths,
  the latest full traceback, request context, and what to do (reproduce, fix in
  the repository with a test, mark resolved). Also downloadable (`.md`, `.json`).
* `python manage.py errors_report [--days N] [--json] [--include-resolved]` prints
  the same report, so Claude Code with shell access runs it in the store's
  container: `docker exec <web> python manage.py errors_report`.
* `python manage.py errors_report --resolve <fingerprint>` marks a group resolved.
* Agent tools `errors.recent` and `errors.get` (scope `diagnostics.read`, read
  only) give Janus in Developer mode and external agents the same view.

## Checks

Tests in `core/errors/tests/`: switch and expiry, log-level gating, request
capture only while on, broken-link and slow-response rules, throttle, redaction,
report content, command, resolve and regress, agent tool registration and scope,
the capture-script flag.
