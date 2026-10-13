# Errors and logging review (2026-10-13)

Owner, 2026-10-13: improve the error and logging system where it can be improved, then analyse
the error logs across Morpheus and Janus and report how to fix things permanently.

## What was read

- The error log (`core.errors`, `ErrorEvent` + `ErrorGroup`) on all four stores, last 30 days.
- Container logs (web, worker, beat) on all four stores.
- Janus/Linda turns and background Worker runs (`AgentRun`), last 30 days.
- Nightly backups (worker volume), health checks, the audit trail.

## Numbers

| Store | Events (30 d) | Groups | Open before this release | Events since Oct 1 |
|---|---|---|---|---|
| dotbooks | 91 | 38 | 30 | 9 |
| Supernatural | 4,860 | 37 | 31 | 12 |
| Montenegro | 454 | 55 | 51 | 89 (mostly browser) |
| Irving | 53 | 11 | 1 | 53 |

97% of all events come from two template bugs on Supernatural that stopped on September 22.
Since October 1 the stores are close to quiet. The open list did not show that: 113 of 141 groups
were still "open" weeks after their last event, because nothing ever closed a group.

## Broken now

1. **AI provider balance is empty** on dotbooks and Supernatural (DeepSeek answers 402
   "Insufficient Balance" every day). Montenegro also runs DeepSeek. Linda had **no turns at all**
   in 30 days on dotbooks, Supernatural and Montenegro. *Owner: top up, or pick another provider
   on Settings → AI.*
2. **Irving has no SMTP.** The nightly health check fails every day, and Irving's emails
   (sign-in codes, orders) are written to the log, not sent. *Owner: SMTP on Settings →
   Notifications.*
3. **Background Worker runs fail** 9 of 21 times: the AI operator's 45-second limit, and the step
   limit (DeepSeek on Supernatural, Opus on Montenegro). *Code: run operator workflows on Celery
   without the request-sized limit, and give the step budget to the job's size.*
4. **A cross-origin script throws on Montenegro's Serbian booking pages** (74 events, "Script
   error."). The browser hides which script. *Code: load third-party scripts with
   `crossorigin="anonymous"` so the next one is readable; the opaque event is now dropped.*
5. **`django-fsm` is unmaintained** (warns at every boot; it moved into `viewflow.fsm`). Orders use
   it for their state machine. *Code: migrate in its own change, with the order tests.*

## Fixed in this release

- **Secrets never reach the error log.** Only emails, phones and IPs were scrubbed, so a provider
  error quoting a key, an `Authorization` header in a traceback, a Linda turn token (`lt1.…`) or a
  database URL with its password was stored as is and could go out in the daily digest. They are
  removed before anything is stored (`core/errors/services.py:redact_secrets`), including the log
  line the log handler copies into an event.
- **A Janus turn that gives no reply is an ERROR.** Timeouts, crashes, a failed spawn and an
  unusable home were WARNINGs, which the error log keeps only while detailed capture is on, so the
  merchant saw "no reply" and the owner saw nothing.
- **Stale groups close themselves.** The nightly prune resolves a group with no event for 14 days
  ("Resolved automatically"); if it comes back, the page shows it as regressed. The open list is
  now what is broken now.
- **Browser noise.** Chrome's "Transition was skipped" and the opaque "Script error." are dropped,
  in the browser and on the server, like the other page-transition aborts.
- **Boot and request noise.** gunicorn no longer tries to open a control socket in the root-owned
  `/app` (an ERROR at every boot); Django's warning about the registry's by-design database read at
  startup is filtered; the storefront policy allows the service worker's Google Fonts fetches; the
  analytics beacon answers 204 without a body (gunicorn dropped it and warned on every hit).
- Earlier today: one-group-per-day for the same provider error (v0.102.0, verified on real data);
  Pulse's 1,145 duplicate insights (v0.106.0).

## Already fixed, now closed by the nightly job

All last seen in September: Supernatural's product-page template errors (4,731, a facet read
`.name` on a string), Montenegro's journal page (`TemplateSyntaxError`, an unloaded filter), journal
`published_at` lookups, `nav_destinations`, the backup permission error (fixed September 27),
one burst of "too many clients" on Postgres, the SEO scan `FieldError`, the site audit hitting its
time limit.

## Permanent improvements (in order)

1. **Owner, no code:** AI balances and Irving's SMTP (above). These are the only user-visible
   failures today.
2. **Backups off the server.** Nightly backups work on all four stores (dotbooks 1.4 GB a day), but
   every copy sits on the same host as the stores. One disk or one compromise loses the shops and
   the backups together. Copy each night's file to object storage (S3, R2 or B2), keep 30 days there.
3. **Logs that survive a deploy.** Docker keeps logs per container, and every deploy replaces the
   containers, so anything only printed (not in the error log) is gone within hours. Either ship
   container logs to a store (Vector → Loki, Axiom or Better Stack), or keep the rule this release
   follows: anything that matters is an ERROR and lands in the error log.
4. **Spike alerts.** The digest is daily. Add an immediate email when a new group passes N events in
   an hour, so a broken page is known in minutes, not the next morning (Supernatural's template
   errors ran 3,000+ times before anyone looked).
5. **Catch template-variable bugs before deploy.** The largest error class was templates reading an
   attribute on data of the wrong shape (`VariableDoesNotExist`). Run the storefront and theme
   suites with a strict template setting that fails on an unresolved variable.
6. **Worker limits** (above, item 3 of "Broken now").
7. **`django-fsm` → `viewflow.fsm`** (above, item 5).
8. **Janus's own log.** When a turn fails, attach the tail of the Janus home's error log to the
   error event, so a crash says why without a shell on the server.
