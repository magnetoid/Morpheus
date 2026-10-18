---
summary: Publishes a Pinterest catalog feed, runs the Pinterest Tag and Conversions API, and manages Pinterest Ads.
---

## What it's for
Pinterest Commerce builds your product catalog into a feed for Pinterest Catalogs, runs the Pinterest Tag plus a matching server-side Conversions API so purchases and cart activity are tracked even when a shopper blocks the tag, and lets you create, pause and report on Pinterest Ads campaigns. It's for whoever manages your Pinterest shopping and ads.

## Set it up
Turn on [](field:pinterest_commerce.enabled) to publish the feed, shown on [Pinterest Commerce](page:overview), and add that URL as a data source in Pinterest Catalogs. Add a Bearer access token, your [](field:pinterest_commerce.ad_account_id), [](field:pinterest_commerce.catalog_feed_id) and [](field:pinterest_commerce.tag_id) on [Pinterest Commerce](settings:pinterest_commerce). Turn on [](field:pinterest_commerce.tag_enabled) to fire the tag on the storefront.

## Common tasks
- Rebuild the feed after changing settings, instead of waiting for the automatic refresh
- Check Pinterest's own feed processing status and item-level errors, once your catalog feed ID is set
- Create a campaign, then pause, enable or report on it
- Check spend, clicks and checkouts for the last 7, 14 or 30 days

## Good to know
The feed itself needs no credentials; the tag, its server-side events and Ads all need the access token. Pinterest pulls the feed on its own schedule — this app has no button to push it to Pinterest directly, only to rebuild the file Pinterest fetches. The tag and its matching server-side events only fire when the shopper has agreed to marketing tracking. Linda can check feed coverage, get the feed URL, read Pinterest's processing diagnostics and the Ads report, but cannot create or change a campaign herself.
