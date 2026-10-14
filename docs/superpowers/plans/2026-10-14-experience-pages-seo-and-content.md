# Experience Pages: SEO Structure and Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Montenegro experience page answers first, lays out the facts a traveller decides on, describes itself fully in structured data and carries rewritten, specific copy for all 142 listings, editable in the product editor.

**Architecture:** The markup lives in the Montenegro theme's booking page. The view, the JSON-LD, the product editor's Booking details card and a content-import command live in `booking_marketplace`. The copy is written outside the app (a brief, a validator, parallel writers) and applied live by the command, which writes a backup first; applying that backup restores the old values.

**Tech Stack:** Django templates, booking_marketplace hooks (`SEO_JSONLD_GRAPH`, `PRODUCT_FORM_CARDS` / `PRODUCT_FORM_SAVED`), seo `SeoMeta`, the gettext `sr` catalog.

**Spec:** `docs/plans/booking-extends-product-2026-10.md`, section "Then, on that structure" (items 1 and 2).

## Global Constraints

- Page markup is the Montenegro theme's (`themes/library/montenegro/templates/booking_marketplace/detail.html`). The view, JSON-LD, card and command belong to `booking_marketplace`. Nothing in `storefront`, `seo` or `admin_dashboard` changes.
- Every new `{% trans %}` string in the theme or the app's templates gets a Serbian (Montenegrin ijekavian, Latin script) `msgstr` in `locale/sr/LC_MESSAGES/django.po`. Compile it with `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`; `booking_marketplace/tests/test_serbian_catalog.py` enforces this. The dashboard card stays plain English with no `{% trans %}`, like the rest of the card.
- Structured data states only what the page shows:
  - `aggregateRating` and `Review` come only from `services.verified_reviews`.
  - An `Offer` appears only when prices are shown (`not listing_mode`).
  - The currency comes from the price and is never hardcoded.
- Content never invents operational facts. Price, duration, group size, languages, meeting point, inclusions and exclusions, and cancellation terms stay as stored. Prose, itinerary steps and FAQ answers use only those facts plus public knowledge of the place.
- Live writes happen only after a database dump and the command's JSON backup, both kept in `/root/content-backups/` on tetra.
- Tests assert on unique markers (element ids, slugs), never on display words (CLAUDE.md).
- Tests run with: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace' .venv/bin/python manage.py test <labels>` (written `$TEST <labels>` below).
- Gates before pushing:
  - ruff 0.15.8 `check .` and `format --check .`
  - `manage.py check`
  - `makemigrations --check --dry-run`
  - `scripts/check_core_boundary.py`, `check_plugin_boundary.py` and `check_plugin_standard.py`
  - `manage.py release --check`

  A merge to main deploys; release with `manage.py release`.
- Page CSS goes in `{% block extra_head %}`. Never write `*/` inside a CSS comment.

## Owner decisions this plan takes (each can be reversed before execution)

1. **Reviews.** The reviews list keeps showing every review, because the code treats them as the merchant's content (`services.verified_reviews` docstring). Only the rating in the Reviews heading switches to verified reviews, matching the rating line under the title, which already does.
2. **Itineraries for the 20 flagship experiences.** These have no itinerary today. Writers may give each a 3–6 step itinerary built only from its stored facts and description. No meeting point or languages are invented; those rows stay hidden.
3. **Names.** Experience names may be improved to say what and where. Slugs and URLs never change. Goods keep their names.
4. **Language.** The copy is written in English. `/sr/` pages show it in English until localization step 1 translates database content.

## Review Focus

1. **Old seed shapes.** A listing whose itinerary or FAQs hold an old shape (a non-dict entry, or a step with no detail): the page and JSON-LD skip the bad entry and keep the rest. Tested by `test_malformed_steps_are_skipped` (Task 4).
2. **No linked product.** A listing never linked to a product renders from its own fields, and the summary falls back to `service.short_description`. Tested by `test_an_unlinked_listing_still_renders` (Task 2).
3. **Listing mode.** With `BOOKING_LISTING_MODE=True`, there is no Offer anywhere, and no Product node unless a verified rating gives it something to carry. The TouristTrip becomes the main entity. Tested by `test_listing_mode_states_no_price` (Task 4).
4. **Long text.** A product short description longer than the listing's 300 characters, or a name longer than 200, is clipped on the listing's copy, so the sync never fails on Postgres. A listing save never truncates the product. Tested in Task 1.
5. **Restoring a backup.** Applying a backup file as input returns every field it names to its prior value, including the SEO row's `auto_filled` flag. Tested by `test_the_backup_puts_everything_back` (Task 6).

---

### Task 1: The listing's copies fit their columns

**Files:**
- Modify: `plugins/installed/booking_marketplace/products.py` (`sync_from_product`, `sync_to_product`, new `_clip` and `_listing_copy`)
- Test: `plugins/installed/booking_marketplace/tests/test_listing_text.py`

**Interfaces:**
- Produces: `_listing_copy(service, field: str, value: str) -> str`, which returns what the listing keeps of a Product text field (plain text, clipped to the listing column's `max_length`).

Product allows a 300-character name and an unlimited short description; the listing's copies are `varchar(200)` and `varchar(300)`. On Postgres a longer edit fails the listing's save inside `on_product_updated` (logged and swallowed), so the page goes on showing the old title. sqlite never enforces the length.

- [ ] **Step 1: Write the failing tests** (append to `ListingTextTests`)

```python
    def test_a_long_product_name_and_summary_fit_the_listing(self):
        # Product.name allows 300 characters and short_description is unlimited; the
        # listing's copies are varchar(200) and varchar(300), and Postgres refuses more.
        self._edit_product(
            name='Kayak the bay of Kotor ' * 11,
            short_description='<p>' + 'Paddle under the walls at dawn. ' * 15 + '</p>',
        )
        self.assertLessEqual(len(self.svc.name), 200)
        self.assertLessEqual(len(self.svc.short_description), 300)
        self.assertTrue(self.svc.short_description.endswith('…'))

    def test_saving_the_listing_keeps_the_products_long_text(self):
        from plugins.installed.booking_marketplace.products import save_listing

        long_name = ('Kayak the bay of Kotor ' * 11).strip()
        long_summary = 'Paddle under the walls at dawn. ' * 15
        self._edit_product(name=long_name, short_description=long_summary)
        self.svc.price = Money(Decimal('60'), 'EUR')
        save_listing(self.svc)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, long_name)
        self.assertEqual(self.product.short_description, long_summary)
```

- [ ] **Step 2: Run them, expecting a failure**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_listing_text`
Expected: FAIL, with `252 not less than or equal to 200` in the first test.

- [ ] **Step 3: Implement**

In `products.py`, below `plain_text`:

```python
def _clip(text: str, limit: int) -> str:
    """The text cut at a word to fit `limit` characters, with an ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'


def _listing_copy(service, field: str, value: str) -> str:
    """What the listing keeps of a Product text field: plain, and short enough for its column.

    Product allows a longer name and an unlimited summary; Postgres refuses a copy
    longer than the listing's column, and sqlite never does.
    """
    text = value if field == 'name' else plain_text(value)
    limit = type(service)._meta.get_field(field).max_length
    return _clip(text, limit) if limit else text
```

In `sync_from_product`, replace the three text assignments with:

```python
    service.name = _listing_copy(service, 'name', product.name)
    service.short_description = _listing_copy(
        service, 'short_description', product.short_description
    )
    service.description = _listing_copy(service, 'description', product.description)
```

In `sync_to_product`, replace `product.name = service.name` and the text loop with:

```python
    # The listing holds plain, clipped copies of the product's text: write a field back
    # only when the host changed it, or a price edit would strip the editor's formatting
    # or cut a long name.
    for field in ('name', 'short_description', 'description'):
        text = getattr(service, field)
        if text != _listing_copy(service, field, getattr(product, field)):
            setattr(product, field, text)
```

- [ ] **Step 4: Run them, expecting a pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_listing_text plugins.installed.booking_marketplace.tests.test_listing_products`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/booking_marketplace/products.py plugins/installed/booking_marketplace/tests/test_listing_text.py
git commit -m "fix(booking): the listing's copies fit their columns, and a listing save never cuts the product's text"
```

---

### Task 2: The page answers first and lays out its facts

**Files:**
- Modify: `themes/library/montenegro/templates/booking_marketplace/detail.html`
- Modify: `locale/sr/LC_MESSAGES/django.po` and `django.mo`
- Create: `plugins/installed/booking_marketplace/tests/test_experience_page_structure.py`

**Interfaces:**
- Consumes: the `listing_text` filter (v0.109.2), `listing_rating` (already in the template as `vr`).
- Produces: element ids `experience-summary`, `at-a-glance`, `glance-duration`, `glance-group`, `glance-languages`, `glance-meeting-point`, `glance-cancellation`, `about`, `meeting-point`, `guest-questions`, `reviews` and `reviews-rating`. Task 3 adds `places-nearby` after the similar experiences.

- [ ] **Step 1: Write the failing tests**

```python
"""The experience page answers first and lays out the facts a traveller decides on."""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import BookableService, Booking, ServiceReview
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor

SUMMARY = 'Two calm hours paddling under the walls of Kotor at dawn, for beginners.'


class ExperiencePageStructureTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            region='kotor',
            location='Kotor',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description=SUMMARY,
            description='Paddle the bay.',
            duration_label='2 hours',
            max_guests_per_booking=8,
            languages=['English', 'Montenegrin'],
            meeting_point='Kotor Sea Gate, by the ticket kiosk',
            cancellation_policy='Free cancellation up to 24 hours before.',
            faqs=[{'q': 'Do I need to swim?', 'a': 'A little; you wear a vest.'}],
        )
        self.product = ensure_product(self.svc)

    def _page(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _section(self, html, marker):
        start = html.index(marker)
        return html[start : html.index('</section>', start)]

    def test_the_summary_answers_first_under_the_title(self):
        html = self._page()
        self.assertLess(html.index('<h1'), html.index('id="experience-summary"'))
        self.assertLess(html.index('id="experience-summary"'), html.index('id="at-a-glance"'))
        start = html.index('id="experience-summary"')
        self.assertIn(SUMMARY, html[start : start + 600])

    def test_at_a_glance_lists_the_known_facts(self):
        block = self._section(self._page(), 'id="at-a-glance"')
        for marker, fact in (
            ('glance-duration', '2 hours'),
            ('glance-group', '8'),
            ('glance-languages', 'English, Montenegrin'),
            ('glance-meeting-point', 'Kotor Sea Gate, by the ticket kiosk'),
            ('glance-cancellation', 'Free cancellation up to 24 hours before.'),
        ):
            with self.subTest(marker=marker):
                self.assertIn(f'id="{marker}"', block)
                self.assertIn(fact, block)

    def test_at_a_glance_leaves_out_what_the_listing_does_not_know(self):
        BookableService.objects.filter(pk=self.svc.pk).update(languages=[], meeting_point='')
        block = self._section(self._page(), 'id="at-a-glance"')
        self.assertNotIn('id="glance-languages"', block)
        self.assertNotIn('id="glance-meeting-point"', block)
        self.assertIn('id="glance-duration"', block)

    def test_the_meeting_point_shows_where_youll_be(self):
        html = self._page()
        self.assertIn('Kotor Sea Gate, by the ticket kiosk', self._section(html, 'id="meeting-point"'))

    def test_the_description_has_its_heading(self):
        self.assertIn('id="about"', self._page())

    def test_guest_questions_come_before_the_reviews(self):
        html = self._page()
        self.assertEqual(html.count('id="guest-questions"'), 1)
        self.assertEqual(html.count('id="reviews"'), 1)
        self.assertLess(html.index('id="guest-questions"'), html.index('id="reviews"'))

    def test_a_product_listing_has_no_at_a_glance(self):
        BookableService.objects.filter(pk=self.svc.pk).update(listing_kind='product')
        self.assertNotIn('id="at-a-glance"', self._page())

    def test_an_unlinked_listing_still_renders(self):
        BookableService.objects.filter(pk=self.svc.pk).update(product=None)
        html = self._page()
        self.assertIn(SUMMARY, html)
        self.assertIn('id="at-a-glance"', html)

    def test_the_reviews_heading_rates_only_verified_reviews(self):
        ServiceReview.objects.create(service=self.svc, rating=5, author_name='Seed', body='Seeded.')
        self.assertNotIn('id="reviews-rating"', self._page())
        U = get_user_model()
        guest = U.objects.create(**{U.USERNAME_FIELD: 'guest@x.io'})
        Booking.objects.create(
            service=self.svc,
            customer=guest,
            customer_name='Guest',
            customer_email='guest@x.io',
            booking_date=timezone.localdate() + datetime.timedelta(days=2),
            guests=1,
            status='confirmed',
        )
        S.create_review(self.svc, user=guest, rating=4, body='A real morning on the water.')
        self.assertIn('id="reviews-rating"', self._page())
```

- [ ] **Step 2: Run them, expecting a failure**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_experience_page_structure`
Expected: FAIL / ERROR, with `substring not found` for `id="experience-summary"`.

- [ ] **Step 3: Edit the template**

Run this script from the repo root. Each `replace` asserts that its anchor occurs exactly once.

```python
from pathlib import Path

p = Path('themes/library/montenegro/templates/booking_marketplace/detail.html')
s = p.read_text()


def once(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:60])
    s = s.replace(old, new)


# 1. The answer-first summary, inside the title block, under the rating line.
once(
    '      {% endif %}\n    </div>\n  </div>\n\n  <!-- Image gallery -->',
    '      {% endif %}\n    </div>\n'
    '    {# Answer first: what it is, where, how long and for whom, before anything else. #}\n'
    '    {% with summary=product.short_description|default:service.short_description %}{% if summary %}\n'
    '    <div id="experience-summary" class="mt-4 max-w-3xl text-base md:text-lg leading-7 md:leading-8 text-foreground">{{ summary|listing_text }}</div>\n'
    '    {% endif %}{% endwith %}\n'
    '  </div>\n\n  <!-- Image gallery -->',
)

# 2. At a glance, before Highlights: each fact only when the listing knows it.
DT = 'class="text-sm text-muted-foreground"'
DD = 'class="font-medium text-foreground mt-0.5"'
once(
    '      {# Highlights #}\n',
    '      {# At a glance: the facts a traveller decides on, each only when the listing knows it. #}\n'
    "      {% if service.listing_kind != 'product' %}\n"
    '      <section id="at-a-glance" class="py-8 border-b border-border">\n'
    '        <h2 class="text-xl font-semibold text-foreground mb-6">{% trans "At a glance" %}</h2>\n'
    '        <dl class="grid sm:grid-cols-2 gap-x-8 gap-y-5">\n'
    f'          {{% if service.duration_label or service.duration_minutes %}}<div id="glance-duration"><dt {DT}>{{% trans "Duration" %}}</dt><dd {DD}>{{% if service.duration_label %}}{{{{ service.duration_label }}}}{{% else %}}{{{{ service.duration_minutes }}}} {{% trans "minutes" %}}{{% endif %}}</dd></div>{{% endif %}}\n'
    f'          {{% if service.max_guests_per_booking %}}<div id="glance-group"><dt {DT}>{{% trans "Group size" %}}</dt><dd {DD}>{{% trans "Up to" %}} {{{{ service.max_guests_per_booking }}}} {{% trans "guests per booking" %}}</dd></div>{{% endif %}}\n'
    f'          {{% if service.languages %}}<div id="glance-languages"><dt {DT}>{{% trans "Languages" %}}</dt><dd {DD}>{{{{ service.languages|join:", " }}}}</dd></div>{{% endif %}}\n'
    f'          {{% if service.meeting_point %}}<div id="glance-meeting-point" class="sm:col-span-2"><dt {DT}>{{% trans "Meeting point" %}}</dt><dd {DD}>{{{{ service.meeting_point }}}}</dd></div>{{% endif %}}\n'
    f'          {{% if service.cancellation_policy %}}<div id="glance-cancellation" class="sm:col-span-2"><dt {DT}>{{% trans "Cancellation" %}}</dt><dd {DD}>{{{{ service.cancellation_policy }}}}</dd></div>{{% endif %}}\n'
    '        </dl>\n'
    '      </section>\n'
    '      {% endif %}\n\n'
    '      {# Highlights #}\n',
)

# 3. The description gets its heading.
once(
    '      <section class="py-8 border-b border-border">\n'
    '        <div class="prose-pdp text-foreground leading-7 space-y-4">{{ text|listing_text }}</div>',
    '      <section id="about" class="py-8 border-b border-border">\n'
    '        <h2 class="text-xl font-semibold text-foreground mb-6">{% if service.listing_kind == \'product\' %}{% trans "About this product" %}{% else %}{% trans "About this experience" %}{% endif %}</h2>\n'
    '        <div class="prose-pdp text-foreground leading-7 space-y-4">{{ text|listing_text }}</div>',
)

# 4. Where you'll be names the meeting point when the listing has one.
once(
    '        <p class="text-sm text-muted-foreground mt-3">{% trans "Exact meeting point details are provided after booking." %}</p>',
    '        {% if service.meeting_point %}<p id="meeting-point" class="text-sm text-foreground mt-3"><span class="font-medium">{% trans "Meeting point" %}:</span> {{ service.meeting_point }}</p>'
    '{% else %}<p class="text-sm text-muted-foreground mt-3">{% trans "Exact meeting point details are provided after booking." %}</p>{% endif %}',
)

# 5. Guest questions move into the reading flow, before the reviews; "Things to know"
#    goes (its three facts are At a glance now).
start, end = s.index('  <!-- Guest questions (FAQ) -->'), s.index('  <!-- Meet your host -->')
s = s[:start] + s[end:]
start, end = s.index('      <!-- Things to know -->'), s.index('      <!-- Reviews -->')
FAQ = (
    '      <!-- Guest questions: in the reading flow, before the reviews -->\n'
    '      {% if service.faqs %}\n'
    '      <section id="guest-questions" class="py-8 border-b border-border">\n'
    '        <h2 class="text-xl font-semibold text-foreground mb-6">{% trans "Guest questions" %}</h2>\n'
    '        <div class="border-y border-border divide-y divide-border">\n'
    '          {% for f in service.faqs %}\n'
    '          <details class="group py-4">\n'
    '            <summary class="flex items-center justify-between gap-4 cursor-pointer list-none font-medium text-foreground">\n'
    '              {{ f.q }}\n'
    '              <svg class="w-4 h-4 text-muted-foreground shrink-0 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>\n'
    '            </summary>\n'
    '            <p class="text-sm text-muted-foreground leading-relaxed mt-3">{{ f.a }}</p>\n'
    '          </details>\n'
    '          {% endfor %}\n'
    '        </div>\n'
    '      </section>\n'
    '      {% endif %}\n\n'
)
s = s[:start] + FAQ + s[end:]

# 6. Reviews: an anchor, and the heading's rating from verified reviews (as the title line).
once('      <!-- Reviews -->\n      <section class="py-8">', '      <!-- Reviews -->\n      <section id="reviews" class="py-8">')
once('{% if review_summary.count %}<span class="inline-flex', '{% if vr.0 %}<span id="reviews-rating" class="inline-flex')
once(
    '{{ review_summary.avg }} <span class="text-muted-foreground">({{ review_summary.count }})</span>',
    '{{ vr.1 }} <span class="text-muted-foreground">({{ vr.0 }})</span>',
)
p.write_text(s)
```

- [ ] **Step 4: Add the Serbian strings and compile them**

Append to `locale/sr/LC_MESSAGES/django.po`:

```
msgid "At a glance"
msgstr "Ukratko"

msgid "Languages"
msgstr "Jezici"

msgid "About this experience"
msgstr "O ovom doživljaju"
```

Run: `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`
Expected: no output, exit 0. A duplicate msgid fails here; if one of the three already exists, delete the appended copy.

- [ ] **Step 5: Run the tests, expecting a pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_experience_page_structure plugins.installed.booking_marketplace.tests.test_serbian_catalog plugins.installed.booking_marketplace.tests.test_detail_page plugins.installed.booking_marketplace.tests.test_montenegro_storefront_claims`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add themes/library/montenegro/templates/booking_marketplace/detail.html locale/sr/LC_MESSAGES/django.po locale/sr/LC_MESSAGES/django.mo plugins/installed/booking_marketplace/tests/test_experience_page_structure.py
git commit -m "feat(montenegro): experience pages answer first, with the facts at a glance and questions before reviews"
```

---

### Task 3: Places nearby

**Files:**
- Modify: `plugins/installed/booking_marketplace/views.py` (`service_detail`)
- Modify: `themes/library/montenegro/templates/booking_marketplace/detail.html`
- Modify: `locale/sr/LC_MESSAGES/django.po` and `django.mo`
- Create: `plugins/installed/booking_marketplace/tests/test_experience_nearby_places.py`

**Interfaces:**
- Consumes: `stays.nearby_places(obj, *, limit=6)`, which reads `obj.region` and returns active `Place` rows of that region ordered by name.
- Produces: the context key `nearby_places` and the element id `places-nearby`.

- [ ] **Step 1: Write the failing tests**

```python
"""An experience links the destination guides of its region."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor


class ExperienceNearbyPlacesTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            region='kotor',
            location='Kotor',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
        )
        Place.objects.create(name='Perast', slug='perast', region='kotor', summary='A baroque town.')
        Place.objects.create(name='Žabljak', slug='zabljak', region='durmitor')

    def _page(self):
        return self.client.get(f'/bookings/{self.svc.slug}/').content.decode()

    def test_places_in_the_same_region_are_linked(self):
        html = self._page()
        section = html[html.index('id="places-nearby"') :]
        self.assertIn('href="/places/perast/"', section)
        self.assertNotIn('href="/places/zabljak/"', section)

    def test_a_product_listing_links_no_places(self):
        BookableService.objects.filter(pk=self.svc.pk).update(listing_kind='product')
        self.assertNotIn('id="places-nearby"', self._page())
```

- [ ] **Step 2: Run them, expecting a failure**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_experience_nearby_places`
Expected: ERROR `substring not found`.

- [ ] **Step 3: Implement**

In `views.py`, `service_detail`, directly after `ctx['web_story'] = …`:

```python
    # The destination guides of this experience's region: the hub-and-spoke links the
    # stay pages already carry (stays.nearby_places).
    from plugins.installed.booking_marketplace.stays import nearby_places

    ctx['nearby_places'] = (
        nearby_places(service, limit=4) if service.listing_kind != 'product' else []
    )
```

In the theme template, insert before the anchor `</div>\n<script>(function(){var m=document.getElementById('exp-map')` (asserted to occur once):

```html
  <!-- Places nearby: the destination guides of this experience's region -->
  {% if nearby_places %}
  <section id="places-nearby" class="border-t border-border pt-10 mt-10">
    <h2 class="text-xl font-semibold text-foreground mb-6">{% trans "Places nearby" %}</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      {% for pl in nearby_places %}
      <a href="/places/{{ pl.slug }}/" class="group rounded-2xl overflow-hidden border border-border bg-card shadow-card">
        <div class="aspect-[4/3] bg-muted overflow-hidden">{% if pl.image %}<img src="{{ pl.image.url }}" alt="{{ pl.name }}" loading="lazy" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">{% endif %}</div>
        <div class="p-3"><h3 class="font-semibold text-foreground group-hover:text-primary transition-colors line-clamp-1">{{ pl.name }}</h3>{% if pl.summary %}<p class="text-xs text-muted-foreground line-clamp-2 mt-1">{{ pl.summary }}</p>{% endif %}</div>
      </a>
      {% endfor %}
    </div>
  </section>
  {% endif %}
```

Append to the `.po` and compile it as in Task 2:

```
msgid "Places nearby"
msgstr "Mjesta u blizini"
```

- [ ] **Step 4: Run them, expecting a pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_experience_nearby_places plugins.installed.booking_marketplace.tests.test_serbian_catalog`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/booking_marketplace/views.py themes/library/montenegro/templates/booking_marketplace/detail.html locale/sr/LC_MESSAGES/django.po locale/sr/LC_MESSAGES/django.mo plugins/installed/booking_marketplace/tests/test_experience_nearby_places.py
git commit -m "feat(montenegro): an experience links the places of its region"
```

---

### Task 4: Structured data: TouristTrip, and an Offer only when prices show

**Files:**
- Modify: `plugins/installed/booking_marketplace/seo_jsonld.py` (new `_offer` and `_trip_node`; `_product_node` and `experience_nodes` take `with_prices`)
- Modify: `plugins/installed/booking_marketplace/seo.py` (`_entity_nodes` passes `with_prices`)
- Create: `plugins/installed/booking_marketplace/tests/test_experience_trip_jsonld.py`

**Interfaces:**
- Produces:
  - `experience_nodes(service, *, url: str, request=None, with_prices: bool = True) -> list[dict]`
  - `_trip_node(service, *, url: str, request=None, with_prices: bool = True) -> dict`, with `@id` `<url>#trip`.

- [ ] **Step 1: Write the failing tests**

```python
"""TouristTrip and Offer on experience pages, stated only as far as the page shows them."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace import seo_jsonld
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor

_LDJSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def _nodes(html):
    return [n for blob in _LDJSON.findall(html) for n in json.loads(blob).get('@graph', [])]


def _typed(nodes, kind):
    return [n for n in nodes if n.get('@type') == kind]


class ExperienceTripJsonLdTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=self.vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Paddle at dawn.',
            itinerary=[
                {'title': 'Meet at the gate', 'detail': 'Kit and a briefing.'},
                {'title': 'Paddle under the walls', 'detail': ''},
            ],
        )

    def _page_nodes(self):
        return _nodes(self.client.get(f'/bookings/{self.svc.slug}/').content.decode())

    def test_an_experience_is_a_tourist_trip_with_its_itinerary(self):
        trips = _typed(self._page_nodes(), 'TouristTrip')
        self.assertEqual(len(trips), 1)
        steps = trips[0]['itinerary']['itemListElement']
        self.assertEqual(
            [(s['position'], s['name']) for s in steps],
            [(1, 'Meet at the gate'), (2, 'Paddle under the walls')],
        )
        self.assertEqual(steps[0]['description'], 'Kit and a briefing.')
        self.assertNotIn('description', steps[1])
        self.assertEqual(trips[0]['offers']['priceCurrency'], 'EUR')

    def test_a_product_listing_is_no_trip(self):
        BookableService.objects.filter(pk=self.svc.pk).update(listing_kind='product')
        self.assertEqual(_typed(self._page_nodes(), 'TouristTrip'), [])

    @override_settings(BOOKING_LISTING_MODE=True)
    def test_listing_mode_states_no_price(self):
        nodes = self._page_nodes()
        # Nothing for a Product to carry: no offer, no verified rating.
        self.assertEqual(_typed(nodes, 'Product'), [])
        trip = _typed(nodes, 'TouristTrip')[0]
        self.assertNotIn('offers', trip)
        webpage = next(n for n in nodes if str(n.get('@id', '')).endswith('#webpage'))
        self.assertEqual(webpage['mainEntity'], {'@id': trip['@id']})

    def test_the_offer_states_the_listings_currency(self):
        self.svc.price = Money(Decimal('50'), 'USD')
        self.svc.save()
        product = _typed(self._page_nodes(), 'Product')[0]
        self.assertEqual(product['offers']['priceCurrency'], 'USD')

    def test_malformed_steps_are_skipped(self):
        service = BookableService(
            name='X',
            slug='x',
            vendor=self.vendor,
            itinerary=['Meet', {'detail': 'no title'}, {'title': 'Paddle'}],
        )
        node = seo_jsonld._trip_node(service, url='https://x.test/bookings/x/', with_prices=False)
        steps = node['itinerary']['itemListElement']
        self.assertEqual([(s['position'], s['name']) for s in steps], [(1, 'Paddle')])
```

- [ ] **Step 2: Run them, expecting a failure**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_experience_trip_jsonld`
Expected: FAIL (no TouristTrip; `_trip_node` missing).

- [ ] **Step 3: Implement**

In `seo_jsonld.py`, above `_product_node`:

```python
def _offer(service, url: str) -> dict:
    return {
        '@type': 'Offer',
        'price': str(service.price.amount),
        'priceCurrency': str(service.price.currency),
        'availability': 'https://schema.org/InStock',
        'url': url,
    }
```

`_product_node(service, *, url: str, request=None, with_prices=True)`: replace its `node['offers'] = {...}` block with:

```python
    if with_prices:  # listing mode shows "Contact for price": claim none
        node['offers'] = _offer(service, url)
```

Add below `_product_node`:

```python
def _trip_node(service, *, url: str, request=None, with_prices=True) -> dict:
    """TouristTrip: the experience as a trip, its itinerary an ordered list of steps."""
    node = {
        '@type': 'TouristTrip',
        '@id': f'{url}#trip',
        'name': service.name,
        'description': service.short_description or service.description[:300] or service.name,
        'url': url,
        'provider': {'@type': 'Organization', 'name': service.vendor.name},
    }
    if service.image:
        node['image'] = _abs(request, service.image.url)
    steps = [s for s in (service.itinerary or []) if isinstance(s, dict) and s.get('title')]
    if steps:
        node['itinerary'] = {
            '@type': 'ItemList',
            'numberOfItems': len(steps),
            'itemListElement': [
                {
                    '@type': 'ListItem',
                    'position': position,
                    'name': str(step['title']),
                    **({'description': str(step['detail'])} if step.get('detail') else {}),
                }
                for position, step in enumerate(steps, start=1)
            ],
        }
    if with_prices:
        node['offers'] = _offer(service, url)
    return node
```

Replace `experience_nodes`:

```python
def experience_nodes(service, *, url: str, request=None, with_prices=True) -> list[dict]:
    """Product (+ Offer, verified rating), TouristTrip (+ itinerary) and the visible FAQPage.

    The Product is left out when it would carry nothing Google accepts it with (no
    offer in listing mode, no verified rating): the trip is then the page's main entity.
    """
    nodes = []
    product = _product_node(service, url=url, request=request, with_prices=with_prices)
    if any(key in product for key in ('offers', 'aggregateRating', 'review')):
        nodes.append(product)
    if service.listing_kind != 'product':
        nodes.append(_trip_node(service, url=url, request=request, with_prices=with_prices))
    faq = faq_node(getattr(service, 'faqs', None), url)
    if faq:
        nodes.append(faq)
    return nodes
```

In `seo.py` `_entity_nodes`:

```python
    if name == 'detail' and ctx.get('service') is not None:
        return seo_jsonld.experience_nodes(
            ctx['service'], url=url, request=request, with_prices=not ctx.get('listing_mode')
        )
```

- [ ] **Step 4: Run them, expecting a pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_experience_trip_jsonld plugins.installed.booking_marketplace.tests.test_experience_jsonld plugins.installed.booking_marketplace.tests.test_seo_integration plugins.installed.booking_marketplace.tests.test_ai_feed`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/booking_marketplace/seo_jsonld.py plugins/installed/booking_marketplace/seo.py plugins/installed/booking_marketplace/tests/test_experience_trip_jsonld.py
git commit -m "feat(booking): experiences are TouristTrips with their itinerary; offers only where prices show"
```

---

### Task 5: Edit the itinerary and the guest questions in the product editor

**Files:**
- Modify: `plugins/installed/booking_marketplace/product_card.py`
- Modify: `plugins/installed/booking_marketplace/templates/booking_marketplace/_product_form_card.html`
- Test: `plugins/installed/booking_marketplace/tests/test_product_form_card.py`

**Interfaces:**
- Produces:
  - POST keys `booking__itinerary_present`, `booking__itinerary_title` (repeated), `booking__itinerary_detail` (repeated), `booking__faqs_present`, `booking__faqs_q` (repeated) and `booking__faqs_a` (repeated).
  - Card context `itinerary_rows` and `faq_rows`: lists of `(str, str)`.

- [ ] **Step 1: Write the failing tests** (append to `BookingDetailsCardTests`)

```python
    def _save_rows(self, **lists):
        post = QueryDict(mutable=True)
        for key, values in lists.items():
            post.setlist(f'booking__{key}', values)
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        self.svc.refresh_from_db()

    def test_saving_writes_the_itinerary_in_order(self):
        self._save_rows(
            itinerary_present=['1'],
            itinerary_title=['Meet at the gate', '', 'Paddle under the walls'],
            itinerary_detail=['Kit and a briefing.', 'a detail with no step', ''],
        )
        self.assertEqual(
            self.svc.itinerary,
            [
                {'title': 'Meet at the gate', 'detail': 'Kit and a briefing.'},
                {'title': 'Paddle under the walls', 'detail': ''},
            ],
        )

    def test_saving_keeps_only_answered_questions(self):
        self._save_rows(
            faqs_present=['1'],
            faqs_q=['Do I need to swim?', 'Can children come?', ''],
            faqs_a=['A little.', '', 'an answer with no question'],
        )
        self.assertEqual(self.svc.faqs, [{'q': 'Do I need to swim?', 'a': 'A little.'}])

    def test_a_save_without_the_rows_keeps_them(self):
        self.svc.itinerary = [{'title': 'Meet', 'detail': ''}]
        self.svc.faqs = [{'q': 'Swim?', 'a': 'Yes.'}]
        self.svc.save()
        self._save(meeting_point='Kotor Sea Gate')
        self.assertEqual(self.svc.itinerary, [{'title': 'Meet', 'detail': ''}])
        self.assertEqual(self.svc.faqs, [{'q': 'Swim?', 'a': 'Yes.'}])

    def test_the_card_shows_the_rows_and_spares(self):
        self.svc.faqs = [{'q': 'Do I need to swim?', 'a': 'A little.'}]
        self.svc.save()
        self.client.force_login(self.admin)
        html = self.client.get(f'/dashboard/products/{self.product.pk}/').content.decode()
        self.assertIn('value="Do I need to swim?"', html)
        self.assertEqual(html.count('name="booking__faqs_q"'), 4)
        self.assertEqual(html.count('name="booking__itinerary_title"'), 4)
```

- [ ] **Step 2: Run them, expecting a failure**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_product_form_card`
Expected: FAIL (itinerary stays `[]`; the count is 0).

- [ ] **Step 3: Implement**

In `product_card.py`, below `_LINES`:

```python
_PAIRS = {'itinerary': ('title', 'detail'), 'faqs': ('q', 'a')}


def _rows(items, first: str, second: str, *, spare: int = 2, minimum: int = 4):
    """Stored pairs as (first, second) rows, plus empty rows to add more."""
    rows = [
        (str(item.get(first) or ''), str(item.get(second) or ''))
        for item in (items or [])
        if isinstance(item, dict)
    ]
    return rows + [('', '')] * max(spare, minimum - len(rows))
```

In `on_product_form_cards`, add to the card's `context`:

```python
                'itinerary_rows': _rows(listing.itinerary, 'title', 'detail'),
                'faq_rows': _rows(listing.faqs, 'q', 'a'),
```

In `on_product_form_saved`, before the `transaction.atomic()` save:

```python
    for field, (first, second) in _PAIRS.items():
        if not has(f'{field}_present'):
            continue  # an older form without these rows changes nothing
        rows = []
        for one, two in zip(
            post.getlist(f'{PREFIX}{field}_{first}'), post.getlist(f'{PREFIX}{field}_{second}')
        ):
            one, two = one.strip(), two.strip()
            if one and (two or field == 'itinerary'):  # a step needs a title, a question its answer
                rows.append({first: one, second: two})
        setattr(listing, field, rows)
```

In `_product_form_card.html`, insert before the anchor `  <div>\n    <label class="block text-sm font-medium mb-1" for="booking-cancellation">`:

```html
  <fieldset class="space-y-2">
    <legend class="block text-sm font-medium mb-1">Itinerary <span class="font-normal text-xs text-[color:var(--text-muted)]">one step per row, in order; empty rows are dropped</span></legend>
    <input type="hidden" name="booking__itinerary_present" value="1">
    {% for title, detail in itinerary_rows %}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
      <input class="input w-full" name="booking__itinerary_title" value="{{ title }}" maxlength="120" placeholder="Step" aria-label="Step {{ forloop.counter }}">
      <input class="input w-full md:col-span-2" name="booking__itinerary_detail" value="{{ detail }}" maxlength="300" placeholder="What happens" aria-label="Step {{ forloop.counter }}: what happens">
    </div>
    {% endfor %}
  </fieldset>
  <fieldset class="space-y-2">
    <legend class="block text-sm font-medium mb-1">Guest questions <span class="font-normal text-xs text-[color:var(--text-muted)]">shown on the page and to search engines; a question needs its answer</span></legend>
    <input type="hidden" name="booking__faqs_present" value="1">
    {% for q, a in faq_rows %}
    <div class="grid grid-cols-1 gap-2">
      <input class="input w-full" name="booking__faqs_q" value="{{ q }}" maxlength="200" placeholder="Question" aria-label="Question {{ forloop.counter }}">
      <textarea class="input w-full" name="booking__faqs_a" rows="2" placeholder="Answer" aria-label="Answer {{ forloop.counter }}">{{ a }}</textarea>
    </div>
    {% endfor %}
  </fieldset>
```

- [ ] **Step 4: Run them, expecting a pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_product_form_card plugins.installed.admin_dashboard.tests.test_product_form_roundtrip plugins.installed.booking_marketplace.tests.test_serbian_catalog`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/booking_marketplace/product_card.py plugins/installed/booking_marketplace/templates/booking_marketplace/_product_form_card.html plugins/installed/booking_marketplace/tests/test_product_form_card.py
git commit -m "feat(booking): the product editor edits an experience's itinerary and guest questions"
```

---

### Task 6: `apply_listing_content`, a backed-up and restorable content import

**Files:**
- Create: `plugins/installed/booking_marketplace/content.py`
- Create: `plugins/installed/booking_marketplace/management/commands/apply_listing_content.py`
- Create: `plugins/installed/booking_marketplace/tests/test_apply_listing_content.py`

**Interfaces:**
- Consumes: `products.plain_text`, and `PRODUCT_UPDATED` (fired by `Product.save()`, copies onto the listing).
- Produces:
  - `content.validate(data) -> list[str]`
  - `content.snapshot(data) -> dict`
  - `content.apply(data) -> int`
  - Command: `manage.py apply_listing_content <file> [--backup <file>] [--dry-run]`

  The input and backup shape is documented in `content.py`'s docstring.

- [ ] **Step 1: Write the failing tests**

```python
"""apply_listing_content: validated, backed up, written to product, listing and SEO, restorable."""

from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.catalog.models import Category, Product, Vendor

NEW = {
    'kayak-the-bay': {
        'name': 'Sunrise Kayak under the Walls of Kotor',
        'short_description': 'Two calm hours on the water at dawn & no experience needed.',
        'description': '<p>Paddle <strong>under the walls</strong>.</p><h3>Who it suits</h3><p>Beginners.</p>',
        'category': 'water-sports',
        'seo_title': 'Sunrise Kayak Tour in Kotor Bay',
        'seo_description': 'A two-hour sunrise kayak under the walls of Kotor, for beginners.',
        'highlights': ['Calm water at dawn', 'Small group'],
        'itinerary': [{'title': 'Meet at the Sea Gate', 'detail': 'Kit and a briefing.'}],
        'faqs': [{'q': 'Do I need to swim?', 'a': 'A little; you wear a buoyancy vest.'}],
    }
}


class ApplyListingContentTests(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        Category.objects.create(name='Water Sports', slug='water-sports')
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Paddle the bay.',
            description='Paddle the bay.',
            highlights=['Caves'],
            faqs=[{'q': 'Kids?', 'a': 'From 8.'}],
        )
        self.product = ensure_product(self.svc)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def _run(self, data, *args):
        path = self.dir / 'content.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        out = StringIO()
        call_command('apply_listing_content', str(path), *args, stdout=out)
        return out.getvalue()

    def _meta(self):
        from plugins.installed.seo.models import SeoMeta

        return SeoMeta.objects.filter(
            content_type=ContentType.objects.get_for_model(Product), object_id=str(self.product.pk)
        ).first()

    def test_a_dry_run_writes_nothing(self):
        self.assertIn('would write 1 listing', self._run(NEW, '--dry-run'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Kayak the bay')

    def test_a_real_run_needs_a_backup(self):
        with self.assertRaisesMessage(CommandError, '--backup'):
            self._run(NEW)

    def test_problems_stop_the_run_before_any_write(self):
        bad = {
            'kayak-the-bay': {
                **NEW['kayak-the-bay'],
                'faqs': [{'q': 'Kids?', 'a': ''}],
                'short_description': 'word ' * 80,
            },
            'no-such-listing': {'name': 'Ghost'},
        }
        with self.assertRaises(CommandError) as caught:
            self._run(bad, '--backup', str(self.dir / 'b.json'))
        for fragment in ('no-such-listing: no listing with a product', 'faqs must be', 'short_description is'):
            self.assertIn(fragment, str(caught.exception))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Kayak the bay')
        self.assertFalse((self.dir / 'b.json').exists())

    def test_it_writes_the_product_the_listing_and_the_seo_row(self):
        self._run(NEW, '--backup', str(self.dir / 'b.json'))
        self.product.refresh_from_db()
        self.svc.refresh_from_db()
        self.assertEqual(self.product.name, 'Sunrise Kayak under the Walls of Kotor')
        self.assertIn('<strong>under the walls</strong>', self.product.description)
        self.assertEqual(self.product.category.slug, 'water-sports')
        self.assertEqual(self.svc.name, 'Sunrise Kayak under the Walls of Kotor')
        self.assertNotIn('<', self.svc.description)
        self.assertEqual(
            self.svc.short_description, 'Two calm hours on the water at dawn & no experience needed.'
        )
        self.assertEqual(self.svc.category.slug, 'water-sports')
        self.assertEqual(self.svc.itinerary, NEW['kayak-the-bay']['itinerary'])
        self.assertEqual(self.svc.faqs, NEW['kayak-the-bay']['faqs'])
        meta = self._meta()
        self.assertEqual((meta.title, meta.auto_filled), ('Sunrise Kayak Tour in Kotor Bay', False))
        self.assertEqual(meta.provenance.get('title'), 'ai')
        html = self.client.get('/bookings/kayak-the-bay/').content.decode()
        self.assertIn('<title>Sunrise Kayak Tour in Kotor Bay', html)

    def test_the_backup_puts_everything_back(self):
        old = self._meta()
        before = (getattr(old, 'title', ''), getattr(old, 'auto_filled', True))
        backup = self.dir / 'b.json'
        self._run(NEW, '--backup', str(backup))
        self._run(json.loads(backup.read_text()), '--backup', str(self.dir / 'b2.json'))
        self.product.refresh_from_db()
        self.svc.refresh_from_db()
        self.assertEqual(self.product.name, 'Kayak the bay')
        self.assertEqual(self.product.description, 'Paddle the bay.')
        self.assertIsNone(self.product.category_id)
        self.assertEqual(self.svc.highlights, ['Caves'])
        self.assertEqual(self.svc.itinerary, [])
        self.assertEqual(self.svc.faqs, [{'q': 'Kids?', 'a': 'From 8.'}])
        meta = self._meta()
        self.assertEqual((meta.title, meta.auto_filled), before)
```

- [ ] **Step 2: Run them, expecting a failure**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_apply_listing_content`
Expected: ERROR `Unknown command: 'apply_listing_content'`.

- [ ] **Step 3: Implement `content.py`**

```python
"""Write content to listings and their Products, with a backup that restores it.

The input maps a listing slug to the fields to write; every field is optional:

    {"<slug>": {
        "name": "…", "short_description": "…", "description": "<p>…</p>",
        "category": "<category slug>",
        "seo_title": "…", "seo_description": "…",
        "highlights": ["…"], "what_to_bring": ["…"],
        "itinerary": [{"title": "…", "detail": "…"}],
        "faqs": [{"q": "…", "a": "…"}],
        "seo_auto_filled": false, "seo_provenance": {"title": "ai"}
    }}

Product owns the name, the texts and the category (PRODUCT_UPDATED copies them onto
the listing); the listing owns its booking lists; the product's SeoMeta row holds the
SEO title and description. `snapshot()` returns the current values of exactly the
fields an input writes, in the same shape, so applying a backup restores it.
"""

from __future__ import annotations

from django.db import transaction

PRODUCT_FIELDS = ('name', 'short_description', 'description')
LIST_FIELDS = ('highlights', 'what_to_bring')
PAIR_FIELDS = {'itinerary': ('title', 'detail'), 'faqs': ('q', 'a')}
SEO_FIELDS = {'seo_title': 'title', 'seo_description': 'description'}
FIELDS = {
    *PRODUCT_FIELDS,
    *LIST_FIELDS,
    *PAIR_FIELDS,
    *SEO_FIELDS,
    'category',
    'seo_auto_filled',
    'seo_provenance',
}
LIMITS = {'name': 200, 'short_description': 300, 'seo_title': 200, 'seo_description': 320}


def _text_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _pairs(value, first: str, second: str, *, both: bool) -> bool:
    if not isinstance(value, list):
        return False
    for row in value:
        if not (isinstance(row, dict) and set(row) <= {first, second}):
            return False
        one, two = row.get(first), row.get(second, '')
        if not (isinstance(one, str) and one.strip() and isinstance(two, str)):
            return False
        if both and not two.strip():
            return False
    return True


def validate(data) -> list[str]:
    """Every problem with an input, or []: nothing is written while any remain."""
    from plugins.installed.booking_marketplace.models import BookableService
    from plugins.installed.booking_marketplace.products import plain_text
    from plugins.installed.catalog.models import Category

    if not isinstance(data, dict) or not data:
        return ['the file must map listing slugs to their fields']
    linked = set(
        BookableService.objects.filter(slug__in=list(data), product__isnull=False).values_list(
            'slug', flat=True
        )
    )
    categories = set(Category.objects.values_list('slug', flat=True))
    problems = []
    for slug, fields in data.items():
        if slug not in linked:
            problems.append(f'{slug}: no listing with a product')
            continue
        if not isinstance(fields, dict):
            problems.append(f'{slug}: the fields must be an object')
            continue
        problems += [f'{slug}: unknown field {key!r}' for key in sorted(set(fields) - FIELDS)]
        for key in (*PRODUCT_FIELDS, *SEO_FIELDS):
            if key in fields and not isinstance(fields[key], str):
                problems.append(f'{slug}: {key} must be text')
        if isinstance(fields.get('name'), str) and not fields['name'].strip():
            problems.append(f'{slug}: name is empty')
        for key, limit in LIMITS.items():
            value = fields.get(key)
            if isinstance(value, str):
                size = len(plain_text(value)) if key == 'short_description' else len(value)
                if size > limit:
                    problems.append(f'{slug}: {key} is {size} characters, over {limit}')
        for key in LIST_FIELDS:
            if key in fields and not _text_list(fields[key]):
                problems.append(f'{slug}: {key} must be a list of text')
        for key, (first, second) in PAIR_FIELDS.items():
            if key in fields and not _pairs(fields[key], first, second, both=key == 'faqs'):
                problems.append(f'{slug}: {key} must be a list of {first}/{second} rows')
        category = fields.get('category')
        if 'category' in fields and category is not None and category not in categories:
            problems.append(f'{slug}: unknown category {category!r}')
        if 'seo_auto_filled' in fields and not isinstance(fields['seo_auto_filled'], bool):
            problems.append(f'{slug}: seo_auto_filled must be true or false')
        if 'seo_provenance' in fields and not isinstance(fields['seo_provenance'], dict):
            problems.append(f'{slug}: seo_provenance must be an object')
    return problems


def _seo_row(product, *, create: bool = False):
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.seo.models import SeoMeta

    lookup = {
        'content_type': ContentType.objects.get_for_model(type(product)),
        'object_id': str(product.pk),
    }
    if create:
        return SeoMeta.objects.get_or_create(**lookup)[0]
    return SeoMeta.objects.filter(**lookup).first()


def snapshot(data) -> dict:
    """The current values of exactly the fields `data` writes, in the input's shape."""
    from plugins.installed.booking_marketplace.models import BookableService

    backup = {}
    for service in BookableService.objects.filter(slug__in=list(data)).select_related(
        'product__category'
    ):
        fields, product, current = data[service.slug], service.product, {}
        for key in PRODUCT_FIELDS:
            if key in fields:
                current[key] = getattr(product, key)
        for key in (*LIST_FIELDS, *PAIR_FIELDS):
            if key in fields:
                current[key] = getattr(service, key)
        if 'category' in fields:
            current['category'] = product.category.slug if product.category_id else None
        if any(key in fields for key in SEO_FIELDS):
            meta = _seo_row(product)
            for key, column in SEO_FIELDS.items():
                current[key] = getattr(meta, column, '') if meta else ''
            current['seo_auto_filled'] = bool(meta.auto_filled) if meta else True
            current['seo_provenance'] = dict(meta.provenance or {}) if meta else {}
        backup[service.slug] = current
    return backup


@transaction.atomic
def apply(data) -> int:
    """Write a validated input; returns the number of listings written."""
    from plugins.installed.booking_marketplace.models import BookableService
    from plugins.installed.catalog.models import Category

    written = 0
    for service in BookableService.objects.filter(slug__in=list(data)).select_related('product'):
        fields, product = data[service.slug], service.product
        for key in PRODUCT_FIELDS:
            if key in fields:
                setattr(product, key, fields[key])
        if 'category' in fields:
            slug = fields['category']
            product.category = Category.objects.get(slug=slug) if slug else None
        product.save()  # PRODUCT_UPDATED copies the name, texts and category onto the listing
        service.refresh_from_db()
        lists = [key for key in (*LIST_FIELDS, *PAIR_FIELDS) if key in fields]
        for key in lists:
            setattr(service, key, fields[key])
        if lists:
            service.save(update_fields=lists)
        if any(key in fields for key in SEO_FIELDS):
            meta = _seo_row(product, create=True)
            origin = dict(meta.provenance or {})
            for key, column in SEO_FIELDS.items():
                if key in fields:
                    setattr(meta, column, fields[key])
                    origin[column] = 'ai'
            meta.auto_filled = fields.get('seo_auto_filled', False)
            meta.provenance = fields.get('seo_provenance', origin)
            meta.save()
        written += 1
    return written
```

- [ ] **Step 4: Implement the command**

```python
"""Write listing content from a JSON file, backing up what it replaces first."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Write content (names, texts, SEO, highlights, itinerary, guest questions) to listings '
        'and their products. The backup holds the current values in the same shape: apply it '
        'to restore them.'
    )

    def add_arguments(self, parser):
        parser.add_argument('file', help='JSON mapping a listing slug to its fields')
        parser.add_argument('--backup', help='Where to write the current values first')
        parser.add_argument('--dry-run', action='store_true', help='Validate and report only')

    def handle(self, *args, **options):
        from plugins.installed.booking_marketplace import content

        path = options['file']
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Cannot read {path}: {exc}') from exc
        problems = content.validate(data)
        if problems:
            raise CommandError(
                f'{len(problems)} problem(s), nothing written:\n' + '\n'.join(problems)
            )
        if options['dry_run']:
            self.stdout.write(f'would write {len(data)} listing(s)')
            return
        backup = options['backup']
        if not backup:
            raise CommandError('--backup <file> is required for a real run (or use --dry-run)')
        try:
            Path(backup).write_text(
                json.dumps(content.snapshot(data), ensure_ascii=False, indent=1), encoding='utf-8'
            )
        except OSError as exc:
            raise CommandError(f'Cannot write the backup {backup}: {exc}') from exc
        written = content.apply(data)
        self.stdout.write(f'written={written} backup={backup}')
```

- [ ] **Step 5: Run them, expecting a pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_apply_listing_content plugins.installed.booking_marketplace.tests.test_link_command`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/booking_marketplace/content.py plugins/installed/booking_marketplace/management/commands/apply_listing_content.py plugins/installed/booking_marketplace/tests/test_apply_listing_content.py
git commit -m "feat(booking): apply_listing_content writes listing copy with a backup that restores it"
```

---

### Task 7: Docs, release, deploy, live structure check

**Files:**
- Modify: `CLAUDE.md` (the vertical-extends-Product convention: one sentence on the column clip)
- Modify: `docs/plans/booking-extends-product-2026-10.md` (status line)

- [ ] **Step 1: Docs**

In CLAUDE.md, after "…a listing save writes text back only when it changed, or a price edit strips the formatting.", add: "The listing's copies are clipped to their columns (`products._listing_copy`): Product allows a longer name and an unlimited summary, Postgres refuses the rest, and sqlite never does." Add `test_experience_page_structure.py`, `test_experience_trip_jsonld.py` and `test_apply_listing_content.py` to that paragraph's "Guarded by". Under the spec's "Then, on that structure" heading add: "Status (2026-10-14): the page structure and the import command shipped in v0.110.0; content per `docs/superpowers/plans/2026-10-14-experience-pages-seo-and-content.md` Tasks 8–9."

- [ ] **Step 2: The combined suites**

Run: `$TEST plugins.installed.booking_marketplace plugins.installed.admin_dashboard plugins.installed.catalog plugins.installed.seo plugins.installed.storefront plugins.installed.webstories themes > "$S/suite.log" 2>&1; grep -E "^Ran |^OK|^FAILED|^(ERROR|FAIL):" "$S/suite.log"`
Expected: `OK`.

- [ ] **Step 3: Gates, then release**

Run every gate in Global Constraints. Expected: all clean.

```bash
.venv/bin/python manage.py release --minor "Experience pages answer first" \
  -m "Every experience page opens with a short answer of what, where, how long and for whom, then the facts at a glance: duration, group size, languages, meeting point, cancellation." \
  -m "Guest questions sit in the page before the reviews; each experience links the places of its region; the Reviews heading rates only reviews from a real booking." \
  -m "Search engines see each experience as a trip with its itinerary, and a price only where the page shows one." \
  -m "The product editor edits an experience's itinerary and guest questions." \
  -m "A long name or summary typed in the product editor no longer stops the experience page from updating." \
  --commit
```

- [ ] **Step 4: Deploy and check the live page**

Run: `git push -q origin main && SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh v0.110.0`
Expected: `SMOKE OK — every store serves v0.110.0`.

Then: `curl -s "https://montenegro-experience.me/bookings/catamaran-day-charter-tivat/?cb=$RANDOM" | grep -o 'id="\(experience-summary\|at-a-glance\|guest-questions\|reviews\|places-nearby\)"' | sort -u`
Expected: all five ids.

---

### Task 8: Write the content (brief, validator, parallel writers)

**Files (scratchpad, not committed):** `S=/private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/experiences`: `dump.py`, `listings.json`, `split.py`, `group_A..F.json`, `BRIEF.md`, `validate.py`, `out/`, `merge.py`, `content.json`.

- [ ] **Step 1: Dump the live listings**

`$S/dump.py`:

```python
import json
from plugins.installed.booking_marketplace.models import REGIONS, BookableService, Place
from plugins.installed.booking_marketplace.products import plain_text
from plugins.installed.catalog.models import Category

regions = dict(REGIONS)
places = {}
for place in Place.objects.filter(is_active=True).order_by('name'):
    places.setdefault(place.region, []).append({'slug': place.slug, 'name': place.name})
rows = []
for s in BookableService.objects.select_related('product__category', 'vendor').order_by('region', 'slug'):
    p = s.product
    rows.append({
        'slug': s.slug, 'kind': s.listing_kind, 'name': p.name,
        'short_description': plain_text(p.short_description), 'description': plain_text(p.description),
        'category': p.category.slug if p.category_id else None,
        'category_name': p.category.name if p.category_id else None,
        'region': s.region, 'region_label': str(regions.get(s.region, '')), 'location': s.location,
        'duration_label': s.duration_label, 'duration_minutes': s.duration_minutes,
        'max_guests_per_booking': s.max_guests_per_booking, 'languages': s.languages,
        'meeting_point': s.meeting_point, 'cancellation_policy': s.cancellation_policy,
        'included': s.included, 'not_included': s.not_included, 'highlights': s.highlights,
        'what_to_bring': s.what_to_bring, 'itinerary': s.itinerary, 'faqs': s.faqs,
        'host': s.vendor.name, 'places_nearby': places.get(s.region, [])[:8],
    })
for row in rows:
    row['related'] = [
        {'slug': o['slug'], 'name': o['name']}
        for o in rows
        if o['region'] == row['region'] and o['slug'] != row['slug'] and o['kind'] == 'experience'
    ][:6]
cats = [
    {'slug': c.slug, 'name': c.name}
    for c in Category.objects.filter(products__booking__isnull=False).distinct().order_by('name')
]
print('JSONSTART' + json.dumps({'listings': rows, 'categories': cats}, ensure_ascii=False, default=str) + 'JSONEND')
```

Run: `~/.ssh/tetra-ssh.sh "docker exec -i <web> python manage.py shell" < $S/dump.py | sed -n 's/.*JSONSTART\(.*\)JSONEND.*/\1/p' > $S/listings.json && python3 -c "import json;d=json.load(open('$S/listings.json'));print(len(d['listings']))"`. Find `<web>` first with `~/.ssh/tetra-ssh.sh "docker ps --format '{{.Names}}' | grep '^web-fo8rvcg94bmcyi43e8iq9tvm'"`.
Expected: `142`.

- [ ] **Step 2: Split into six groups**

`$S/split.py`:

```python
import json, math

data = json.load(open('listings.json', encoding='utf-8'))
allowed = sorted(c['slug'] for c in data['categories'] if c['name'] != 'Books')
experiences = [r for r in data['listings'] if r['kind'] == 'experience']
goods = [r for r in data['listings'] if r['kind'] == 'product']
slugs = sorted(r['slug'] for r in experiences)
size = math.ceil(len(experiences) / 5)
groups = {chr(65 + i): experiences[i * size : (i + 1) * size] for i in range(5)}
groups['F'] = goods
for name, members in groups.items():
    with open(f'group_{name}.json', 'w', encoding='utf-8') as fh:
        json.dump({'allowed_categories': allowed, 'all_listing_slugs': slugs, 'listings': members}, fh, ensure_ascii=False, indent=1)
    print(name, len(members))
```

Run: `cd $S && python3 split.py`
Expected: `A 25`, `B 25`, `C 25`, `D 25`, `E 25` and `F 17`.

- [ ] **Step 3: Write `$S/BRIEF.md`**

````markdown
# Montenegro Experience: listing copy

montenegro-experience.me is a marketplace of experiences (tours, activities, classes, boat
charters, wellness) and local goods across Montenegro, booked with local hosts. You are
rewriting the listings in your group file so each page answers a traveller's questions fast,
reads as if an expert local guide wrote it, and ranks for what people search
("kayak tour Kotor", "Tara rafting from Žabljak").

Each listing gives you its FACTS (name, kind, location, region, duration, group size,
languages, meeting point, included, not included, what to bring, cancellation policy, host)
and its CURRENT TEXT (description, highlights, itinerary, FAQs). Facts are the store's
commitments: never change them and never add new ones.

## The facts rule (most important)
- Never state or imply anything outside the facts on these points:
  - a price, currency amount or discount;
  - a duration, distance, time of day, group size, age limit or language;
  - what is included (food, drinks, transfers, equipment, tickets, photos, guiding) beyond `included`;
  - a meeting place beyond `meeting_point`;
  - refund, weather or rescheduling terms beyond `cancellation_policy`;
  - licences, certifications, insurance, awards, safety records, review scores, "family-run", years in business, or the host's personal story.
- You may use public knowledge of the place: geography, history, architecture, nature,
  seasons, food and wine traditions, what a visitor sees. Keep it accurate and checkable;
  when unsure, leave it out.
- If a fact a traveller wants is missing (meeting point, languages), never fill it in; the
  FAQ about it says to confirm with the host when enquiring.

## Voice
- An experienced local guide writing for an informed traveller: specific, warm, calm, precise.
  Never salesy. British English spelling (favourite, travellers, colour).
- Short paragraphs of 2–4 sentences. Concrete nouns: place names, the water, the stone, the dishes.
- Never use: unforgettable, breathtaking, stunning, hidden gem, nestled, must-see, must-do,
  once-in-a-lifetime, bucket list, paradise, magical, delve, embark, tapestry, boast(s),
  seamless, "whether you're", "look no further", best, ultimate, guarantee(d), 100%,
  world-class, top-rated, award-winning, "book now", the € sign, exclamation marks.
- At most 3 em dashes per description; prefer commas and full stops.

## Experiences (kind "experience")
- `name`: what and where, 10–70 characters, keeping the activity of the current name.
  Example: "Sea Kayaking under the Walls of Kotor".
- `short_description`: the answer-first summary shown under the title and quoted by answer
  engines. One or two sentences, 25–45 words, plain text (no HTML), at most 280 characters:
  what you do, where, how long (from the facts) and who it suits.
- `description`: HTML, 300–500 words.
  1. Open with a `<p>` of 2–3 sentences: the experience in its place, not repeating the summary.
  2. Then 2–4 `<h3>` sections, each with `<p>` and at most one `<ul>`. Suggested headings:
     "What you'll see", "How it runs" (only from the facts and itinerary), "Who it suits",
     "Good to know" (season, conditions, what to expect physically).
  3. Optionally add up to 3 links, only to `places_nearby` (`<a href="/places/<slug>/">Name</a>`)
     or to `related` listings (`<a href="/bookings/<slug>/">Name</a>`).

  Allowed tags: p, h3, ul, ol, li, strong, em, a, br. No h1/h2, classes or styles.
- `seo_title`: 30–60 characters, the search phrase first ("Tara River Rafting from Žabljak,
  Durmitor"). Never the store name; it is added automatically.
- `seo_description`: 120–155 characters, the place, the activity and one concrete reason to choose it.
- `highlights`: 4–6 items, each at most 80 characters and specific ("Swim stop at the Blue
  Cave", not "Great views").
- `itinerary`: 3–6 steps `{"title", "detail"}`, title at most 50 characters, detail at most
  160, in the order the experience runs, built only from the facts and current text. No
  clock times or durations unless the facts give them.
- `faqs`: 5–7 `{"q", "a"}` specific to THIS experience. Each question ends with "?", each
  answer is 15–70 words. Cover what people ask before booking:
  - fitness or skill needed;
  - children (general guidance only, unless the facts say more);
  - what to wear or bring (from `what_to_bring`);
  - weather (keep the meaning of the current answer and the cancellation policy, add nothing);
  - languages (only from the facts, else "confirm with the host when you enquire");
  - getting to the start (only from `meeting_point`).
- `category`: only when the current category is "Books" or clearly wrong, one slug from
  `allowed_categories`. Otherwise leave the key out.

## Goods (kind "product")
- `short_description`: 15–35 words, plain text.
- `description`: HTML, 120–220 words: what it is, the Montenegrin tradition behind it (public
  knowledge), how to use or enjoy it. No claims about the maker, materials, size, weight,
  village of origin or ingredients beyond the current text. Same allowed tags; no h3 needed.
- `seo_title` and `seo_description`: as above.
- Do not write `name`, `highlights`, `itinerary` or `faqs` for goods.

## Output
Write one JSON file `out/<G>.json`: an object mapping each slug in your group to its fields.
Then run the validator and fix every FAIL until it prints `PROBLEMS 0`:

    python3 validate.py out/<G>.json group_<G>.json
````

- [ ] **Step 4: Write `$S/validate.py`**

```python
"""Validate a writer's output: python3 validate.py out/<G>.json group_<G>.json"""
import json, re, sys
from html.parser import HTMLParser

out = json.load(open(sys.argv[1], encoding='utf-8'))
group = json.load(open(sys.argv[2], encoding='utf-8'))
listings = {row['slug']: row for row in group['listings']}
allowed_categories = set(group['allowed_categories'])
booking_slugs = set(group['all_listing_slugs'])
ALLOWED = {'p', 'h3', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'br'}
BANNED = [r'unforgettable', r'breathtaking', r'stunning', r'hidden gem', r'nestled', r'must[- ]see',
          r'must[- ]do', r'once[- ]in[- ]a[- ]lifetime', r'bucket[- ]list', r'paradise', r'magical',
          r'\bdelve', r'\bembark', r'tapestry', r'\bboasts?\b', r'seamless', r"whether you.re",
          r'look no further', r'\bbest\b', r'\bultimate\b', r'guarantee', r'100\s?%', r'world[- ]class',
          r'top[- ]rated', r'award[- ]winning', r'€', r'\bEUR\b', r'book now', r'!']
LANGS = r'\b(English|Italian|German|French|Russian|Serbian|Montenegrin|Spanish)\b'
EXPERIENCE = {'name', 'short_description', 'description', 'seo_title', 'seo_description',
              'highlights', 'itinerary', 'faqs'}
GOODS = {'short_description', 'description', 'seo_title', 'seo_description'}


class Parse(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.links, self.bad_attrs, self.h3 = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.h3 += tag == 'h3'
        for key, value in attrs:
            if tag == 'a' and key == 'href':
                self.links.append(value or '')
            else:
                self.bad_attrs.append(f'{tag}[{key}]')


def words(text):
    return len(re.findall(r"[\w'’-]+", re.sub(r'<[^>]+>', ' ', text or '')))


problems = 0
missing, extra = set(listings) - set(out), set(out) - set(listings)
if missing or extra:
    print('KEYS missing', sorted(missing), 'extra', sorted(extra))
    problems += 1
for slug, fields in out.items():
    if slug not in listings:
        continue
    row, issues = listings[slug], []
    kind = row['kind']
    want = EXPERIENCE if kind == 'experience' else GOODS
    if set(fields) - want - {'category'}:
        issues.append(f'unexpected {sorted(set(fields) - want - {"category"})}')
    if want - set(fields):
        issues.append(f'missing {sorted(want - set(fields))}')
    html = fields.get('description', '')
    parsed = Parse()
    parsed.feed(html)
    if set(parsed.tags) - ALLOWED:
        issues.append(f'tags {sorted(set(parsed.tags) - ALLOWED)}')
    if parsed.bad_attrs:
        issues.append(f'attributes {sorted(set(parsed.bad_attrs))}')
    n = words(html)
    lo, hi = (300, 520) if kind == 'experience' else (120, 230)
    if not lo <= n <= hi:
        issues.append(f'description {n} words, want {lo}-{hi}')
    if kind == 'experience' and not 2 <= parsed.h3 <= 4:
        issues.append(f'{parsed.h3} <h3>, want 2-4')
    places = {p['slug'] for p in row.get('places_nearby', [])}
    if len(parsed.links) > 3:
        issues.append(f'{len(parsed.links)} links, max 3')
    for href in parsed.links:
        m = re.fullmatch(r'/(places|bookings)/([a-z0-9-]+)/', href)
        ok = m and (
            (m.group(1) == 'places' and m.group(2) in places)
            or (m.group(1) == 'bookings' and m.group(2) in booking_slugs and m.group(2) != slug)
        )
        if not ok:
            issues.append(f'link {href}')
    if html.count('—') > 3:
        issues.append(f'{html.count("—")} em dashes')
    short = fields.get('short_description', '')
    lo, hi = (25, 45) if kind == 'experience' else (15, 35)
    if '<' in short:
        issues.append('short_description has HTML')
    if not lo <= words(short) <= hi:
        issues.append(f'short_description {words(short)} words, want {lo}-{hi}')
    if len(short) > 280:
        issues.append(f'short_description {len(short)} characters, max 280')
    title, desc = fields.get('seo_title', ''), fields.get('seo_description', '')
    if not 30 <= len(title) <= 60:
        issues.append(f'seo_title {len(title)} characters, want 30-60')
    if 'Montenegro Experience' in title:
        issues.append('seo_title carries the store name')
    if not 120 <= len(desc) <= 155:
        issues.append(f'seo_description {len(desc)} characters, want 120-155')
    if kind == 'experience':
        name = fields.get('name', '')
        if not 10 <= len(name) <= 70:
            issues.append(f'name {len(name)} characters, want 10-70')
        hl = fields.get('highlights', [])
        if not (isinstance(hl, list) and 4 <= len(hl) <= 6 and all(isinstance(h, str) and 0 < len(h) <= 80 for h in hl)):
            issues.append('highlights: 4-6 items of 1-80 characters')
        it = fields.get('itinerary', [])
        if not (isinstance(it, list) and 3 <= len(it) <= 6 and all(
                isinstance(s, dict) and set(s) == {'title', 'detail'}
                and 0 < len(s['title']) <= 50 and 0 < len(s['detail']) <= 160 for s in it)):
            issues.append('itinerary: 3-6 steps of {title <=50, detail <=160}')
        fq = fields.get('faqs', [])
        if not (isinstance(fq, list) and 5 <= len(fq) <= 7 and all(
                isinstance(f, dict) and set(f) == {'q', 'a'} and f['q'].strip().endswith('?')
                and 15 <= words(f['a']) <= 70 for f in fq)):
            issues.append('faqs: 5-7 of {q ending "?", a of 15-70 words}')
        if not row.get('languages') and isinstance(fq, list):
            if any(isinstance(f, dict) and re.search(LANGS, f.get('a', '')) for f in fq):
                issues.append('an answer names a language the listing does not list')
    blob = ' '.join(json.dumps(v, ensure_ascii=False) for v in fields.values())
    policy = (row.get('cancellation_policy') or '').lower()
    if 'free cancellation' in blob.lower() and 'free cancellation' not in policy:
        issues.append('claims free cancellation the policy does not state')
    if 'category' in fields and fields['category'] not in allowed_categories:
        issues.append(f'category {fields["category"]!r} not allowed')
    hits = [pat for pat in BANNED if re.search(pat, blob, re.I)]
    if hits:
        issues.append(f'banned {hits}')
    if issues:
        problems += 1
        print(f'FAIL {slug}:', '; '.join(issues))
    else:
        print(f'ok   {slug} ({n}w)')
print('PROBLEMS', problems)
```

Run a smoke check with an empty output: `cd $S && mkdir -p out && echo '{}' > out/T.json && python3 validate.py out/T.json group_F.json | tail -1 && rm out/T.json`
Expected: `PROBLEMS 1` (missing keys).

- [ ] **Step 5: Dispatch the writers, three at a time**

Use six Agent calls (`general-purpose`, the session model), A–C together, then D–F. Each prompt:

"You are writing listing copy for montenegro-experience.me. Work in `<$S>`. Read BRIEF.md in full, then group_<G>.json. Write out/<G>.json covering every listing in the group, following the brief exactly; the facts rule outranks everything else. Run `python3 validate.py out/<G>.json group_<G>.json` and fix every FAIL until it prints PROBLEMS 0. Reply with only the PROBLEMS line and the number of listings written."

Expected: each reply ends `PROBLEMS 0`.

- [ ] **Step 6: Quality gate (read before anything goes live)**

Read 12 entries: 2 from each group, including one of the 20 flagship listings without an itinerary and two goods. Compare each with its facts in `group_<G>.json` against this checklist:
- no fact added (inclusions, times, distances, languages, meeting place, policy);
- the summary answers what, where, how long and for whom;
- the copy is specific to the place;
- each FAQ fits the listing;
- the tone matches the brief.

If a group fails, send that writer one follow-up naming the slugs and the exact problems, then re-validate.

- [ ] **Step 7: Merge and validate everything**

`$S/merge.py`:

```python
import glob, json

merged = {}
for path in sorted(glob.glob('out/*.json')):
    merged.update(json.load(open(path, encoding='utf-8')))
json.dump(merged, open('content.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('listings', len(merged))
```

Run: `cd $S && for g in A B C D E F; do python3 validate.py out/$g.json group_$g.json | tail -1; done && python3 merge.py`
Expected: six lines of `PROBLEMS 0`, then `listings 142`.

---

### Task 9: Apply live and verify

- [ ] **Step 1: Back up the database**

Run: `~/.ssh/tetra-ssh.sh "docker ps --format '{{.Names}}' | grep fo8rvcg94bmcyi43e8iq9tvm"` to get the `web-…` and `db-…` (postgres) container names.
Then: `~/.ssh/tetra-ssh.sh "docker exec <db> sh -c 'pg_dump -U \"\$POSTGRES_USER\" -Fc \"\$POSTGRES_DB\"' > /root/content-backups/montenegro-db-before-content-20261014.dump && ls -la /root/content-backups/montenegro-db-before-content-20261014.dump"`
Expected: a file of several MB.

- [ ] **Step 2: Dry run, then the real run**

```bash
~/.ssh/tetra-ssh.sh "docker exec -i <web> sh -c 'cat > /tmp/content.json'" < $S/content.json
~/.ssh/tetra-ssh.sh "docker exec <web> python manage.py apply_listing_content /tmp/content.json --dry-run" | tail -2
```
Expected: `would write 142 listing(s)`.

```bash
~/.ssh/tetra-ssh.sh "docker exec <web> python manage.py apply_listing_content /tmp/content.json --backup /tmp/montenegro-listings-before-content.json" | tail -2
~/.ssh/tetra-ssh.sh "docker cp <web>:/tmp/montenegro-listings-before-content.json /root/content-backups/montenegro-listings-before-content-20261014.json && ls -la /root/content-backups/ | tail -3"
```
Expected: `written=142 backup=…`, and the backup file is copied.

- [ ] **Step 3: Stories**

Run: `~/.ssh/tetra-ssh.sh "docker exec <web> python manage.py backfill_webstories --help"`. If it has a rebuild or force option, run it with that option; if not, confirm on two `/story/<slug>/` pages that the new text shows (stories rebuild on product save and heal on view).

- [ ] **Step 4: Verify every page**

`$S/verify.py` (piped into `manage.py shell` in the web container):

```python
import json, re
from django.test import Client
from plugins.installed.booking_marketplace.models import BookableService
c = Client(secure=True, HTTP_X_FORWARDED_PROTO='https', HTTP_HOST='montenegro-experience.me', HTTP_USER_AGENT='Mozilla/5.0 verify')
content = json.load(open('/tmp/content.json', encoding='utf-8'))
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
bad = []
for s in BookableService.objects.select_related('product'):
    want = content.get(s.slug, {})
    r = c.get(f'/bookings/{s.slug}/')
    html = r.content.decode()
    nodes = [n for blob in LD.findall(html) for n in json.loads(blob).get('@graph', [])]
    types = {n.get('@type') for n in nodes}
    title = re.search(r'<title>(.*?)</title>', html, re.S).group(1)
    checks = {
        'status': r.status_code == 200,
        'title': title.startswith(want.get('seo_title', '')[:30]),
        'summary': 'id="experience-summary"' in html,
        'escaped': '&lt;p&gt;' not in html and '&amp;amp;' not in html,
    }
    if s.listing_kind == 'experience':
        faq = next((n for n in nodes if n.get('@type') == 'FAQPage'), {})
        checks |= {
            'glance': 'id="at-a-glance"' in html,
            'trip': 'TouristTrip' in types,
            'faq': len(faq.get('mainEntity', [])) == len(s.faqs),
        }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        bad.append((s.slug, failed))
print('checked', BookableService.objects.count(), 'failed', len(bad))
for row in bad[:20]:
    print(row)
```

Run: `~/.ssh/tetra-ssh.sh "docker exec -i <web> python manage.py shell" < $S/verify.py | tail -5`
Expected: `checked 142 failed 0`.

- [ ] **Step 5: Look at one page**

With the chrome-devtools MCP, open `https://montenegro-experience.me/bookings/catamaran-day-charter-tivat/?cb=<n>` at 1280 px and at 390 px, take a screenshot of each and read them. Check:
- the summary under the title;
- the At a glance block;
- the question accordion before the reviews;
- the places row;
- no horizontal scroll at 390 px.

- [ ] **Step 6: Record**

Update the memory file `booking-extends-product-v0109.md` with:
- the content run;
- the backup paths;
- the restore command: `apply_listing_content /root/…/montenegro-listings-before-content-20261014.json --backup <new file>`.
