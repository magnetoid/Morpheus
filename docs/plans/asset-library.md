# Asset library (media plugin) — enhancements

The "asset page" is the **media plugin library**:
[`plugins/installed/media/templates/media/library.html`](../plugins/installed/media/templates/media/library.html)
backed by [`plugins/installed/media/views.py`](../plugins/installed/media/views.py)
(`_federated_assets()` unions `MediaAsset` + `ProductImage` + `Product.digital_file`).
Routes in `plugins/installed/media/urls.py`. Asset edit page:
`media/templates/media/edit_meta.html` + `views.edit_meta`.

## Requests (2026-06-02)

1. **DONE — book covers no longer cropped.** `library.html:111` was
   `object-fit: cover` on a 1:1 box (cropped tall covers) → now
   `object-fit: contain; padding: 6px` (full cover, letterboxed).

2. **DONE — Upload + Download buttons.** Library tiles now carry a download
   button (`<a download>` overlay, top-right); the digital-products tab gained a
   styled `.btn` Download per row. Admin context downloads the raw file URL
   directly (staff-only page) — the *customer* tokened path in `digital_products`
   is untouched.

3. **DONE (verified) — all uploads appear.** `_federated_assets` unions
   MediaAsset + ProductImage + Product.digital_file across the tabs; `_build_tabs`
   counts include the federated rows. No source was siloed, so no widening needed.

4. **DONE — click an asset → inline SEO modal.** Native library assets
   (`source == 'media'`) open a `<dialog class="morph-modal">` editing
   title / alt text / description / tags + Direct URL + Download, submitting via
   the `data-ajax` JSON contract (`edit_meta` returns `{ok, asset}`; the tile
   updates in place). New `MediaAsset.title` + `description` fields back it
   (migration 0003); 4 tests pin the contract. Non-media tiles still deep-link to
   their product editor. **Also fixed a live 404:** `from_media_asset` linked
   `/dashboard/media/{id}/` (no `/edit/`) — every library tile click 404'd.

## Notes
- Keep everything inside the media plugin (+ digital_products for the secure
  download path). Follow the modular contract.
- This is a fresh-session feature chunk; item 1 already shipped.
