---
summary: Publishes a TikTok catalog feed, runs the TikTok Pixel and Events API, and manages TikTok Ads campaigns.
---

## What it's for
TikTok Commerce builds your product catalog into a feed for TikTok's Catalog Manager, runs the TikTok Pixel plus a matching server-side Events API so purchases and cart activity are tracked even when a shopper blocks the pixel, and lets you create, pause and report on TikTok Ads campaigns. It's for whoever manages your TikTok shopping and ads.

## Set it up
Turn on [](field:tiktok_commerce.enabled) to publish the feed, shown on [TikTok Commerce](page:overview), and add that URL as a data feed in TikTok Catalog Manager. Add an access token, your [](field:tiktok_commerce.advertiser_id), [](field:tiktok_commerce.catalog_id) and [](field:tiktok_commerce.pixel_code) on [TikTok Commerce](settings:tiktok_commerce). Turn on [](field:tiktok_commerce.pixel_enabled) to fire the pixel on the storefront.

## Common tasks
- Rebuild the feed after changing settings, instead of waiting for the automatic refresh
- Check TikTok's live catalog review status and top reject reasons
- Create a new campaign — it's created paused, so you finish setup in TikTok Ads Manager before it spends
- Pause or enable a campaign, and check spend, clicks and conversions for the last 7, 14 or 30 days

## Good to know
The feed itself needs no credentials; the pixel, its server-side events and Ads all need the access token. The pixel and its matching server-side events only fire when the shopper has agreed to marketing tracking. Linda can check feed coverage, get the feed URL, read catalog diagnostics and the Ads report, but cannot create or change a campaign herself.
