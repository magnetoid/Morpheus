# Edge caching — Cloudflare configuration

Morpheus's storefront responses are already designed to be edge-cacheable:

  - `core/storefront_cache.py` middleware sets `Cache-Control: public,
    max-age=N, s-maxage=N` on anonymous GET responses to storefront
    pages (PDP, PLP, home, journal, content).
  - Authenticated and cart-bearing responses are explicitly marked
    `private, no-cache` so they never hit the edge.
  - The CDN allow-list in `core/security_headers.py` permits Cloudflare
    asset hosts for fonts/JS that the storefront uses.

To unlock the actual edge savings — sub-30ms TTFB at p95 and a 95%+
cache hit-rate on the public storefront — configure Cloudflare as
follows. None of these settings change Morpheus's behaviour; they're
all CDN-side knobs.

## 1. Cache rules (Cloudflare Dashboard → Caching → Cache rules)

Create three rules in this order. **Stop at first match.**

### Rule 1 — skip cache on sensitive paths
- **When incoming requests match:** URI Path *contains* one of
  `/cart`, `/checkout`, `/account`, `/auth`, `/dashboard`, `/admin`,
  `/api/`, `/mcp/`, `/graphql`, `/_/`, `/post-purchase/nps/`.
- **Then:** Bypass cache.

### Rule 2 — cache static assets aggressively
- **When:** URI Path *starts with* one of `/static/`, `/media/`.
- **Then:** Cache eligibility = Eligible. Edge TTL = 1 month.
  Browser TTL = 1 day. Cache key includes the query string.

### Rule 3 — cache HTML pages with origin TTL respected
- **When:** none of the above matched AND request method = GET.
- **Then:** Cache eligibility = Eligible. Edge TTL = Use Cache-Control
  header. Browser TTL = Use Cache-Control header. Cache key:
  default + `Origin` header (so the same URL doesn't bleed across
  storefronts on multi-domain installs).

## 2. Always Online (Settings → Caching)

- Turn **Always Online** on. When the origin is down, Cloudflare
  serves the last successful cached HTML and the SW falls back to
  `/offline/` for uncached pages.

## 3. Tiered Cache (Settings → Caching)

- Turn **Tiered Cache** on. Multi-PoP fan-out reduces origin load
  by 60%+ on a global catalog.

## 4. Polish + Mirage (Speed → Optimization)

- **Polish:** Lossless or Lossy depending on whether you care more about
  byte savings than perfect fidelity. Lossy is usually fine.
- **Mirage:** Off. Conflicts with our AVIF rollout and the
  `loading="lazy"` attributes the templates already emit.

## 5. Argo Smart Routing (paid)

- If conversion-per-millisecond matters more than Cloudflare's cost
  per gigabyte, turn Argo on. Median latency drop ~30%.

## 6. Workers (optional — for "personalised holes")

When you want personalised UI bits (cart count, user name) on
otherwise-cached pages, deploy a Cloudflare Worker that:

  1. Serves the cached HTML.
  2. Injects a `<script>` that calls `/api/cart/count` and
     `/api/me/short` — both already CSRF-exempt JSON endpoints.
  3. Sets `s-maxage=300` so edge caches stay warm.

See `core/storefront_cache.py` for the Cache-Control headers
currently emitted; tweak there if you want longer / shorter edge TTLs.

## Verification

```bash
# Public PDP: should be cached
curl -I https://dotbooks.store/products/peter-pan/ | grep -i 'cf-cache-status\|cache-control'
# Cart: should never be cached
curl -I https://dotbooks.store/cart/ | grep -i 'cf-cache-status\|cache-control'
# Static asset: cf-cache-status HIT after second request
for _ in 1 2; do
  curl -sI https://dotbooks.store/static/css/storefront.css | grep -i 'cf-cache-status'
done
```

`cf-cache-status` reports HIT, MISS, EXPIRED, BYPASS, or DYNAMIC.
- HIT = served from edge ✅
- BYPASS = the rule above matched ✅
- DYNAMIC = no caching rule matched; check your rule order.
