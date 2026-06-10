---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/crm/inbox.py

Symbols in `plugins/installed/crm/inbox.py`.

- L34 `_normalise_subject(subj: str)` (function) — Strip Re:/Fwd: prefixes, lowercase, collapse whitespace.
- L45 `_thread_key(subject: str, counterparty_email: str)` (function)
- L49 `_match_customer(email_address: str)` (function)
- L59 `_decode_payload(part)` (function)
- L70 `_extract_bodies(msg: email.message.Message)` (function)
- L92 `fetch_account(account, *, max_messages: int=200)` (function) — Pull new messages for one MailAccount via IMAP. Returns count imported.
- L194 `send_message(account, *, to: Iterable[str], subject: str, body_text: str, body_html: str='', cc: Iterable[str] | None=None, in_reply_to: str='', customer=None)` (function) — Send an email and persist a MailMessage(direction='out').
- L260 `fetch_all_active(*, max_per_account: int=200)` (function) — Poll every active mail account once. Returns {label: count}.
