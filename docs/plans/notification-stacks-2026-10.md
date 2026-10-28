# Staff notifications: stacks, priority, settings, live bell, snooze (2026-10-28)

Owner's ask: "improve internal notification system, enable stacking and some more
advanced things". Chosen on 2026-10-28: stacking = **group repeats** (not a toast
pile), plus priority + filters, per-person settings, a live bell, snooze + archive.
Everything lives in `plugins/installed/notifications_center/`.

## Model

`Notification` gains (all safe for the release before: NOT NULL columns carry
`db_default`, the rest are nullable):

- `group_key` — `"<kind>:<subject>"` when the sender names what the notification is
  about (a variant, an agent), else `''` (never stacks). Keyed on what produced it,
  never on display text (the Pulse dedupe landmine).
- `count`, `occurrences` (newest first, at most 20 of `{at, title, body}`).
- `level` — `info` | `warning` | `urgent`; a stack keeps its highest level.
- `last_at` — latest activity; lists order by `Coalesce(last_at, created_at)` so rows
  written by the release before still sort.
- `snoozed_until`, `archived_at`.

`NotificationPreference(user, muted_kinds)` — one row per staff member.

## Rules

- `notify(..., level='', subject='')`: a muted kind is not delivered; an open stack
  (same user and `group_key`, unread, not archived) takes the occurrence instead of a
  new row. Reading or archiving closes a stack; the next occurrence starts a new one.
- The inbox is everything not archived and not snoozed into the future. The unread
  count counts stacks in the inbox; `urgent` unread turns the badge red.
- Snooze (1 hour, tomorrow 09:00, next week 09:00 store time) marks the stack unread
  and moves its `last_at` to the wake time, so it comes back at the top.
- Each staff member's own inbox needs no capability: rbac gives `system.read` to admins
  only, which would take an inventory manager's low-stock alerts away under `enforce`.
- Default level per built-in kind lives in `services.KINDS`; senders only add `subject`.

## Surfaces

- List page: Inbox / Unread / Snoozed / Archived, level and kind filters, a stack shows
  `×N` and its occurrences, per-row read / snooze / archive / mute.
- Settings page (`/dashboard/notifications/preferences/`): which kinds you get.
- Bell: `notifications_center/static/notifications_center/bell.js` (the shell only
  includes it while the app is on); polls the unread counts every 30 s while the tab is
  visible; stacks, hover actions.
- Linda: `notifications.list` (scope-less, the asker's own inbox, like `help.*`) and
  `notifications.update` (`system.write`, `requires_approval`: hiding an urgent alert is
  what injected text would try). Both refuse an external agent's conversation.
