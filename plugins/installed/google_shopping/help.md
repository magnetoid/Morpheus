---
summary: Publishes a Google Merchant Center product feed and runs Shopping ads, remarketing and Content API sync.
---

## What it's for
Google Shopping builds your product catalog into a feed for Google Merchant Center, can push the same data straight to Google through the Content API once connected, runs the Google Ads dynamic remarketing tag on the storefront, and lets you create, pause and report on Google Ads Shopping campaigns. It's for whoever manages your Google Shopping listings and ads.

## Set it up
Turn on [](field:google_shopping.enabled) to publish the feed, shown on [Google Shopping](page:overview), and submit that URL in Merchant Center. For the Content API push, Merchant diagnostics and Google Ads, add an OAuth client ID and secret on [Google Shopping feed](settings:google_shopping), then use Connect with Google on the same page to grant access in one step. To run remarketing, set [](field:google_shopping.remarketing_id) and turn on [](field:google_shopping.remarketing_enabled).

## Common tasks
- Rebuild the feed after changing settings, instead of waiting for the automatic refresh
- Push products to Merchant Center directly with Push now, once connected
- Check Merchant Center's live approval status and item-level issues
- Check which active products are missing a GTIN, brand or category
- Create a Google Ads Shopping campaign, then pause, enable or report on it

## Good to know
The feed itself needs no credentials; only the Content API push, Merchant diagnostics and Google Ads need Google connected. Turning the feed off makes its URL answer not found. The remarketing tag obeys the same marketing consent as the rest of the storefront's ad tags. Linda can check feed coverage, rebuild the feed, and read Merchant diagnostics and the Ads report, but cannot create or change a Google Ads campaign herself.
