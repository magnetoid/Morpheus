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
- See what shoppers searched for, what found nothing and what they searched before ordering on [Search terms](page:search-terms)
- Watch the storefront live on [Real-time](page:realtime)
- See where shoppers drop out of buying on [Funnel](page:funnel)
- Check what share of one week's customers still buy weeks later on [Cohorts](page:cohorts)
- Compare ad spend to revenue under different attribution models on [Attribution](page:attribution)
- Export the traffic summary and top products as CSV or JSON

## Good to know
- A visit is one visitor's pages with no 30-minute gap. A visitor is someone who allowed analytics cookies, or the day's key for one who didn't when cookieless counting is on.
- A visit is filed under its first page: its link's tags, else the site that sent it, so a visitor who came from Facebook, then Google, counts once under each. Older visits show as Not known.
- Each page is counted by the visitor's browser, so cached pages count too; crawlers never do.
- Days follow your store's time zone; today's numbers are at most an hour old.
- Conversion rate is counted visitors' purchases over their visits, so it can't pass 100%; an order and its payment belong to the visit that placed it.
- Orders and revenue are the store's sales: placed, not cancelled, after refunds.
- Purchases, checkouts, sign-ups and logins come only from the store's own events, never the browser.
- The dashboard home shows visits, conversion rate and AI referrals for the period you pick; a nightly check flags unusual swings.
