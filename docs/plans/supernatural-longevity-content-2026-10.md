# supernatural-shop.com — content per the longevity analysis (2026-10)

**Status: shipped in v0.82.0 (2026-10-09).** Owner request (2026-10-08): "this is the
content analysis — do the complete content on supernatural-shop.com according to it."
Source: the owner's research document *Where a dropshipped longevity shop profits*
(Google Doc `Longevity_shop_profitable_categories.md`).

## What the analysis says the shop is

* **Identity:** a verified, food-first, modestly priced longevity pantry. "A store
  named for the natural should sell on the tested."
* **Profit engine:** daily staples (creatine, magnesium, omega-3, fiber, collagen)
  on reorder/subscription, sold as stacks; mushrooms (lion's mane, reishi,
  mushroom coffee) as the second line.
* **Traffic:** ingredient-level comparison content, email, affiliate links —
  not generic health SEO; retailers with comparison data are the realistic AEO
  opening.
* **Leave out:** weight-loss formulas, pre-workouts, joint formulas, melatonin.
* **Claims:** US-first. Structure/function language only, substantiated;
  no lifespan, anti-ageing or disease claims (FTC holds retailers and affiliates
  liable; Stripe and Shopify bar "pseudo-pharmaceuticals"; EU/UK ban unauthorised
  claims). Food sidesteps most of this.
* **Gaps to own:** food-first assortment, entry price below the $79/month hero
  products, batch-level testing transparency.

## What the site was (2026-10-08)

684 active products from one vendor: ~450 imported aromatherapy items (oils,
blends, hydrosols, carrier oils, books, kits), 90 seeded "wellness" items
(vitamins, adaptogens and mushrooms, superfoods, herbal tinctures, teas) with
invented brand names, 90 seeded "arcana" items (crystals, talismans,
divination), 12 NatureGift weight-loss coffees making fat-burning claims. Home
led with a scrying orb and an amulet; "Emotional Trauma Blend — Proven
anti-anxiety oils" sat on the home page; the theme still said "N books",
"between issues", "Meet the publishers", the footer offered "Write a book", and
the product page and cart promised "Free shipping over $40" with no such rate.

## Content delivered

1. **Theme copy (`supernatural_shop` 0.2.0):** nav by shelf (Shop · Daily staples ·
   Mushrooms · Pantry · Aromatherapy · Guides); home that starts with the staples, a
   curated "shop by shelf" index, an Our standards block and guides; About ("A pantry,
   not a pharmacy"); the US supplement disclaimer in every footer; product counts in
   products, not books; search examples, cart, journal, vendor, marketplace and
   affiliate pages without bookshop or oils-only words; shipping and returns fallbacks
   with no invented rate, carrier or threshold; the product page's trust strip now
   states only what checkout and the returns and standards pages state.
2. **Catalogue (store DB, backed up first to `/root/content-backups/` on tetra):**
   wellness categories renamed to Longevity, Daily staples, Mushrooms & adaptogens,
   Pantry, Teas, Herbal tinctures, with descriptions and search descriptions; Arcana
   and the aromatherapy shelves described as objects and scents, with safety notes;
   collagen and flax filed under Daily staples too, every tea under Pantry too.
3. **Products:** the 90 seeded wellness items renamed plainly ("Moonlit Magnesium" →
   "Magnesium Glycinate"), with claim-free one-liners carrying the safety notes that
   matter (He Shou Wu liver risk, chaga oxalates, mucuna L-dopa, ginkgo and blood
   thinners, kelp iodine); 57 sentences claiming tests, certificates,
   standardisation, organic status or detox effects removed from their long copy;
   their search titles and descriptions refreshed.
4. **Merchandising:** featured = magnesium, omega-3, vitamin D3+K2, lion's mane,
   matcha, cacao nibs, reishi, rooibos; a "Start here" collection on the home rail.
5. **Guides (journal):** eleven sourced, claim-safe articles on the analysis's top
   categories (magnesium forms, creatine, fish oil labels, fiber, collagen, lion's
   mane / reishi / cordyceps, mushroom coffee, high-phenolic olive oil, matcha grades,
   NAD/NMN/NR, a simple daily stack), each with citations and a disclaimer.
6. **Pages:** Our standards (new), FAQ rewritten.
7. **Compliance pass:** the twelve weight-loss coffees archived and their four
   categories deactivated; the home page's anti-anxiety claim removed; the book
   creator app ("Write a book") switched off.

## Left for the owner (decisions, not content)

* The staples the analysis ranks first (creatine, psyllium, collagen as a real
  SKU, mushroom coffee, high-phenolic olive oil, tinned fish) need real supplier
  quotes — the seeded wellness items have invented specifications and no supplier
  behind them, and their long copy still carries some of those specifics.
* ~370 imported aromatherapy descriptions mention diseases (acne, anxiety,
  Alzheimer's, infections), and one oil's copy mentions weight loss. They read like
  another retailer's copy; check the right to use them, then rewrite or retire them.
* 18 products are priced $0.00 (some are free downloads, some are missing
  prices — e.g. Rose Absolute, Beeswax Absolute).
* The standards page, the FAQ and the returns page state policies (certificates of
  analysis per batch, doses on every label, 30-day returns on unopened items); keep
  them true or edit them before you rely on them. Real shipping and returns terms
  belong in CMS pages `shipping` and `returns`, which replace the theme's fallbacks.
