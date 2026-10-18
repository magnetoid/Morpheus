---
summary: Connects your store to Cloudflare so cached pages clear automatically when you edit a product, plus DNS, firewall and bot protection.
---

## What it's for

This app connects your store to your Cloudflare account so the parts of your site Cloudflare caches get cleared automatically whenever you edit a product or a category, instead of showing an old version until the cache expires. From the same screens you can also look at a domain's traffic, change its security and performance settings, see recent firewall activity, manage its DNS records, and purge its cache by hand when you need to.

## Set it up

Add your Cloudflare account on the [Cloudflare](page:overview) page using an API token with cache-purge and DNS permissions, then sync it to pull in its domains. To protect the affiliate application form from bots, turn on [](field:cloudflare.turnstile_enabled) and paste in the site key and secret key from your Cloudflare Turnstile widget.

## Common tasks

- Sync a connected account to pull in its latest domains.
- Open a domain to see its traffic, security and cache settings, or change one.
- Purge a domain's cache by URL, by file, or entirely.
- Look at a domain's recent firewall activity.
- Check or edit a domain's DNS records.

## Good to know

A domain's cache is purged for you when a product or category it was built from changes, or when another app changes a page's address or search listing — you rarely need to purge by hand. Turnstile currently protects only the affiliate application form, not other public forms. Changing a domain's settings here changes them on Cloudflare itself, live.
