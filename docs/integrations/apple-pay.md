# Apple Pay — domain verification + go-live

Apple Pay via Stripe Express Checkout is already wired into the
storefront (`automatic_payment_methods={'enabled': True}` on
PaymentIntent creation). What remains is a one-time Apple **domain
verification** — without it, Safari hides the wallet button even when
the customer has a card on file.

## Steps (one time per storefront domain)

1. **Register the domain in Stripe Dashboard**
   - Stripe Dashboard → Settings → Payment methods → Apple Pay → registered domains.
   - Click "Add a new domain" and enter the exact storefront hostname
     (e.g. `dotbooks.store`, no protocol, no trailing slash).
   - Stripe returns a verification file. Save its raw bytes.

2. **Serve the verification file** at
   `https://<host>/.well-known/apple-developer-merchantid-domain-association`.
   - Content-Type must be `text/plain` and body must match Stripe's
     download byte-for-byte (no BOM, no trailing newline added).
   - Easiest: drop the file into `static/.well-known/` and serve via
     Whitenoise.

3. **Trigger Stripe to verify**
   - Back in the Stripe Dashboard, click "Verify" next to the domain.
   - Status flips to "Verified" within 30 seconds. If it 404s, the
     file isn't reachable — curl it from outside the network to confirm.

4. **Confirm in Safari**
   - Open the storefront in Safari 14+ on macOS Big Sur or iOS 14.5+.
   - On the checkout page, the Apple Pay wallet button must appear
     in the Express Checkout Element row.
   - If still missing: open Web Inspector → Console; Stripe.js logs
     the exact reason. Most common: the domain in the Stripe Dashboard
     doesn't match the one Safari was loaded under (e.g. www vs apex).

## Multi-domain checklist

For every storefront domain (including www / apex variants if both
serve traffic):

- [ ] dotbooks.store
- [ ] www.dotbooks.store (if non-redirected)
- [ ] Staging domain (separate Stripe test-mode verification)

## CSP note

`core/security_headers.py` already allows `https://js.stripe.com` and
`https://hooks.stripe.com` in `script-src` / `frame-src`. No changes
needed for Apple Pay specifically.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Wallet button never appears in Safari | Domain not verified — repeat step 3. |
| Appears in Stripe Elements preview but not on storefront | CSP blocks Stripe iframe — check console for csp_violation. |
| Verification download 404 | Whitenoise path mismatch — ensure file is in `static/.well-known/`. |
| Stripe returns "domain mismatch" on verify | The Stripe Dashboard domain entry doesn't match. Add both apex and www. |

## Related

- [Web Payments docs (Stripe)](https://docs.stripe.com/apple-pay)
- [Apple Pay JS — domain verification](https://developer.apple.com/documentation/apple_pay_on_the_web/setting_up_your_server)
