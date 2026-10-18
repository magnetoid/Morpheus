---
summary: Sends GA4 purchase, cart and browsing events from the server, runs Google Tag Manager, and audits every event.
---

## What it's for
Tracking connects your store to Google Analytics 4 and Google Tag Manager. It fires events like purchases, cart changes, checkout starts, searches, sign-ups and page views both from the server — so ad blockers and browser quirks can't lose them — and from the browser through GTM. Every server-side event is logged so you can see what fired, whether it was sent, deduplicated or failed, and why. It's for whoever manages your analytics and ad conversion tracking.

## Set it up
Open [Tracking](page:overview) and click Settings to add your GA4 measurement ID, API secret and GTM container ID — server-side firing needs the measurement ID and API secret, the GTM script needs the container ID. From there you can also turn individual events on or off, set the default consent state for each Consent Mode signal, turn on sending a hashed customer ID, and set which paths or user agents are never tracked. Separately, add a Google Ads conversion ID and label on [](settings:tracking) to fire a Google Ads conversion on the order confirmation page.

## Common tasks
- Check the last 24 hours' send rate and top events on the main Tracking page
- Fire a test event — purchase, add to cart, search, sign-up and more — to confirm the integration works without placing a real order
- Run a connection check against Google's debug endpoint to validate your measurement ID and API secret without writing to your real reports
- Look up one event's full payload and response in the event log when something looks wrong
- Download a ready-made GTM container to import into your workspace

## Good to know
A visitor's own consent decision controls both the server-side and the client-side events; only a dedicated debug switch can override that, and it is meant for internal testing, never for a live store serving EU consumers. Product-view tracking skips known crawlers, since a server-side hit carries the store's own address and can't otherwise tell a bot from a shopper. Purchases are deduplicated against the client-side hit by transaction ID by default, so a sale firing from both the server and the browser doesn't count twice.
