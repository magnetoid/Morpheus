---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/notifications_center/services.py

Symbols in `plugins/installed/notifications_center/services.py`.

- L21 `notify(*, user, kind: str, title: str, body: str='', action_url: str='', icon: str='bell')` (function) — Create a notification for a single staff user.
- L46 `notify_all_staff(*, kind: str, title: str, body: str='', action_url: str='', icon: str='bell')` (function) — Fan out to every staff user. Returns the count actually written.
- L68 `unread_count_for(user)` (function)
- L78 `latest_for(user, *, limit: int=10)` (function) — Latest N notifications for a user, newest first. Used by the
