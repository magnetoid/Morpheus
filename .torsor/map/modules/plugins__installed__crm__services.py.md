---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/crm/services.py

Symbols in `plugins/installed/crm/services.py`.

- L15 `upsert_lead(*, email: str, first_name: str='', last_name: str='', phone: str='', company: str='', source: str='other', metadata: Optional[dict[str, Any]]=None)` (function) — Idempotent lead create-or-update by email.
- L40 `convert_lead(*, lead, customer)` (function) — Mark a lead as converted to a customer.
- L50 `log_interaction(*, subject, kind: str, summary: str='', body: str='', direction: str='internal', actor=None, actor_name: str='', occurred_at=None, metadata: Optional[dict[str, Any]]=None)` (function) — Append an interaction to a subject's timeline.
- L80 `list_open_tasks(*, assignee=None, limit: int=25)` (function)
- L88 `create_followup_task(*, subject, title: str, due_in_hours: int=24, priority: str='normal', assignee=None, description: str='')` (function)
- L111 `advance_deal(*, deal, target_stage: str, actor=None, note: str='')` (function) — Move a deal to the named stage in the same pipeline. Logs an interaction.
- L140 `ensure_default_pipeline()` (function) — Create + return the default pipeline (idempotent).
- L170 `customer_timeline(customer, *, limit: int=50)` (function) — All interactions where the subject is this customer.
