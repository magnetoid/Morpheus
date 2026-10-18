---
summary: Publishes a Bing Merchant Center feed, the UET conversion tag, and Microsoft Advertising campaign management.
---

## What it's for
Microsoft / Bing Commerce publishes your product catalog as a feed for Microsoft Merchant Center, adds the UET tag that tracks visits and purchases for Microsoft Advertising, and lets you create, pause and monitor Microsoft Advertising campaigns from the dashboard. It's for whoever runs your Bing Shopping listings and ads.

## Set it up
Turn on [](field:microsoft_commerce.enabled) to publish the feed, shown on [Microsoft / Bing](page:overview), then add it as a scheduled feed URL in Microsoft Merchant Center. Add your [](field:microsoft_commerce.uet_tag_id) and turn on [](field:microsoft_commerce.uet_enabled) for conversion tracking. For campaign management, add an OAuth client ID and secret, a refresh token, a developer token, your customer ID and account ID on [Microsoft / Bing Commerce](settings:microsoft_commerce).

## Common tasks
- Rebuild the feed after changing settings, instead of waiting for the automatic refresh
- Check catalog-eligible product coverage and which attributes are missing
- Create a new Shopping campaign — it's created paused, so you finish setup in Microsoft Advertising before it spends
- Pause or enable a campaign, and pull its latest spend, clicks, conversions and revenue with Refresh metrics

## Good to know
The Merchant Center feed works with no credentials — only campaign management and the UET tag need them. Performance metrics come from Microsoft's asynchronous reporting, fetched in the background; click Refresh metrics and check back in about a minute. Both campaign management and its reporting are best-effort until checked against a live Microsoft Advertising account. Turning the feed off makes its URL answer not found. Linda can check feed coverage, get the feed URL and list campaigns, but cannot create, pause or change a campaign herself.
