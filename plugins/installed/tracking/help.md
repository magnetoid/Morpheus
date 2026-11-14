---
summary: Runs Google Analytics 4 or Tag Manager on every page, sends purchase and cart events from the server, and audits every event.
---

## What it's for
Tracking connects your store to Google Analytics 4 and Google Tag Manager. In the shopper's browser it loads your GTM container, or GA4 itself when you have no container, on every page. From the server it sends purchases, refunds, cart changes, checkout starts, searches, sign-ups and sign-ins, joined to the browser's visit, so ad blockers can't lose them; each is logged. A travel store's enquiries go as leads, its confirmed bookings as purchases.

## Set it up
Open [Tracking](page:overview) and click Settings:
- Add your GA4 measurement ID and API secret. The ID alone puts GA4 on every page; the API secret lets the server send events too.
- Add a GTM container ID if you run GA4 through Tag Manager. Leave it blank and GA4 loads directly.
- The other tabs switch events, set Consent Mode defaults, send a hashed ID for signed-in shoppers, list other domains a visit can cross, and exclude paths or user agents.

Fill in the Google Ads card on the Connection tab to fire a conversion on the order confirmation page.

## Common tasks
- Check the last 24 hours' send rate and top events on the main Tracking page
- Fire a test event, such as a purchase, without placing a real order
- Look up one event's full payload and response in the event log
- Download a ready-made GTM container to import into your workspace

## Good to know
- The visitor's consent decides both the browser tags and the server events: tags load once analytics is allowed, then tell Google what was chosen. Only the debug switch overrides that, and never on a live store serving EU consumers.
- Product views come from the browser's tag when there is one, else from the server, skipping known crawlers.
- Searches send the words the shopper typed; one made with filters alone sends none.
- Purchases go out from both the browser and the server with the same transaction ID, which GA4 uses to count each order once.
- An enquiry or booking goes once: from the guest's next page when a tag is set up, else from the server; one confirmed later, from the server if the guest's visit was noted on it.
- Debug mode shows server events in GA4's DebugView; turn it off afterwards.
- Scrolls, outbound clicks, downloads and video plays are switched in GA4 (Enhanced Measurement).
- Cross-domain measurement needs the same domain list in GA4 → Admin → Data streams → Configure your domains.
