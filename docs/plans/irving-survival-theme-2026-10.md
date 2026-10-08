# Irving Survival theme — direction 1a (2026-10)

**Status: shipped in v0.82.0, active on beta.irvingsurvival.com.** Owner request
(2026-10-08): "create the Irving Survival theme in the repo and make it active on
beta.irvingsurvival.com", followed by two design canvases: *Turn 1 · Homepage
directions* (1a product hero, 1b bento grid, 1c editorial index) and *Inner pages ·
built on direction 1a* (category, product, calculator, bundles, checkout). The canvases
use the working name "REMNANT"; the theme reads the store's own name.

## What was built (`themes/library/irving_survival/`)

* **Design system** in `templates/storefront/base.html`: warm grey `#F3F2EE`, white
  surfaces, ink `#121311`, one orange signal `#E8590C`, Geist + Geist Mono, pill
  buttons, 24–28 px tiles. The legacy token names (`--paper`, `--rule`, `--serif`)
  stay as aliases so every shared page template restyles without edits.
* **Chrome:** a status line (theme setting; default "Power cut in England, Scotland or
  Wales? Call 105, free." with a link to the Government's Prepare guidance), the
  letter-spaced wordmark, five nav links, Search / Account / Cart as words, a
  four-column footer.
* **Home (1a):** centred hero in Irving's own words ("Normal life can stop. Your
  needs don't."); the lead featured product large, or — with nothing featured — the
  household kit list; four official figures (2.5–3 L, 10 L, 105, several days of
  medicines); shop by system (top-level categories, from three); featured; the
  supply calculator and readiness cards; bundles (the `staff-picks` collection under
  its own name); a guides band.
* **Inner pages:** category and product list with the large title row and a filter
  sidebar (search, category, sort and attribute facets in one form); the product page
  with a wider gallery, a tall buy box, a full-width cart pill and facts in mono; the
  calculator (`/p/calculator/`) and readiness check (`/p/readiness/`) rendered by the
  theme's `cms/page.html`; returns and shipping fallbacks that state UK statutory
  rights and no invented rate, carrier or threshold.

## Decisions against the canvases

* No "GLOBAL STATUS: STABLE · Grid 99.2%" line — the theme cannot know grid status;
  the status line carries the 105 power-cut number instead.
* No auto-rotate food subscription band — the store sells no such service; the band
  is the guides instead.
* The readiness score is the visitor's own answers, kept in their browser; with no
  answers it shows a dash rather than the canvas's "34".
* The calculator's list names quantities, not products, and has no "Add all to
  cart": the theme cannot know which product in this catalogue answers each line.

## Store setup done with the activation

* `MORPHEUS_ACTIVE_THEME=irving_survival` (production + preview) and
  `MORPHEUS_DISABLED_APPS` = the book vertical, as on supernatural and montenegro.
* CMS pages `calculator` and `readiness` published; the bookshop's 3D store and
  "Write a book" apps switched off; the empty "Books" category deactivated.

## Left for the owner

* The catalogue is empty: products, top-level categories (for "shop by system") and a
  `staff-picks` collection named for the bundles.
* The store currency is USD while the copy is written for UK households (statutory
  rights, 105). Switching to GBP is a settings change the owner should make on purpose.
* Shipping and returns: write the real terms as CMS pages `shipping` and `returns`;
  they replace the theme's fallbacks automatically.
