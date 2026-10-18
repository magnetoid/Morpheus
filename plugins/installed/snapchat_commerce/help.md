---
summary: Publishes a Snapchat catalog feed for Dynamic Ads, runs the Snap Pixel and Conversions API, and manages Snapchat Ads.
---

## What it's for
Snapchat Commerce builds your product catalog into a feed for Snapchat's Catalog Manager (used by Dynamic Ads), runs the Snap Pixel plus a matching server-side Conversions API so purchases are tracked even when a shopper blocks the pixel, and lets you create, pause and report on Snapchat Ads campaigns. It's for whoever manages your Snapchat shopping and ads.

## Set it up
Turn on [](field:snapchat_commerce.enabled) to publish the feed, shown on [Snapchat Commerce](page:overview), and add that URL as a product feed in Snapchat Catalog Manager. Add an OAuth refresh token, your [](field:snapchat_commerce.ad_account_id) and [](field:snapchat_commerce.pixel_id) on [Snapchat Commerce](settings:snapchat_commerce). Turn on [](field:snapchat_commerce.pixel_enabled) to fire the pixel on the storefront.

## Common tasks
- Rebuild the feed after changing settings, instead of waiting for the automatic refresh
- Verify the connection to Snapchat is working
- Create a new campaign — it's created paused, so you finish setup in Snapchat Ads Manager before it spends
- Pause or enable a campaign, and check spend, swipes and conversions for the last 7, 14 or 30 days

## Good to know
The feed itself needs no credentials; the pixel, its server-side events and Ads all need the OAuth connection. The pixel and its matching server-side events only fire when the shopper has agreed to marketing tracking. Linda can check feed coverage, get the feed URL and read the Ads report, but cannot create or change a campaign herself.
