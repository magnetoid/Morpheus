---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/crm/models.py

Symbols in `plugins/installed/crm/models.py`.

- L33 `Lead` (class) — A pre-customer contact captured from forms, imports, or the agent layer.
- L92 `__str__(self)` (method)
- L96 `display_name(self)` (method)
- L101 `Account` (class) — A B2B company. Optional — only used when `enable_b2b` is on.
- L137 `__str__(self)` (method)
- L141 `Pipeline` (class) — A configurable sales pipeline (set of stages).
- L153 `__str__(self)` (method)
- L157 `PipelineStage` (class) — An ordered stage within a pipeline.
- L172 `__str__(self)` (method)
- L176 `Deal` (class) — An opportunity — typically B2B, but works for retail enterprise sales too.
- L220 `__str__(self)` (method)
- L224 `Interaction` (class) — An event in the relationship history — call, email, note, system log, etc.
- L284 `CrmTask` (class) — A follow-up reminder. Forward-looking (TODO) vs Interaction (DONE).
- L337 `is_open(self)` (method)
- L341 `is_overdue(self)` (method)
- L347 `MailAccount` (class) — An IMAP/SMTP mailbox the merchant connects so support email lands in
- L400 `__str__(self)` (method)
- L404 `MailMessage` (class) — A single email — inbound (fetched via IMAP) or outbound (sent via SMTP).
- L459 `__str__(self)` (method)
- L463 `occurred_at(self)` (method)
- L467 `CustomerNote` (class) — Quick freeform note attached to a customer (separate from Interaction
