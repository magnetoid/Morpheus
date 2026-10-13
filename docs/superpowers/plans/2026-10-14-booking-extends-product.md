# Booking Extends Product — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every marketplace listing (experience or local good) is a catalog Product extended by the booking app, so the dashboard's Products, Linda's product tools, web stories and product SEO all cover them.

**Architecture:** `BookableService` gains a OneToOne `product` to `catalog.Product`; Product becomes the source of truth for the fields every product has and the listing keeps the booking data, so no booking, enquiry or review foreign key moves. A new `service` product type marks them; the shopping surfaces (storefront catalogue, sitemap, channel feeds) list only `Product.objects.shoppable()`. One idempotent management command links the existing 142 listings (reusing the 17 archived goods by slug) and creates a 301 from `/products/<slug>/` to `/bookings/<slug>/`.

**Tech Stack:** Django 6.0, django-money, the Morpheus hook bus (`PRODUCT_FORM_CARDS`, `PRODUCT_FORM_SAVED`), the seo app's `Redirect` model, the webstories app.

**Spec:** `docs/plans/booking-extends-product-2026-10.md`

## Global Constraints

- Product is the source of truth for: name, slug, short_description, description, price, compare_at_price (was-price), category, vendor, images, status, meta_title, meta_description.
- The listing keeps: listing_kind, duration_minutes, duration_label, meeting_point, latitude, longitude, region, location, languages, highlights, included, not_included, what_to_bring, itinerary, faqs, cancellation_policy, daily_capacity, max_guests_per_booking, availability windows, tiers, add-ons, bookings, enquiries, reviews.
- No foreign key on Booking, Enquiry, ServiceReview, ServiceImage, PricingTier, AddOn or AvailabilityWindow changes.
- The storefront URL of a listing stays `/bookings/<slug>/`.
- Nothing is deleted by the migration; a JSON backup of both tables is written first.
- The booking app requires `catalog`, `cms`, `seo` (already declared): it may import those apps; catalog must not import booking_marketplace.

## Review Focus

- A Product slug that already exists but belongs to a non-listing product: link only when the names match, otherwise create the Product with a `-experience` suffix.
- Running the link command twice: the second run changes nothing and creates no duplicate Product, image or Redirect.
- A listing whose image file is missing from storage: the Product is created without that image, not aborted.
- Editing an experience's price in the product editor while the listing editor is open in another tab: the Product value wins; the listing's copy is re-synced on save.
- Disabling the booking app: the Booking details card disappears from the product editor and service Products stay out of every shopping surface.

---

### Task 1: The `service` product type and `Product.objects.shoppable()`

**Files:**
- Modify: `plugins/installed/catalog/models.py` (PRODUCT_TYPES, a ProductQuerySet/manager)
- Create: `plugins/installed/catalog/migrations/0020_product_type_service.py` (makemigrations)
- Test: `plugins/installed/catalog/tests/test_service_products.py`

**Interfaces:**
- Produces: `Product.PRODUCT_TYPES` includes `('service', 'Service (booked through an app)')`; `Product.objects.shoppable()` → QuerySet of `status='active'` excluding `product_type='service'`.

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal
from django.test import TestCase
from djmoney.money import Money
from plugins.installed.catalog.models import Product


class ServiceProductTests(TestCase):
    def test_shoppable_leaves_out_services_and_inactive(self):
        Product.objects.create(name='Book', slug='book', sku='B1', status='active', price=Money(Decimal('10'), 'EUR'))
        Product.objects.create(name='Kayak', slug='kayak', sku='S1', status='active', product_type='service', price=Money(Decimal('50'), 'EUR'))
        Product.objects.create(name='Old', slug='old', sku='O1', status='archived', price=Money(Decimal('5'), 'EUR'))
        self.assertEqual(list(Product.objects.shoppable().values_list('slug', flat=True)), ['book'])
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test plugins.installed.catalog.tests.test_service_products`
Expected: FAIL (`'service'` not a valid choice is not enforced on create, so it fails on `AttributeError: ... has no attribute 'shoppable'`).

- [ ] **Step 3: Implement**

In `catalog/models.py` add above `class Product`:

```python
class ProductQuerySet(models.QuerySet):
    def shoppable(self):
        """What the shop sells as goods: active, and not a service an app books
        (booking_marketplace's experiences live at /bookings/<slug>/)."""
        return self.filter(status='active').exclude(product_type='service')
```

In `Product`: add `('service', 'Service (booked through an app)')` to `PRODUCT_TYPES`, and `objects = ProductQuerySet.as_manager()` (check first that `Product` does not already declare `objects`; if it does, add `shoppable` to that manager's queryset instead). Then `python manage.py makemigrations catalog -n product_type_service`.

- [ ] **Step 4: Run to verify it passes** (same command) — Expected: OK.
- [ ] **Step 5: Commit** — `git add plugins/installed/catalog && git commit -m "feat(catalog): a service product type and Product.objects.shoppable()"`

### Task 2: Shopping surfaces list only shoppable products

**Files:**
- Modify: `plugins/installed/catalog/graphql/queries.py:99` (the `products` list resolver; leave the single-product resolver at :80 alone, the redirect handles it)
- Modify: `plugins/installed/storefront/views/catalog.py` (each `Product.objects.filter(status='active')` that feeds a listing, category page or search — 7 sites; read each and switch the listing ones)
- Modify: `plugins/installed/seo/services/sitemaps.py:272` (product iterator) and the other product counts in that file that feed the sitemap
- Modify: every channel feed: `plugins/installed/{google_shopping,meta_commerce,microsoft_commerce,pinterest_commerce,snapchat_commerce,tiktok_commerce}/services/feed.py`, `plugins/installed/openai_shopping/feed.py`, `plugins/installed/agentic_checkout/feed.py`
- Test: `plugins/installed/catalog/tests/test_service_products.py` (extend)

**Interfaces:**
- Consumes: `Product.objects.shoppable()` (Task 1).

- [ ] **Step 1: Write the failing tests** (append to the Task 1 file)

```python
class ServiceProductSurfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(name='Book', slug='book', sku='B1', status='active', price=Money(Decimal('10'), 'EUR'))
        Product.objects.create(name='Kayak tour', slug='kayak-tour', sku='S1', status='active', product_type='service', price=Money(Decimal('50'), 'EUR'))

    def test_the_storefront_catalogue_leaves_services_out(self):
        html = self.client.get('/products/').content.decode()
        self.assertIn('/products/book/', html)
        self.assertNotIn('kayak-tour', html)

    def test_the_sitemap_leaves_services_out(self):
        from plugins.installed.seo.services.sitemaps import _merged_sitemap_entries
        locs = [e['loc'] for e in _merged_sitemap_entries()]
        self.assertFalse(any('/products/kayak-tour/' in loc for loc in locs))

    def test_the_google_feed_leaves_services_out(self):
        from plugins.installed.google_shopping.services.feed import build_feed_items  # use the module's real builder name
        self.assertNotIn('kayak-tour', str(build_feed_items()))
```

(Before writing the feed test, open `google_shopping/services/feed.py` and use the function it actually exports for building items; the sitemap function name is from CLAUDE.md memory "check `_merged_sitemap_entries()`".)

- [ ] **Step 2: Run to verify they fail** — Expected: the three assertions fail (services listed).
- [ ] **Step 3: Implement** — replace `Product.objects.filter(status='active')` with `Product.objects.shoppable()` at each listed site that lists products for shoppers or channels. Leave dashboard, Linda tools, ai_assistant search, webstories and recommendations untouched: services belong there.
- [ ] **Step 4: Run** the new tests and `plugins.installed.storefront plugins.installed.seo plugins.installed.google_shopping plugins.installed.meta_commerce` — Expected: OK.
- [ ] **Step 5: Commit** — `git commit -m "fix(catalog): shopping surfaces list only shoppable products"`

### Task 3: `BookableService.product` and `ensure_product(service)`

**Files:**
- Modify: `plugins/installed/booking_marketplace/models.py` (field)
- Create: `plugins/installed/booking_marketplace/migrations/00XX_bookableservice_product.py` (makemigrations)
- Create: `plugins/installed/booking_marketplace/products.py` (`ensure_product`, `sync_from_product`)
- Test: `plugins/installed/booking_marketplace/tests/test_listing_products.py`

**Interfaces:**
- Produces: `BookableService.product: OneToOneField('catalog.Product', null=True, blank=True, on_delete=SET_NULL, related_name='booking')`; `ensure_product(service) -> Product`; `sync_from_product(product) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
from decimal import Decimal
from django.test import TestCase
from djmoney.money import Money
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product, sync_from_product
from plugins.installed.catalog.models import Product, Vendor


class ListingProductTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=self.vendor, name='Kayak the bay', slug='kayak-the-bay', listing_kind='experience',
            short_description='Paddle', description='Long text', price=Money(Decimal('50'), 'EUR'),
            original_price=Money(Decimal('60'), 'EUR'), is_active=True,
        )

    def test_a_listing_gets_one_service_product_with_its_fields(self):
        p = ensure_product(self.svc)
        self.assertEqual((p.slug, p.name, p.product_type, p.status), ('kayak-the-bay', 'Kayak the bay', 'service', 'active'))
        self.assertEqual(p.price.amount, Decimal('50'))
        self.assertEqual(p.compare_at_price.amount, Decimal('60'))
        self.assertFalse(p.requires_shipping)
        self.assertEqual(ensure_product(self.svc).pk, p.pk)  # idempotent
        self.assertEqual(Product.objects.count(), 1)

    def test_an_archived_good_with_the_same_slug_and_name_is_reused(self):
        old = Product.objects.create(name='Kayak the bay', slug='kayak-the-bay', sku='OLD', status='archived', price=Money(Decimal('1'), 'EUR'))
        self.assertEqual(ensure_product(self.svc).pk, old.pk)

    def test_a_different_product_on_the_slug_is_left_alone(self):
        Product.objects.create(name='A book', slug='kayak-the-bay', sku='BOOK', status='active', price=Money(Decimal('9'), 'EUR'))
        p = ensure_product(self.svc)
        self.assertEqual(p.slug, 'kayak-the-bay-experience')

    def test_product_edits_flow_to_the_listing(self):
        p = ensure_product(self.svc)
        p.name = 'Kayak the Bay of Kotor'
        p.price = Money(Decimal('55'), 'EUR')
        p.save()
        sync_from_product(p)
        self.svc.refresh_from_db()
        self.assertEqual((self.svc.name, self.svc.price.amount), ('Kayak the Bay of Kotor', Decimal('55')))

    def test_the_product_page_redirects_to_the_booking_page(self):
        ensure_product(self.svc)
        resp = self.client.get('/products/kayak-the-bay/')
        self.assertEqual((resp.status_code, resp['Location']), (301, '/bookings/kayak-the-bay/'))
```

- [ ] **Step 2: Run** `... manage.py test plugins.installed.booking_marketplace.tests.test_listing_products` (with `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace'`) — Expected: ImportError / FAIL.
- [ ] **Step 3: Implement**

`models.py` in `BookableService`:

```python
    # The catalog Product this listing extends (docs/plans/booking-extends-product-2026-10.md):
    # Product owns name, slug, descriptions, price, category, host, photos, status and SEO.
    product = models.OneToOneField(
        'catalog.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='booking'
    )
```

`products.py`:

```python
"""A listing's catalog Product: created or linked once, then the source of truth."""

from __future__ import annotations

from django.db import transaction

_SYNCED = ('name', 'slug', 'short_description', 'description', 'price', 'category_id', 'vendor_id')


@transaction.atomic
def ensure_product(service):
    from djmoney.money import Money

    from plugins.installed.catalog.models import Product, ProductImage
    from plugins.installed.seo.models import Redirect

    if service.product_id:
        return service.product
    slug = service.slug
    existing = Product.objects.filter(slug=slug).first()
    if existing is not None and existing.name.strip().lower() != service.name.strip().lower():
        slug, existing = f'{service.slug}-experience', Product.objects.filter(slug=f'{service.slug}-experience').first()
    product = existing or Product(slug=slug, sku=f'BK-{service.pk.hex[:12].upper()}')
    product.name = service.name
    product.short_description = service.short_description
    product.description = service.description
    product.price = Money(service.price.amount, service.price.currency)
    product.compare_at_price = (
        Money(service.original_price.amount, service.original_price.currency) if service.original_price else None
    )
    product.category_id = service.category_id
    product.vendor_id = service.vendor_id
    product.product_type = 'service'
    product.status = 'active' if service.is_active else 'draft'
    product.requires_shipping = False
    product.track_inventory = False
    product.save()
    if service.image and not product.images.exists():
        try:
            if service.image.storage.exists(service.image.name):
                ProductImage.objects.create(product=product, image=service.image.name, is_primary=True, alt_text=service.name[:255])
        except Exception:  # noqa: BLE001 — a missing file never aborts the link
            pass
    for i, extra in enumerate(service.images.all().order_by('pk'), start=1):
        if not product.images.filter(image=extra.image.name).exists():
            ProductImage.objects.create(product=product, image=extra.image.name, sort_order=i, alt_text=service.name[:255])
    service.product = product
    service.save(update_fields=['product'])
    Redirect.objects.get_or_create(
        from_path=f'/products/{product.slug}/',
        defaults={'to_path': f'/bookings/{service.slug}/', 'status_code': 301, 'note': 'Booking listing'},
    )
    return product


def sync_from_product(product) -> None:
    """Copy the Product's fields onto its listing (the listing still reads its copies)."""
    service = getattr(product, 'booking', None)
    if service is None:
        return
    service.name = product.name
    service.short_description = product.short_description
    service.description = product.description
    service.price = product.price
    service.original_price = product.compare_at_price
    service.category_id = product.category_id
    service.vendor_id = product.vendor_id
    service.is_active = product.status == 'active'
    service.save(update_fields=['name', 'short_description', 'description', 'price', 'original_price', 'category', 'vendor', 'is_active'])
```

(Check `Redirect`'s `match_type`/`source` choices and pass the defaults the seo app uses for an exact-path redirect; check `ServiceImage` has an `image` field and order it by its real ordering field.)

- [ ] **Step 4: Run** the tests — Expected: OK. Then `makemigrations --check`.
- [ ] **Step 5: Commit** — `git commit -m "feat(booking_marketplace): a listing extends a catalog Product"`

### Task 4: Product saves reach the listing; new listings get their Product

**Files:**
- Modify: `plugins/installed/booking_marketplace/apps.py` or `app.py` `ready()` (post_save receiver on `catalog.Product`)
- Modify: `plugins/installed/booking_marketplace/host.py` (after a host saves a listing), `forms.py` `ListingForm.save` (after save) — call `ensure_product(svc)` then `sync_to_product(svc)` for the listing's own edits of shared fields
- Modify: `plugins/installed/booking_marketplace/products.py` (`sync_to_product(service)`: listing → product for the shared fields, used by the host portal and the listing editor)
- Test: extend `test_listing_products.py`

- [ ] **Step 1: Failing tests**

```python
    def test_saving_the_product_updates_the_listing_without_a_call(self):
        p = ensure_product(self.svc)
        p.price = Money(Decimal('70'), 'EUR')
        p.save()
        self.svc.refresh_from_db()
        self.assertEqual(self.svc.price.amount, Decimal('70'))

    def test_a_host_edit_reaches_the_product(self):
        from plugins.installed.booking_marketplace.products import sync_to_product
        p = ensure_product(self.svc)
        self.svc.name = 'Host renamed'
        self.svc.save()
        sync_to_product(self.svc)
        p.refresh_from_db()
        self.assertEqual(p.name, 'Host renamed')
```

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — `sync_to_product` mirrors `sync_from_product` in the other direction and saves with `update_fields`; register `post_save` for `catalog.Product` in the booking app's `ready()` calling `sync_from_product(instance)` inside `transaction.on_commit` (CLAUDE.md: a side effect that queries runs in its own savepoint; rebuild on commit). Guard re-entry: `sync_to_product` sets `product._booking_sync = True` before saving and the receiver returns early when it is set.
- [ ] **Step 4: Run** — OK, plus the full booking_marketplace suite.
- [ ] **Step 5: Commit** — `git commit -m "feat(booking_marketplace): product and listing stay in step"`

### Task 5: Booking details card in the product editor

**Files:**
- Modify: `plugins/installed/booking_marketplace/app.py` (register `PRODUCT_FORM_CARDS` and `PRODUCT_FORM_SAVED` handlers, like `zendrop/app.py:135-170`)
- Create: `plugins/installed/booking_marketplace/templates/booking_marketplace/_product_form_card.html`
- Test: `plugins/installed/booking_marketplace/tests/test_product_form_card.py`

**Interfaces:**
- Consumes: `product.booking` (Task 3). Card inputs are named `booking__<field>` so the save handler knows the card was on the form.

- [ ] **Step 1: Failing tests** — a superuser GETs `/dashboard/products/<product.pk>/` for a linked product and sees `name="booking__meeting_point"`; a product without a listing does not; POSTing the product form with `booking__duration_label=3 hours` and `booking__highlights=A\nB` saves them on the listing (`['A', 'B']`); with the app deactivated (`app_registry._active.discard('booking_marketplace')`, restored with `addCleanup`) the card is absent.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — `on_product_form_cards` appends `{'template': 'booking_marketplace/_product_form_card.html', 'context': {'listing': product.booking}, 'order': 60}` when `getattr(product, 'booking', None)`; `on_product_form_saved` reads the `booking__*` keys present in `post` (skip when none are present) and saves listing_kind, region, location, duration_minutes, duration_label, meeting_point, languages (comma list), highlights / included / not_included / what_to_bring (one per line), cancellation_policy, daily_capacity, max_guests_per_booking. The template is a `card card-padded` with those inputs and a link to the host editor for availability and tiers.
- [ ] **Step 4: Run** — OK.
- [ ] **Step 5: Commit** — `git commit -m "feat(booking_marketplace): booking details on the product editor"`

### Task 6: The dashboard points at the product editor

**Files:**
- Modify: `plugins/installed/booking_marketplace/dashboard_listings.py` (`edit_url(service)` returns `/dashboard/products/<service.product_id>/` when linked)
- Modify: `plugins/installed/booking_marketplace/agent_tools.py` (`listings.update` writes the shared fields on the Product when linked, then `sync_from_product`)
- Test: extend `tests/test_dashboard_listings.py`

- [ ] **Step 1: Failing tests** — for a linked listing the storefront staff bar's `active_edit_url` is `/dashboard/products/<pk>/`; `listings.update(slug, price='19.50')` changes `product.price` and the listing's copy.
- [ ] **Step 2–4:** implement, run, pass.
- [ ] **Step 5: Commit** — `git commit -m "feat(booking_marketplace): Edit opens the product editor for linked listings"`

### Task 7: Link the existing listings (command) and back them up

**Files:**
- Create: `plugins/installed/booking_marketplace/management/commands/link_listing_products.py`
- Test: `plugins/installed/booking_marketplace/tests/test_link_command.py`

- [ ] **Step 1: Failing test** — two listings (one with an archived same-name Product), `call_command('link_listing_products', backup='<tmp>/b.json')`: both linked, the archived Product reused and now `service` + active, the backup file lists both listings and the pre-existing Product; a second run reports `linked=0` and creates nothing.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — dump `BookableService` and `Product` rows touched (pk, slug, name, status, product_type, price) to the `--backup` path, then `ensure_product(s)` for every listing in a loop, printing `linked=<n> reused=<n> created=<n>`.
- [ ] **Step 4: Run** — OK.
- [ ] **Step 5: Commit** — `git commit -m "feat(booking_marketplace): link_listing_products command"`

### Task 8: The web story on the experience page

**Files:**
- Modify: `plugins/installed/webstories/app.py` (a second `StorefrontBlock` for slot `listing_below_description`, same template)
- Modify: `plugins/installed/booking_marketplace/templates/booking_marketplace/detail.html` and `themes/library/montenegro/templates/booking_marketplace/detail.html` (emit `{% storefront_blocks "listing_below_description" %}` after the description)
- Modify: `plugins/installed/booking_marketplace/views.py` `service_detail` (context `product` = the linked Product, `web_story` = `getattr(product, 'web_story', None)` — check the WebStory related name)
- Test: `plugins/installed/booking_marketplace/tests/test_listing_story.py`

- [ ] **Step 1: Failing test** — with a published WebStory on the linked Product, `/bookings/<slug>/` contains `amp-story-player` and `/story/<product slug>/`; without one it contains neither.
- [ ] **Step 2–4:** implement, run (also `core.tests.test_slot_parity`; if the new slot fails parity under the default theme, the plugin's own `detail.html` renders it, which is what parity reads), pass.
- [ ] **Step 5: Commit** — `git commit -m "feat(webstories): the story card on booking pages"`

### Task 9: Ship and run on Montenegro

- [ ] Full suite with `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`; ruff; boundary and plugin-standard checks; `makemigrations --check`.
- [ ] Docs: CLAUDE.md (the booking app extends Product; `shoppable()` is what shopping surfaces list), `docs/PLUGIN_DEVELOPMENT.md` booking section, the spec's status.
- [ ] `release --minor "Experiences are products"`, push, `scripts/deploy_smoke.sh`.
- [ ] On Montenegro: `python manage.py link_listing_products --backup /tmp/listings-before-link.json`, copy the backup to `/root/content-backups/`, then `python manage.py backfill_webstories`.
- [ ] Verify live: Dashboard → Products shows 142 more products; an experience's product editor shows Booking details; `/products/<experience>/` 301s to `/bookings/<slug>/`; the experience page shows the story card; `/sitemap.xml` has no `/products/<experience>/`.

---

The SEO page structure and the content rewrite (spec, "Then, on that structure") are a separate plan written after this one ships: they edit templates and content on the structure this plan creates.
