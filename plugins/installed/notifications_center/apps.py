"""
notifications_center — staff inbox for "things that happened while
I wasn't looking".

Toast notifications already work for in-flight feedback ("order saved",
"return rejected"). What's missing is the persistent counterpart: when
a customer submits an RMA at 2am, the staff who'll handle it tomorrow
need a way to see the alert in the morning. Email digests are too
noisy; a bell icon with a counter is the Shopify-shaped solution.

The plugin ships:
  • `Notification` model — one row per stack of repeats, with a level
    (info / warning / urgent), snooze and archive; `NotificationPreference`
    holds the kinds each staff member muted
  • `services.notify(...)` API for plugins to fan out events (`subject=`
    makes repeats stack)
  • The topbar bell's script (static/notifications_center/bell.js), which
    the shell includes only while the app is on
  • A full /dashboard/notifications/ page (inbox, unread, snoozed,
    archived; level and kind filters) and a settings page

Plugins call `from plugins.installed.notifications_center.services
import notify` rather than each owning their own alert plumbing —
keeps the fan-in centralised: muted kinds, stacking and each kind's
default level are decided in one place.
"""
