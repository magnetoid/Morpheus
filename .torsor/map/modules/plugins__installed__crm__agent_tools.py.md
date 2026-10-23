---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/crm/agent_tools.py

Symbols in `plugins/installed/crm/agent_tools.py`.

- L24 `find_leads_tool(*, query: str='', status: str='', limit: int=20)` (function)
- L73 `create_lead_tool(*, email: str, first_name: str='', last_name: str='', company: str='', phone: str='', source: str='agent')` (function)
- L114 `log_interaction_tool(*, email: str, kind: str, summary: str, body: str='', direction: str='internal')` (function)
- L159 `list_open_tasks_tool(*, assignee_email: str='', limit: int=25)` (function)
- L201 `advance_deal_tool(*, deal_id: str, stage: str, note: str='')` (function)
- L229 `customer_timeline_tool(*, email: str, limit: int=30)` (function)
- L269 `crm_support_threads_tool(*, status: str='open', limit: int=20)` (function)
- L309 `crm_reply_support_tool(*, thread_id: str, message: str, close: bool=False)` (function)
