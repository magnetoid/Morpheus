---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/crm/models.py

Symbols in `plugins/installed/crm/models.py`.

- L31 `Lead` (class) — A pre-customer contact captured from forms, imports, or the agent layer.
- L84 `__str__(self)` (method)
- L88 `display_name(self)` (method)
- L93 `Account` (class) — A B2B company. Optional — only used when `enable_b2b` is on.
- L121 `__str__(self)` (method)
- L125 `Pipeline` (class) — A configurable sales pipeline (set of stages).
- L137 `__str__(self)` (method)
- L141 `PipelineStage` (class) — An ordered stage within a pipeline.
- L156 `__str__(self)` (method)
- L160 `Deal` (class) — An opportunity — typically B2B, but works for retail enterprise sales too.
- L196 `__str__(self)` (method)
- L200 `Interaction` (class) — An event in the relationship history — call, email, note, system log, etc.
- L255 `CrmTask` (class) — A follow-up reminder. Forward-looking (TODO) vs Interaction (DONE).
- L301 `is_open(self)` (method)
- L305 `is_overdue(self)` (method)
- L310 `MailAccount` (class) — An IMAP/SMTP mailbox the merchant connects so support email lands in
- L362 `__str__(self)` (method)
- L366 `MailMessage` (class) — A single email — inbound (fetched via IMAP) or outbound (sent via SMTP).
- L415 `__str__(self)` (method)
- L419 `occurred_at(self)` (method)
- L423 `CustomerNote` (class) — Quick freeform note attached to a customer (separate from Interaction
