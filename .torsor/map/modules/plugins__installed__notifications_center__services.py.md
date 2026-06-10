---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/notifications_center/services.py

Symbols in `plugins/installed/notifications_center/services.py`.

- L20 `notify(*, user, kind: str, title: str, body: str='', action_url: str='', icon: str='bell')` (function) — Create a notification for a single staff user.
- L41 `notify_all_staff(*, kind: str, title: str, body: str='', action_url: str='', icon: str='bell')` (function) — Fan out to every staff user. Returns the count actually written.
- L60 `unread_count_for(user)` (function)
- L70 `latest_for(user, *, limit: int=10)` (function) — Latest N notifications for a user, newest first. Used by the
