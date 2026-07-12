"""GDPR plugin services — the master gate + idempotent legal-page seeding.

`gdpr_required()` mirrors the storefront's old `_gdpr_required()` gate: the
self-service data-rights pages 404 when a merchant outside GDPR jurisdiction
turns the Settings → General → GDPR/ePrivacy master switch off (default ON).

`seed_legal_pages()` creates the Privacy / Terms / Imprint CMS pages if they
are absent. Idempotent — existing slugs are left alone unless `force=True`.
Exposed via the `seed_legal_pages` management command and callable from tests.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.gdpr')


def gdpr_required() -> None:
    """Raise Http404 when the store has turned GDPR features off."""
    from core.models import StoreSettings

    if not StoreSettings.get('gdpr_enabled', True):
        from django.http import Http404

        raise Http404('GDPR features are disabled for this store.')


def _cfg(key: str, default: str) -> str:
    """Read one gdpr-plugin config value (data controller name/email), with a
    placeholder fallback so the seeded pages are always coherent."""
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('gdpr')
        if plugin is not None:
            val = plugin.get_config_value(key, default)
            if val:
                return str(val)
    except Exception:  # noqa: BLE001 — never let config lookup break seeding.
        logger.debug('gdpr._cfg(%s) failed; using default', key, exc_info=True)
    return default


# ── Legal-page copy (EU placeholder) ───────────────────────────────────────
#
# Deliberately names every third party that receives customer personal data,
# because GDPR Art. 13(1)(e) requires disclosing the recipients — including the
# LLM providers reached through the AI assistant, which is easy to forget.

_PRIVACY_BODY = """\
<div class="wrap" style="max-width: 760px;">
<p class="eyebrow">Legal</p>
<p><em>Placeholder policy — review with counsel before you rely on it.</em></p>

<h3>Who we are</h3>
<p>{controller} ("we") is the data controller for the personal data described
below. Questions about your data? Email <a href="mailto:{email}">{email}</a>.</p>

<h3>What we collect</h3>
<p>Account details (name, email, password hash), order and payment history,
shipping/billing addresses, support messages, and — if you consent — analytics
and marketing cookie data. See our cookie banner to review or change consent at
any time.</p>

<h3>Who we share it with (processors)</h3>
<p>We only share what a processor needs to do its job:</p>
<ul style="padding-left:1.5rem; line-height:1.8;">
  <li><strong>Stripe</strong> — payment processing. Card data goes directly to
      Stripe; we never store full card numbers.</li>
  <li><strong>Our email provider (SMTP)</strong> — transactional and, with your
      consent, marketing email.</li>
  <li><strong>Cloudflare</strong> — CDN, DNS and edge security; it processes
      request metadata (including IP) to serve and protect the site.</li>
  <li><strong>AI / LLM providers</strong> — when you use the on-site AI
      assistant, your message and the relevant context are sent to the
      configured large-language-model provider (for example OpenAI, Anthropic
      or Google) to generate a reply. Don't paste anything into the assistant
      you wouldn't want processed by a third party.</li>
</ul>

<h3>Your rights</h3>
<p>Under the GDPR you can access, export, correct, or delete your data, and
withdraw consent. Logged-in customers can do this instantly from
<a href="/account/privacy/">your privacy hub</a>: download a machine-readable
copy of everything we hold (Art. 15) or delete your account (Art. 17). You can
also lodge a complaint with your local supervisory authority.</p>

<h3>Retention</h3>
<p>We keep order records for as long as tax and accounting law requires, then
anonymise them. Everything else is deleted when you close your account.</p>
</div>"""

_TERMS_BODY = """\
<div class="wrap" style="max-width: 760px;">
<p class="eyebrow">Legal</p>
<p><em>Placeholder terms — review with counsel before you rely on them.</em></p>

<h3>Agreement</h3>
<p>By using this store you agree to these terms. If you don't, please don't use
the store.</p>

<h3>Orders &amp; pricing</h3>
<p>All orders are subject to acceptance and availability. Prices include or
exclude VAT as shown at checkout. We may correct pricing errors before we ship.</p>

<h3>Right of withdrawal (EU)</h3>
<p>Consumers in the EU have a 14-day right of withdrawal on eligible goods, as
set out in the Consumer Rights Directive. Digital goods you have started to
download may be excluded once delivery has begun and you have acknowledged the
loss of that right.</p>

<h3>Returns</h3>
<p>See our returns policy for how to send an item back and how refunds are
issued.</p>

<h3>Liability</h3>
<p>Nothing in these terms limits liability that cannot be limited under
applicable law (for example for death or personal injury caused by negligence).</p>

<h3>Contact</h3>
<p>Questions? Email <a href="mailto:{email}">{email}</a>.</p>
</div>"""

_IMPRINT_BODY = """\
<div class="wrap" style="max-width: 760px;">
<p class="eyebrow">Legal</p>
<p><em>Placeholder imprint — required in several EU jurisdictions (e.g. the
German Impressum under §5 DDG). Fill in your real company details.</em></p>

<h3>Operator</h3>
<p>{controller}<br>
[Street address]<br>
[Postal code, City, Country]</p>

<h3>Contact</h3>
<p>Email: <a href="mailto:{email}">{email}</a><br>
Phone: [phone number]</p>

<h3>Registration</h3>
<p>[Company registration number]<br>
[VAT identification number]</p>

<h3>Responsible for content</h3>
<p>[Name of the person responsible for editorial content]</p>
</div>"""


def _pages() -> list[tuple[str, str, str, str]]:
    controller = _cfg('data_controller_name', 'This store')
    email = _cfg('data_controller_email', 'privacy@example.com')
    fmt = {'controller': controller, 'email': email}
    return [
        (
            'privacy',
            'Privacy Policy',
            'How we collect, use and protect your data.',
            _PRIVACY_BODY.format(**fmt),
        ),
        (
            'terms',
            'Terms & Conditions',
            'The terms that govern use of this store.',
            _TERMS_BODY.format(**fmt),
        ),
        ('imprint', 'Imprint', 'Legal operator and contact details.', _IMPRINT_BODY.format(**fmt)),
    ]


def seed_legal_pages(*, force: bool = False) -> dict[str, int]:
    """Create the Privacy / Terms / Imprint CMS pages if absent.

    Idempotent: existing slugs are skipped unless ``force`` overwrites their
    bodies. Returns a {created, updated, skipped} tally.
    """
    from plugins.installed.cms.models import Page

    created = updated = skipped = 0
    for slug, title, excerpt, body in _pages():
        existing = Page.objects.filter(slug=slug).first()
        if existing and not force:
            skipped += 1
            continue
        if existing:
            existing.title = title
            existing.excerpt = excerpt
            existing.body = body
            existing.state = 'published'
            existing.save()
            updated += 1
        else:
            Page.objects.create(
                slug=slug,
                title=title,
                excerpt=excerpt,
                body=body,
                state='published',
                layout='long_form',
            )
            created += 1
    return {'created': created, 'updated': updated, 'skipped': skipped}
