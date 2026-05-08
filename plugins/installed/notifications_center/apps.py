"""
notifications_center — staff inbox for "things that happened while
I wasn't looking".

Toast notifications already work for in-flight feedback ("order saved",
"return rejected"). What's missing is the persistent counterpart: when
a customer submits an RMA at 2am, the staff who'll handle it tomorrow
need a way to see the alert in the morning. Email digests are too
noisy; a bell icon with a counter is the Shopify-shaped solution.

The plugin ships:
  • `Notification` model — `(user, kind, title, body, action_url,
    read_at, created_at)`
  • `services.notify(...)` API for plugins to fan out events
  • A bell icon + dropdown in the topbar (rendered via the existing
    template-tag pattern + the nav_badges context value)
  • A full /dashboard/notifications/ page (paginated list,
    mark-as-read, mark-all-read)

Plugins call `from plugins.installed.notifications_center.services
import notify` rather than each owning their own alert plumbing —
keeps the fan-in centralised and makes it easy to add per-user
preferences later (digest cadence, channel toggles, etc.).
"""
