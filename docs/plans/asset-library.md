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

2. **Nice digital-product Upload button + a Download button beside it.**
   On the product editor's digital-file section (and/or the library tile),
   pair the upload control with a Download (`<a href="{{ asset.url }}" download>`
   styled `.btn`). For digital products the secure path may differ — check
   `digital_products/views.py` for an existing tokened download route before
   linking the raw file URL.

3. **All uploads (images, PDFs, …) appear on the asset page.** Federation
   already covers MediaAsset + ProductImage + digital_file. VERIFY nothing is
   siloed: digital products render under a special tab (see views.py docstring) —
   confirm a standalone PDF upload and every product image surface in the default
   view, and widen `_federated_assets` / `_filter_for_view` if a source is missing.

4. **Click an asset → modal popup to edit title / description / all SEO.**
   Tiles currently link to `a.edit_url` (the full `edit_meta` page). Replace with
   a modal: fetch the edit form (or render the fields inline) into an
   `admin_dashboard` modal, submit via the `data-ajax` JSON pattern
   (see the `dashboard-ajax-json-contract` memory — return JSON, not a redirect).
   Fields to expose: title, alt text, description, + SEO (read what `edit_meta.html`
   already offers; add the SEO plugin's SeoMeta fields if missing).

## Notes
- Keep everything inside the media plugin (+ digital_products for the secure
  download path). Follow the modular contract.
- This is a fresh-session feature chunk; item 1 already shipped.
