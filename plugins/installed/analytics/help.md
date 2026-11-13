---
summary: Tracks visits and where they came from, funnels, cohorts and ad attribution on the storefront, with real-time traffic and anomaly alerts.
---

## What it's for
Analytics tracks what happens on your storefront (visits, pages, product views, searches, carts, checkouts and orders) and turns it into a traffic overview, a real-time view, where each visit came from, a conversion funnel, retention cohorts and ad attribution.

## Set it up
Nothing to connect: tracking starts when the app is on. On [Analytics](settings:analytics) you can choose how many days of raw events to keep, how long to keep a visitor who hasn't come back (13 months by default), and whether to exclude staff visits (on by default) or all logged-in customers (off by default). You can also count visitors who decline cookies (off by default), with a daily key never stored with a customer or order; check with your privacy adviser first.

## Common tasks
- Check sessions, orders, revenue, a 7-day forecast and agent activity on [Traffic](page:overview)
- See where visits came from and what they bought, by channel, source, campaign, landing page, country or device, on [Sources](page:sources)
- See what shoppers searched for, what found nothing (also by region or date) and what they searched before ordering on [Search terms](page:search-terms)
- Watch the storefront live on [Real-time](page:realtime)
- See where shoppers drop out on [Funnel](page:funnel), to an order or, on a travel store, a booking
- Check what share of one week's customers still buy weeks later on [Cohorts](page:cohorts)
- Compare [channels](app:channels) ad spend with order revenue, ROAS and MER on [Attribution](page:attribution), blank without spend
- Export the traffic summary and top products as CSV or JSON

## Good to know
- A visit is one visitor's pages with no 30-minute gap. A visitor is someone who allowed analytics cookies, or the day's key for one who didn't when cookieless counting is on.
- A visit is filed under its first page: its link's tags, else the site that sent it. Older visits show as Not known.
- Cached pages count too; crawlers never do.
- Days follow your store's time zone; today's numbers are at most an hour old.
- Conversion rate is counted visitors' purchases over their visits, so it can't pass 100%; an order and its payment belong to the visit that placed it.
- Orders and revenue are the store's sales: placed, not cancelled, after refunds. Enquiries and bookings are kept as leads and bookings, never sales.
- Purchases, checkouts, sign-ups and logins come only from the store's own events, never the browser.
- The dashboard home shows visits, conversion rate and AI referrals; a nightly check flags unusual swings.
