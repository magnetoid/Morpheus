---
summary: Publishes a Meta catalog feed, runs the Pixel and Conversions API, manages Meta Ads and syncs retargeting audiences.
---

## What it's for
Meta Commerce builds your product catalog into a feed for Meta's Commerce Manager, can push the same data straight to Meta through the Catalog API once connected, runs the Meta Pixel plus a matching server-side Conversions API so purchases are tracked even when a shopper blocks the pixel, and lets you create, pause and report on Meta Ads campaigns. It's for whoever manages your Facebook and Instagram shopping and ads.

## Set it up
Turn on [](field:meta_commerce.enabled) to publish the feed, shown on [Meta Commerce](page:overview), and add that URL as a data source in Commerce Manager. Add a System User access token from Business Settings, your [](field:meta_commerce.catalog_id), [](field:meta_commerce.ad_account_id) and [](field:meta_commerce.pixel_id) on [Meta Commerce](settings:meta_commerce). Turn on [](field:meta_commerce.pixel_enabled) to fire the pixel on the storefront.

## Common tasks
- Rebuild the feed after changing settings, instead of waiting for the automatic refresh
- Push products to Meta's catalog directly, once connected
- Check Meta's live review status and item-level issues for your catalog
- Create a catalog ad campaign, then pause, enable or report on it
- Sync your customers — all of them, or just purchasers — to a Meta Custom Audience for retargeting

## Good to know
The feed itself needs no credentials; the catalog push, pixel, Conversions API and Ads all need the access token. The pixel and the matching server-side events only fire when the shopper has agreed to marketing tracking. Syncing a customer audience always needs your own go-ahead, whether you click it on the dashboard or ask Linda, since it uploads hashed emails to Meta. Linda can check feed coverage, rebuild the feed, read catalog diagnostics and the Ads report, and sync an audience with your approval, but cannot create or change an ad campaign herself.
