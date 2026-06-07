"""CMS models — pages, blocks, menus, forms.

Closes the "ecommerce + CMS = platform" gap. Themes render content via
the resolver:

    /<slug>/        → Page resolver (about, manifesto, returns, etc.)
    {% cms_menu key %}  → render a Menu by key into the storefront nav
    {% cms_block key %} → render a named Block (callouts, banners) anywhere

Pages support draft / scheduled / published states + per-page SEO via
the existing seo plugin's SeoMeta generic FK.
"""

from __future__ import annotations

import uuid

import bleach
from django.conf import settings
from django.utils import timezone

from morpheus import models

# Allowlist for staff-authored HTML in Page.body / PageSection.body. Both fields
# are rendered with `|safe` in storefront templates, so we sanitise on save in
# case a staff session is compromised (persistent XSS otherwise).
_ALLOWED_TAGS = [
    'p',
    'br',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'strong',
    'em',
    'u',
    's',
    'a',
    'ul',
    'ol',
    'li',
    'blockquote',
    'code',
    'pre',
    'img',
    'figure',
    'figcaption',
    'hr',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'iframe',
    'span',
]
_ALLOWED_ATTRS = {
    '*': ['class', 'id'],
    'a': ['href', 'target', 'rel', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading'],
    'iframe': ['src', 'width', 'height', 'allow', 'allowfullscreen', 'title'],
}
_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def _sanitize_html(html: str) -> str:
    """Strip non-allowlisted tags/attrs/protocols from staff-authored HTML."""
    if not html:
        return html
    return bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )


class Page(models.Model):
    """A merchant-editable static page rendered by the storefront."""

    STATE_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    LAYOUT_CHOICES = [
        ('default', 'Default — single column'),
        ('long_form', 'Long form'),
        ('landing', 'Landing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True, help_text='Markdown or HTML — theme decides.')

    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='default')
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='draft', db_index=True)
    publish_at = models.DateTimeField(null=True, blank=True, db_index=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cms_pages',
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'{self.title} ({self.state})'

    def save(self, *args, **kwargs):
        if self.body:
            self.body = _sanitize_html(self.body)
        super().save(*args, **kwargs)

    @property
    def is_live(self) -> bool:
        if self.state != 'published':
            return False
        return not (self.publish_at and self.publish_at > timezone.now())


class PageSection(models.Model):
    """Composable section of a Page.

    Pages can either be rendered classically from `Page.body` (back-compat
    with v1 CMS pages) or composed of ordered `PageSection` rows. The
    storefront's `{% render_page_sections page %}` template tag prefers
    the section path when at least one row exists.

    `section_id` references a Section registered in `themes.sections.
    section_registry` (e.g. 'hero', 'featured_products', 'rich_text').
    `settings` is a free-form JSON dict per the section's declared
    schema; merged on render with the section's `defaults`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='sections')
    section_id = models.CharField(
        max_length=80,
        db_index=True,
        help_text='Identifier registered in themes.sections.section_registry.',
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text='Per-instance settings; merged with the section defaults at render time.',
    )
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['page', 'sort_order']),
        ]

    def __str__(self) -> str:
        return f'{self.section_id} #{self.sort_order} on {self.page.slug}'


class Block(models.Model):
    """Named, reusable content snippet (banner, callout, hero, etc.)."""

    KIND_CHOICES = [
        ('html', 'HTML / Markdown'),
        ('image', 'Image with caption'),
        ('callout', 'Callout / banner'),
        ('cta', 'Call-to-action'),
        ('embed', 'Embed (script / iframe)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(
        max_length=120, unique=True, db_index=True, help_text='Stable key — themes reference this.'
    )
    label = models.CharField(max_length=200, help_text='Human-readable name.')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='html')
    body = models.TextField(blank=True)
    image_url = models.URLField(max_length=600, blank=True)
    cta_label = models.CharField(max_length=100, blank=True)
    cta_url = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['key']

    def __str__(self) -> str:
        return f'{self.label} ({self.key})'


class Menu(models.Model):
    """Named navigation menu (header, footer, mobile)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=80, unique=True, db_index=True)
    label = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self) -> str:
        return self.label


class MenuItem(models.Model):
    """One entry within a Menu.

    ``kind`` lets a storefront render dynamic entries, not just static links:
      - ``link``            — a plain label → url (default).
      - ``mega_categories`` — the Genres mega-menu (driven by nav_categories).
      - ``mega_authors``    — the Authors mega-menu (driven by nav_authors).
    Mega kinds ignore ``url`` (the theme supplies the panel); ``url`` is still
    used as the mega trigger's own href / the mobile-drawer fallback link.
    """

    KIND_LINK = 'link'
    KIND_MEGA_CATEGORIES = 'mega_categories'
    KIND_MEGA_AUTHORS = 'mega_authors'
    KIND_CHOICES = [
        (KIND_LINK, 'Link'),
        (KIND_MEGA_CATEGORIES, 'Genres mega-menu'),
        (KIND_MEGA_AUTHORS, 'Authors mega-menu'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='items')
    label = models.CharField(max_length=120)
    url = models.CharField(max_length=500, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_LINK)
    target = models.CharField(max_length=10, default='_self', blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    order = models.PositiveSmallIntegerField(default=100)
    icon = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['order', 'id']


class Form(models.Model):
    """A merchant-defined form (contact, newsletter, lead-gen).

    Fields are described by a JSON schema-like list:
        [{"name": "email", "type": "email", "required": true, "label": "Email"}]

    Submissions persist as `FormSubmission` rows — also fan out to CRM
    as a Lead + Interaction (the cms plugin's hook on form_submitted).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=80, unique=True, db_index=True)
    label = models.CharField(max_length=200)
    fields = models.JSONField(default=list)
    submit_label = models.CharField(max_length=80, default='Send')
    success_message = models.CharField(max_length=300, default='Thanks — we got your note.')
    notify_email = models.EmailField(
        blank=True, help_text='Optional address that receives a copy of every submission.'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self) -> str:
        return self.label


class FormSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='submissions')
    payload = models.JSONField(default=dict)
    submitter_email = models.EmailField(blank=True, db_index=True)
    submitter_ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['form', '-created_at'])]


class EmailTemplate(models.Model):
    """Merchant-editable transactional email template.

    `key` matches the template-base used by ``core.emails.handlers._send``
    (e.g. 'order_placed', 'order_paid', 'digital_download'). When a row
    exists for a key the in-DB ``subject`` + ``body_text`` (+ optional
    ``body_html``) replace the filesystem default; otherwise the filesystem
    template under ``core/emails/templates/emails/<key>.txt`` is used.

    Bodies are rendered with the Django template engine, so ``{{ order.total }}``,
    ``{% for ... %}``, etc. all work — same syntax merchants already see in
    other CMS templates.
    """

    KEY_CHOICES = [
        ('order_placed', 'Order placed'),
        ('order_paid', 'Order paid'),
        ('order_fulfilled', 'Order fulfilled'),
        ('order_cancelled', 'Order cancelled'),
        ('refund_issued', 'Refund issued'),
        ('digital_download', 'Digital downloads'),
        ('cart_abandoned', 'Cart abandoned'),
        ('welcome', 'Welcome'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=80, unique=True, choices=KEY_CHOICES)
    label = models.CharField(max_length=120)
    subject = models.CharField(max_length=300)
    body_text = models.TextField(help_text='Plain-text body. Django template syntax allowed.')
    body_html = models.TextField(
        blank=True, help_text='Optional HTML body. Falls back to text when blank.'
    )
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label
