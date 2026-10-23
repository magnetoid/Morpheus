---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/assistant/reports.py

Symbols in `core/assistant/reports.py`.

- L21 `_clean(text, limit: int)` (function)
- L25 `file_report(*, title, problem, fix='', area='', user=None, conversation_key='')` (function) — Record a report, or refresh the open one with the same title.
- L52 `issue_body(report)` (function) — The issue text: the reviewed report, with emails, phones and IPs hashed.
- L73 `issue_url(report)` (function) — GitHub's new-issue form for this report, pre-filled.
- L83 `mark_sent(report, user)` (function)
