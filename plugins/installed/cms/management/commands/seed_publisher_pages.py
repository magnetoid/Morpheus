"""Seed the publishing-house frontend: 6 CMS pages + 1 submission form.

Pages created (idempotent — re-run safely; existing slugs are left alone
unless ``--force`` overwrites bodies):

  /p/publish-with-us/  — pitch + manuscript submission form
  /p/authors/          — authors index intro
  /p/imprints/         — imprints / series intro
  /p/faq/              — frequently asked questions
  /p/shipping/         — shipping policy
  /p/returns/          — returns policy

The "Publish with us" form is created as a CMS ``Form(key='publish-with-us')``
so submissions land in the dashboard at /dashboard/apps/cms/forms/ alongside
all other lead-capture flows.

Usage:
    python manage.py seed_publisher_pages
    python manage.py seed_publisher_pages --force   # overwrite existing bodies
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


PUBLISH_FORM_FIELDS = [
    {'name': 'title',        'type': 'text',     'label': 'Manuscript title',     'required': True},
    {'name': 'author_name',  'type': 'text',     'label': 'Your name',            'required': True},
    {'name': 'email',        'type': 'email',    'label': 'Email',                'required': True},
    {'name': 'phone',        'type': 'tel',      'label': 'Phone (optional)',     'required': False},
    {'name': 'genre',        'type': 'select',   'label': 'Genre / category',     'required': True,
     'options': [
         {'value': 'fiction',     'label': 'Fiction'},
         {'value': 'nonfiction',  'label': 'Non-fiction'},
         {'value': 'poetry',      'label': 'Poetry'},
         {'value': 'memoir',      'label': 'Memoir'},
         {'value': 'children',    'label': "Children's"},
         {'value': 'academic',    'label': 'Academic'},
         {'value': 'other',       'label': 'Other'},
     ]},
    {'name': 'word_count',   'type': 'number',   'label': 'Approximate word count', 'required': True,
     'placeholder': 'e.g. 80000'},
    {'name': 'synopsis',     'type': 'textarea', 'label': 'Synopsis (200–500 words)', 'required': True,
     'rows': 8, 'placeholder': 'A spoiler-free summary: the premise, the stakes, what makes this book worth reading.'},
    {'name': 'sample_url',   'type': 'url',      'label': 'Sample chapter — link to PDF / Google Doc', 'required': True,
     'placeholder': 'https://drive.google.com/...'},
    {'name': 'bio',          'type': 'textarea', 'label': 'Author bio + previous credits', 'required': False,
     'rows': 5},
    {'name': 'comparable_titles', 'type': 'text', 'label': 'Comparable titles (comp titles)', 'required': False,
     'placeholder': 'e.g. "Convenience Store Woman meets Eileen"'},
]


PUBLISH_PAGE_BODY = """\
<div class="wrap" style="max-width: 760px;">

<p class="eyebrow">For writers</p>
<h2 style="font-family: var(--display, serif); font-size: 1.8rem; margin: .5rem 0 1.5rem;">A small press, reading widely.</h2>

<p>We're an independent publisher with a small list and a long attention span. We publish 8–12 titles a year across literary fiction, non-fiction, and poetry — books that take their form seriously and their reader seriously.</p>

<p>We read every submission. There's no agent gate, no genre prejudice; we'd rather find a book by surprise than by referral. If your manuscript is finished — or close enough that you can show us a strong sample — we want to hear from you.</p>

<h3 style="margin: 2.5rem 0 1rem; font-size: 1.15rem;">What we're looking for</h3>
<ul style="padding-left: 1.5rem; line-height: 1.8;">
  <li>Literary fiction (novels and story collections), 50–120k words</li>
  <li>Narrative non-fiction, essays, criticism, hybrid forms</li>
  <li>Poetry (full collections, 60–100 pages)</li>
  <li>Memoir with a strong frame — biography, place, an idea — rather than chronological autobiography</li>
  <li>Children's and YA — if you have a sense of where your book sits on a shelf</li>
</ul>

<h3 style="margin: 2.5rem 0 1rem; font-size: 1.15rem;">What we're not the right home for</h3>
<ul style="padding-left: 1.5rem; line-height: 1.8;">
  <li>Genre fiction aimed at a wide commercial audience (we admire it; we don't publish it)</li>
  <li>Self-help, business books, cookbooks</li>
  <li>Manuscripts under 30k words (unless it's poetry)</li>
</ul>

<h3 style="margin: 2.5rem 0 1rem; font-size: 1.15rem;">What to send</h3>
<p>The form below collects everything we need on a first pass: title, synopsis, a link to a sample (PDF or Google Doc), a short author bio. Please don't paste the whole manuscript in — we'll ask if we want to read more.</p>

<p>We aim to respond within 8–12 weeks. We read carefully; we say no kindly. If we're a yes we'll be in touch within that window with a real conversation, not a form letter.</p>

<hr style="margin: 3rem 0 2rem; border: 0; border-top: 1px solid var(--rule, #e7e3dc);">

<h3 style="margin: 0 0 1.5rem; font-size: 1.25rem;">Send us your work</h3>

<form method="post" action="/forms/publish-with-us/submit/" class="cms-form publish-form" style="display:grid; gap: 1.2rem;">
  <input type="hidden" name="csrfmiddlewaretoken" value="">
  <div>
    <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Manuscript title *</label>
    <input type="text" name="title" required class="input">
  </div>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
    <div>
      <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Your name *</label>
      <input type="text" name="author_name" required class="input">
    </div>
    <div>
      <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Email *</label>
      <input type="email" name="email" required class="input">
    </div>
  </div>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
    <div>
      <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Genre / category *</label>
      <select name="genre" required class="input">
        <option value="">— choose —</option>
        <option value="fiction">Fiction</option>
        <option value="nonfiction">Non-fiction</option>
        <option value="poetry">Poetry</option>
        <option value="memoir">Memoir</option>
        <option value="children">Children's</option>
        <option value="academic">Academic</option>
        <option value="other">Other</option>
      </select>
    </div>
    <div>
      <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Approximate word count *</label>
      <input type="number" name="word_count" required class="input" placeholder="e.g. 80000">
    </div>
  </div>
  <div>
    <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Synopsis (200–500 words) *</label>
    <textarea name="synopsis" required rows="8" class="input" placeholder="Spoiler-free: premise, stakes, what makes this book worth reading."></textarea>
  </div>
  <div>
    <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Sample chapter — link to PDF or Google Doc *</label>
    <input type="url" name="sample_url" required class="input" placeholder="https://drive.google.com/...">
    <p style="font-size: .8rem; color: var(--muted, #888); margin-top: .35rem;">Please share a read-only link to the first 20–40 pages.</p>
  </div>
  <div>
    <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Author bio + previous credits</label>
    <textarea name="bio" rows="4" class="input"></textarea>
  </div>
  <div>
    <label class="block" style="font-size: .85rem; margin-bottom: .35rem; color: var(--ink-2);">Comparable titles</label>
    <input type="text" name="comparable_titles" class="input" placeholder='e.g. "Convenience Store Woman meets Eileen"'>
  </div>
  <div style="margin-top: 1rem;">
    <button type="submit" class="btn btn-primary" style="padding: .8rem 2rem;">Send submission</button>
    <p style="font-size: .8rem; color: var(--muted, #888); margin-top: .75rem;">By submitting you confirm the work is your own and unpublished, and that we may keep your submission on file for review.</p>
  </div>
</form>

</div>
"""


AUTHORS_PAGE_BODY = """\
<div class="wrap" style="max-width: 760px;">
<p class="eyebrow">Voices on the list</p>
<p style="font-size: 1.1rem; line-height: 1.7;">Every book on our list is a writer first. Some are well-known names; many are debuts. Each has their own page — interviews, full backlist, related reading.</p>
<p style="font-size: 1.05rem; line-height: 1.7;">Browse the full <a href="/products/">catalogue</a> to find a book, then follow the author link on any title to land on that writer's page. We'll be building out a full A–Z index here soon.</p>
<p style="margin-top: 2.5rem; font-size: .95rem;"><strong>Writing yourself?</strong> See our <a href="/p/publish-with-us/">submissions page</a>.</p>
</div>
"""


IMPRINTS_PAGE_BODY = """\
<div class="wrap" style="max-width: 760px;">
<p class="eyebrow">Three lists, one editorial sensibility</p>
<p style="font-size: 1.1rem; line-height: 1.7;">We publish under three imprints — separate identities, shared standards. Use these to navigate the list by mood rather than by genre.</p>

<div style="display: grid; gap: 1.5rem; margin-top: 2.5rem;">
  <div style="padding: 1.5rem; border: 1px solid var(--rule, #e7e3dc); border-radius: 4px;">
    <h3 style="margin: 0 0 .5rem; font-size: 1.15rem;">dot books — the main list</h3>
    <p style="margin: 0; font-size: .95rem; color: var(--ink-2);">Literary fiction and non-fiction. Where most of our titles live.</p>
  </div>
  <div style="padding: 1.5rem; border: 1px solid var(--rule, #e7e3dc); border-radius: 4px;">
    <h3 style="margin: 0 0 .5rem; font-size: 1.15rem;">dot pocket — pocket editions</h3>
    <p style="margin: 0; font-size: .95rem; color: var(--ink-2);">Smaller-format reissues of essays, novellas, and short story collections. Designed to fit in a coat pocket.</p>
  </div>
  <div style="padding: 1.5rem; border: 1px solid var(--rule, #e7e3dc); border-radius: 4px;">
    <h3 style="margin: 0 0 .5rem; font-size: 1.15rem;">dot poetry</h3>
    <p style="margin: 0; font-size: .95rem; color: var(--ink-2);">Full poetry collections from new and established voices, 60–100 pages.</p>
  </div>
</div>
</div>
"""


FAQ_PAGE_BODY = """\
<div class="wrap" style="max-width: 760px;">

<details open style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">When will my order ship?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">In-stock titles ship within 1–2 business days from our warehouse. You'll get a tracking email once it's on its way. See <a href="/p/shipping/">Shipping</a> for delivery windows by region.</p>
</details>

<details style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">Can I return a book?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">Yes — within 30 days of delivery, in resaleable condition. See <a href="/p/returns/">Returns</a> for the full policy and the return form.</p>
</details>

<details style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">Do you ship internationally?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">We ship to most countries. Rates and timing are shown at checkout based on your address.</p>
</details>

<details style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">Do you offer signed copies?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">For select titles, yes — they're tagged on the product page when available. Quantities are limited; once they're gone we can't restock the signed run.</p>
</details>

<details style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">Are your books available as ebooks?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">Most of our list is available in EPUB and PDF on the product page. Each ebook is DRM-free.</p>
</details>

<details style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">I'd like to stock your books in my shop. How?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">We work with independent bookshops directly. Email <a href="mailto:trade@dotbooks.store">trade@dotbooks.store</a> for our trade terms.</p>
</details>

<details style="border-bottom: 1px solid var(--rule, #e7e3dc); padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">Can I submit a manuscript?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;">Yes — see <a href="/p/publish-with-us/">Publish with us</a> for what we're looking for and the submission form.</p>
</details>

<details style="padding: 1.25rem 0;">
  <summary style="cursor: pointer; font-weight: 600; font-size: 1.05rem;">Still need help?</summary>
  <p style="margin: 1rem 0 0; line-height: 1.7;"><a href="/contact/">Drop us a line</a> — we read every message.</p>
</details>

</div>
"""


SHIPPING_PAGE_BODY = """\
<div class="wrap" style="max-width: 720px; font-size: 1.05rem; line-height: 1.7;">

<p class="eyebrow">Getting books to you</p>

<p>Books ship from our warehouse within 1–2 business days. You'll receive a confirmation email with tracking once your order leaves us.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Delivery windows</h3>
<ul style="padding-left: 1.5rem;">
  <li><strong>United Kingdom</strong> — 2–4 working days (Royal Mail Tracked 48)</li>
  <li><strong>European Union</strong> — 4–8 working days</li>
  <li><strong>United States &amp; Canada</strong> — 7–14 working days</li>
  <li><strong>Rest of world</strong> — 10–21 working days</li>
</ul>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Rates</h3>
<p>Shipping is calculated at checkout based on your address and the weight of your order. We offer free UK shipping on orders over £40.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Tracking</h3>
<p>The shipping confirmation email contains your carrier and tracking number. Tracking goes live within a few hours of dispatch.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Customs &amp; duties</h3>
<p>Orders outside the UK may incur import duties on arrival — these are the recipient's responsibility and depend on local rules.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Lost in the post?</h3>
<p>If a parcel hasn't arrived by the upper end of its window, <a href="/contact/">email us</a> with the order number and we'll get it sorted — usually with a replacement on its way the same day.</p>

</div>
"""


RETURNS_PAGE_BODY = """\
<div class="wrap" style="max-width: 720px; font-size: 1.05rem; line-height: 1.7;">

<p class="eyebrow">If a book isn't right</p>

<p>You can return any physical book within <strong>30 days of delivery</strong> for a full refund, as long as it's in resaleable condition: no markings, no creased spine, no obvious shelf-wear.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">How to start a return</h3>
<ol style="padding-left: 1.5rem;">
  <li>Sign in to your <a href="/account/orders/">account</a> and open the order.</li>
  <li>Click <strong>Request a return</strong> and pick the items.</li>
  <li>We email you a prepaid return label and an RMA number.</li>
  <li>Pack the books, attach the label, drop it at any post office.</li>
</ol>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Refunds</h3>
<p>Once we receive and inspect the return (1–3 business days), we refund the card you paid with. Bank processing can add a further 2–7 business days. You'll get an email at every step.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Damaged or wrong item</h3>
<p>If a book arrives damaged or we sent the wrong title, <a href="/contact/">contact us</a> within 7 days with the order number and a photo. We cover return shipping and send a replacement the same day.</p>

<h3 style="margin: 2rem 0 .75rem; font-size: 1.1rem;">Ebooks &amp; signed copies</h3>
<p>Digital downloads are non-refundable once accessed. Signed copies follow the standard 30-day policy except where damage is from over-handling at signing — we'll judge fairly.</p>

</div>
"""


PAGES = [
    ('publish-with-us', 'Publish with us',   'Submissions are open — send us your manuscript.', PUBLISH_PAGE_BODY),
    ('authors',         'Our authors',       'Voices on our list.',                              AUTHORS_PAGE_BODY),
    ('imprints',        'Imprints',          'Three lists, one editorial sensibility.',          IMPRINTS_PAGE_BODY),
    ('faq',             'Frequently asked', 'Everything you need to know.',                      FAQ_PAGE_BODY),
    ('shipping',        'Shipping',          'How and when your books reach you.',               SHIPPING_PAGE_BODY),
    ('returns',         'Returns',           'If a book isn’t right.',                           RETURNS_PAGE_BODY),
]


class Command(BaseCommand):
    help = 'Seed publisher pages + the publish-with-us submission form.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--force', action='store_true',
            help='Overwrite existing page bodies (otherwise existing slugs are left alone).',
        )

    def handle(self, *args, **opts) -> None:
        from plugins.installed.cms.models import Form, Page

        force = bool(opts.get('force'))

        # ── Form ─────────────────────────────────────────────────────────────
        form, created = Form.objects.update_or_create(
            key='publish-with-us',
            defaults={
                'label': 'Publish with us',
                'fields': PUBLISH_FORM_FIELDS,
                'submit_label': 'Send submission',
                'success_message': 'Thanks — we read every submission and respond within 8–12 weeks.',
                'is_active': True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f'{"Created" if created else "Updated"} form: publish-with-us'
        ))

        # ── Pages ────────────────────────────────────────────────────────────
        created_n = updated_n = skipped_n = 0
        for slug, title, excerpt, body in PAGES:
            existing = Page.objects.filter(slug=slug).first()
            if existing and not force:
                skipped_n += 1
                self.stdout.write(f'  skipped (exists): /p/{slug}/')
                continue
            if existing:
                existing.title = title
                existing.excerpt = excerpt
                existing.body = body
                existing.state = 'published'
                existing.save()
                updated_n += 1
                self.stdout.write(f'  updated: /p/{slug}/')
            else:
                Page.objects.create(
                    slug=slug,
                    title=title,
                    excerpt=excerpt,
                    body=body,
                    state='published',
                    layout='long_form',
                )
                created_n += 1
                self.stdout.write(f'  created: /p/{slug}/')

        self.stdout.write(self.style.SUCCESS(
            f'done — created={created_n} updated={updated_n} skipped={skipped_n}'
        ))
