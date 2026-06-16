---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/crm/inbox.py

Symbols in `plugins/installed/crm/inbox.py`.

- L35 `_normalise_subject(subj: str)` (function) — Strip Re:/Fwd: prefixes, lowercase, collapse whitespace.
- L46 `_thread_key(subject: str, counterparty_email: str)` (function)
- L50 `_match_customer(email_address: str)` (function)
- L60 `_decode_payload(part)` (function)
- L71 `_extract_bodies(msg: email.message.Message)` (function)
- L93 `fetch_account(account, *, max_messages: int=200)` (function) — Pull new messages for one MailAccount via IMAP. Returns count imported.
- L195 `send_message(account, *, to: Iterable[str], subject: str, body_text: str, body_html: str='', cc: Iterable[str] | None=None, in_reply_to: str='', customer=None)` (function) — Send an email and persist a MailMessage(direction='out').
- L262 `fetch_all_active(*, max_per_account: int=200)` (function) — Poll every active mail account once. Returns {label: count}.
