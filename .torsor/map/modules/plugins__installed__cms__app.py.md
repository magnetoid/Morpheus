---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/cms/app.py

Symbols in `plugins/installed/cms/app.py`.

- L14 `CmsPlugin` (class)
- L26 `ready(self)` (method)
- L66 `on_storefront_page_intro(self, value, page=None, **kwargs)` (method) — Supply the intro copy for a built-in storefront listing page.
- L91 `on_email_template_override(self, value, key=None, ctx=None, **kwargs)` (method) — Supply merchant-edited copy for a transactional email.
- L127 `on_form_submitted(self, form, submission, **kwargs)` (method) — Bridge to CRM if installed: form submission → Lead + Interaction.
- L147 `contribute_agent_tools(self)` (method)
- L176 `contribute_dashboard_pages(self)` (method)
