"""product_gallery — square-format scroll-snap carousel for PDPs.

A self-contained plugin that ships a single template partial,
`product_gallery/_carousel.html`, designed to drop into any theme's
PDP via ``{% include "product_gallery/_carousel.html" with images=… %}``.

The carousel:
  - square slides (aspect-ratio 1:1, object-fit cover)
  - native CSS scroll-snap horizontal swipe (mobile + trackpad)
  - prev/next buttons + dot indicators + image counter
  - keyboard nav (← → when focused)
  - works with the SEO plugin's responsive <picture> output

No JS library, no migration.
"""
