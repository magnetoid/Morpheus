"""Store-settings forms (Settings → General / Notifications)."""

from __future__ import annotations

from morpheus.app import forms

from ._helpers import DashboardFormMixin

# Common storefront languages for the core-language picker. Code is ISO 639-1;
# the core language is served unprefixed, other enabled languages get a /xx/
# URL prefix (see docs/plans/full-localization-2026-06.md).
CORE_LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('fr', 'French — Français'),
    ('de', 'German — Deutsch'),
    ('es', 'Spanish — Español'),
    ('it', 'Italian — Italiano'),
    ('pt', 'Portuguese — Português'),
    ('nl', 'Dutch — Nederlands'),
    ('sr', 'Serbian — Српски'),
    ('ru', 'Russian — Русский'),
    ('pl', 'Polish — Polski'),
    ('tr', 'Turkish — Türkçe'),
    ('ar', 'Arabic — العربية'),
    ('zh-hans', 'Chinese (Simplified) — 简体中文'),
    ('ja', 'Japanese — 日本語'),
]


class StoreGeneralForm(DashboardFormMixin, forms.Form):
    """Editable subset of `core.StoreSettings` shown under Settings → General."""

    store_name = forms.CharField(max_length=200)
    store_description = forms.CharField(widget=forms.Textarea, required=False)
    primary_currency = forms.CharField(max_length=3)
    country = forms.CharField(max_length=2)
    core_language = forms.ChoiceField(
        choices=CORE_LANGUAGE_CHOICES,
        required=False,
        label='Core language',
        help_text='Default storefront language — served without a URL prefix. '
        'Other languages you enable get a prefix (e.g. /fr/, /sr/).',
    )
    timezone = forms.CharField(max_length=50, required=False)
    contact_email = forms.EmailField(required=False)
    support_phone = forms.CharField(max_length=30, required=False)
    product_placeholder_image = forms.ImageField(
        required=False,
        help_text='Shown on the storefront when a product has no image of its own.',
    )
    default_social_image = forms.ImageField(
        required=False,
        help_text='Default social/share (Open Graph) image for pages with no image of their '
        'own. 1200×630 recommended. A per-page or SEO URL override still wins.',
    )
    gdpr_enabled = forms.BooleanField(
        required=False,
        label='GDPR / ePrivacy features',
        help_text='Show the cookie-consent banner and the self-service data '
        'export + account deletion pages. Turn off for stores outside GDPR '
        'jurisdiction (e.g. US-only or B2B).',
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                f: getattr(instance, f, '')
                for f in (
                    'store_name',
                    'store_description',
                    'primary_currency',
                    'country',
                    'core_language',
                    'timezone',
                    'contact_email',
                    'support_phone',
                    'product_placeholder_image',
                    'default_social_image',
                    'gdpr_enabled',
                )
            }
        super().__init__(*args, **kwargs)

    def save(self):
        from core.models import StoreSettings

        instance = self.instance or StoreSettings.objects.first() or StoreSettings()
        for field, value in self.cleaned_data.items():
            # An unchanged file field comes back falsy — don't clobber the
            # stored image with an empty value when no new file was uploaded.
            if field in ('product_placeholder_image', 'default_social_image') and not value:
                continue
            setattr(instance, field, value)
        instance.save()
        # Bust the storefront GDPR-switch cache so the toggle takes effect at
        # once, not after the 60s TTL (Redis survives deploys — see landmine).
        import contextlib

        from django.core.cache import cache

        with contextlib.suppress(Exception):
            cache.delete('morph:gdpr_enabled')
        return instance


class StoreNotificationsForm(DashboardFormMixin, forms.Form):
    """SMTP / outbound email — under Settings → Notifications."""

    default_from_email = forms.CharField(max_length=200, required=False)
    smtp_host = forms.CharField(max_length=200, required=False)
    smtp_port = forms.IntegerField(min_value=1, required=False, initial=587)
    smtp_user = forms.CharField(max_length=200, required=False)
    smtp_password = forms.CharField(
        max_length=200, required=False, widget=forms.PasswordInput(render_value=True)
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                f: getattr(instance, f, '')
                for f in (
                    'default_from_email',
                    'smtp_host',
                    'smtp_port',
                    'smtp_user',
                    'smtp_password',
                )
            }
        super().__init__(*args, **kwargs)

    def save(self):
        from core.models import StoreSettings

        instance = self.instance or StoreSettings.objects.first() or StoreSettings()
        for field, value in self.cleaned_data.items():
            if field == 'smtp_port' and value is None:
                continue
            setattr(instance, field, value)
        instance.save()
        return instance
