# The booking app extends Product (Montenegro, 2026-10-14)

**Status:** the structure shipped in v0.109.0 (plan:
`docs/superpowers/plans/2026-10-14-booking-extends-product.md`); Montenegro's listings are
linked by `manage.py link_listing_products --backup <file>` (`--dry-run` lists what it
would do). The experience-page SEO structure and the content rewrite ("Then, on that
structure") are next.

Owner, 2026-10-14: "experiences don't reflect the database in the backend of Morpheus, why?" and
"the booking plugin extends products in Morpheus with the additional data that is displayed on the
booking page."

## Why they don't show today

`booking_marketplace` keeps experiences and local goods in its own table, `BookableService`
(142 rows on Montenegro: 125 experiences, 17 goods), parallel to `catalog.Product`. The dashboard's
Products page, Linda's product tools, web stories, translations, the search index and the product
SEO all read `Product`, so none of them see an experience. That is the parallel-table pattern
CLAUDE.md forbids ("one concept = one model owner; extending a flow means a FK/OneToOne to the
owner's model, never a parallel table"). The 17 goods also exist as archived catalog Products
(the same names), a leftover of the same split.

## The design

**Product owns what every product has; the booking app owns only what a booking needs.**

- `BookableService` gains `product = OneToOneField('catalog.Product', related_name='booking')`. It
  stays the booking extension, so every booking, enquiry, review, photo, availability window, price
  tier and add-on keeps pointing where it points now: no foreign key moves, no booking is touched.
- **Product is the source of truth** for name, URL slug, short and long description, price and
  was-price, category, host (vendor), photos, active/draft, SEO title and description, and
  translations. **The extension keeps** listing kind, duration, meeting point and map pin, region,
  languages, highlights, included / not included, what to bring, itinerary, FAQs, cancellation
  policy, capacity, availability, tiers and add-ons.
- The old copies of the product fields on `BookableService` are kept in step from Product while the
  rest of the app is moved over to read Product, then dropped in a later release.

**One migration, reversible, Montenegro only (the only store with the app):**
1. For each listing, link the catalog Product with the same slug if one exists (the 17 archived
   goods: this ends the duplicate), otherwise create one: name, slug, descriptions, price,
   `compare_at_price` from the was-price, category, vendor, status from active, the listing photo
   and gallery as product images, `product_type` for a service (no shipping, no stock).
2. Nothing is deleted. A backup of both tables is taken first.

**What the merchant sees:**
- Dashboard → Products lists every experience and good. The product editor gets a **Booking details**
  card contributed by the booking app through `PRODUCT_FORM_CARDS` (the documented pattern; it
  vanishes if the app is disabled): duration, meeting point, languages, highlights, included,
  itinerary, FAQs, cancellation policy, capacity, with availability and tiers linked.
- The Listings page (v0.108.0) becomes a filtered view of those products.
- The storefront keeps `/bookings/<slug>/` (the URLs Google has); `/products/<slug>/` for an
  experience redirects there.
- Web stories, translations, Linda's product tools and product SEO now cover experiences with no
  extra code, and the story card shows on the experience page.

## Then, on that structure

Status (2026-10-14): the page structure and the import command shipped in v0.110.0; content per
`docs/superpowers/plans/2026-10-14-experience-pages-seo-and-content.md` Tasks 8–9.

1. **SEO structure of the experience page:**
   - Answer-first summary and an at-a-glance block (duration, meeting point, languages, group size,
     cancellation).
   - Highlights, itinerary, what's included, FAQs (`FAQPage`), a map, related experiences and places.
   - Structured data: Product + Offer, TouristTrip / itinerary, `aggregateRating` only from verified
     reviews.
2. **Content:** rewrite all 125 experiences and 17 goods, each at a few hundred words of specific,
   expert text with an SEO title and description, written by parallel writers against a brief and
   validator (the Irving categories method). A backup is taken first.

## Tests that prove it

- After the migration every listing has exactly one Product with the same slug, name, price and
  photos.
- Bookings, enquiries and reviews are unchanged in count and links.
- The dashboard product list and Linda's product search find experiences.
- Editing an experience's price in the product editor changes the booking page.
- Disabling the booking app removes the Booking details card.
- `/products/<experience-slug>/` redirects to `/bookings/<slug>/`.
