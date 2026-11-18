"""Replace the seeded accessibility page with the EAA statement (v0.178.0).

Only a page that still holds a seed's own text is replaced (either wording the seed
ever wrote, whatever email it named), so a page the merchant edited stays as it is.
A missing page is the seed's to create (gdpr's post_migrate handler). A page body is
stored through cms's sanitiser, which drops the seed's wrapper and styles, so both
sides are compared as that sanitiser leaves them. Fail-soft, like the seed: a
content hiccup must never stop the production ``migrate``.
"""

import logging
import re

from django.db import migrations

_OLD_SEEDS = (
    # 21456b96 to v0.87.2, then (v0.87.3) without the word "books".
    'We want everyone to be able to browse and buy books here, whatever device or',
    'We want everyone to be able to browse and buy here, whatever device or',
)
_OLD_TEMPLATE = """\
<div class="wrap" style="max-width: 760px;">
<p class="eyebrow">Accessibility</p>

<h3>Our commitment</h3>
<p>{opening}
assistive technology you use. We aim to meet the Web Content Accessibility
Guidelines (WCAG) 2.2 at level AA as a target across the storefront.</p>

<h3>What we do</h3>
<ul style="padding-left:1.5rem; line-height:1.8;">
  <li>Keyboard-navigable menus, dialogs and the cart drawer.</li>
  <li>Visible focus states and labelled form fields.</li>
  <li>Text alternatives for meaningful images and clear colour contrast.</li>
  <li>Respect for your "reduce motion" system setting.</li>
</ul>

<h3>Found a barrier?</h3>
<p>Accessibility is ongoing and we don't always get it right. If something is
hard to use, please tell us at <a href="mailto:{email}">{email}</a> or through our
<a href="/contact/">contact page</a> and we'll fix it as a priority.</p>
</div>"""


_EMAIL = re.compile(r'[^\s"<>:]+@[^\s"<>]+')


def _sanitizer():
    from plugins.installed.cms.models import _sanitize_html

    return _sanitize_html


def _normal(html: str, sanitize) -> str:
    """``html`` as a page stores it, with any email address and spacing made alike."""
    return re.sub(r'\s+', ' ', _EMAIL.sub('EMAIL', sanitize(html or ''))).strip()


def untouched(body: str, sanitize=None) -> bool:
    """Whether ``body`` is a seed's accessibility text, with any email in it."""
    sanitize = sanitize or _sanitizer()
    have = _normal(body, sanitize)
    return any(
        have == _normal(_OLD_TEMPLATE.format(opening=opening, email='seed@example.com'), sanitize)
        for opening in _OLD_SEEDS
    )


def replace_untouched(apps, schema_editor):
    try:
        from plugins.installed.gdpr.services import ACCESSIBILITY_EXCERPT, accessibility_body

        sanitize = _sanitizer()
        Page = apps.get_model('cms', 'Page')
        page = Page.objects.filter(slug='accessibility').first()
        if page is None or not untouched(page.body, sanitize):
            return
        page.body = sanitize(accessibility_body())
        page.excerpt = ACCESSIBILITY_EXCERPT
        page.save(update_fields=['body', 'excerpt', 'updated_at'])
    except Exception:  # noqa: BLE001
        logging.getLogger('morpheus.gdpr').warning(
            'accessibility statement migration skipped', exc_info=True
        )


class Migration(migrations.Migration):
    dependencies = [
        ('gdpr', '0002_seed_legal_pages'),
        ('cms', '0009_emailtemplate_shipment_sent'),
    ]

    operations = [
        migrations.RunPython(replace_untouched, migrations.RunPython.noop),
    ]
