---
summary: Runs Google Analytics 4 or Tag Manager on every page, sends purchase and cart events from the server, and audits every event.
---

## What it's for
Tracking connects your store to Google Analytics 4 and Google Tag Manager. In the shopper's browser it loads your GTM container, or GA4 itself when you have no container, on every page. From the server it sends purchases, refunds, cart changes, checkout starts, searches, sign-ups and sign-ins, joined to the same visit as the browser's events, so ad blockers can't lose them. Every server-side event is logged with whether it was sent, deduplicated or failed, and why.

## Set it up
Open [Tracking](page:overview) and click Settings:
- Add your GA4 measurement ID and API secret. The ID alone puts GA4 on every page; the API secret lets the server send events too.
- Add a GTM container ID if you run GA4 through Tag Manager. Leave it blank and GA4 loads directly.
- The other tabs turn events on or off, set each Consent Mode default, send a hashed customer ID for signed-in shoppers, list other domains a visit can cross, and exclude paths or user agents.

Separately, add a Google Ads conversion ID and label on [](settings:tracking) to fire a Google Ads conversion on the order confirmation page.

## Common tasks
- Check the last 24 hours' send rate and top events on the main Tracking page
- Fire a test event, such as a purchase or a search, without placing a real order
- Run a connection check that validates your measurement ID and API secret without touching your reports
- Look up one event's full payload and response in the event log when something looks wrong
- Download a ready-made GTM container to import into your workspace

## Good to know
- The visitor's consent decides both the browser tags and the server events: tags load once analytics is allowed, then tell Google what was chosen. Only the debug switch overrides that, and never on a live store serving EU consumers.
- Product views come from the browser's tag when one is set up, so none counts twice; otherwise the server sends them, skipping known crawlers.
- Purchases go out from both the browser and the server with the same transaction ID, which GA4 uses to count each order once.
- Debug mode marks server-side events so they show in GA4's DebugView. Turn it off once you've checked them.
- Scrolls, outbound clicks, downloads and video plays are switched in GA4 itself (Enhanced Measurement).
- Cross-domain measurement needs the same domain list in GA4 → Admin → Data streams → Configure your domains.
