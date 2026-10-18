---
summary: Connects to Amazon Advertising to list, create, pause and budget Sponsored Products campaigns, with cached metrics.
---

## What it's for
Amazon Ads connects your store to Amazon Advertising so you can manage Sponsored Products campaigns and see how they're performing, without leaving the dashboard. It's for whoever runs your Amazon advertising. There's no product feed or pixel here — Amazon's own marketplace listing and off-Amazon tracking work differently, so this app only covers the Advertising API side: campaigns and their performance.

## Set it up
Add a Login with Amazon client ID and secret, an OAuth refresh token, your advertising profile ID and region on [Amazon Ads](settings:amazon_ads). Then use Verify connection on [Amazon Ads](page:ads) to check the credentials work.

## Common tasks
- Create a new Sponsored Products campaign — it's created paused, so you finish setup in Amazon Ads before it spends
- Pause or enable an existing campaign
- Change a campaign's daily budget
- Pull the latest cost, clicks, purchases and sales with Refresh metrics

## Good to know
Performance numbers come from Amazon's asynchronous reporting API — click Refresh metrics and check back in about a minute rather than expecting an instant update. The page itself notes that this campaign management is best-effort until it has been checked against a live Amazon Ads account. Linda can list your campaigns and read the cached performance report, but cannot create a campaign, pause one or change a budget herself.
