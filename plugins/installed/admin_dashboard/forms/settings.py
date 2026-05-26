"""Store-settings forms (Settings → General / Notifications)."""
from __future__ import annotations

from morpheus import forms

from ._helpers import DashboardFormMixin


class StoreGeneralForm(DashboardFormMixin, forms.Form):
    """Editable subset of `core.StoreSettings` shown under Settings → General."""

    store_name = forms.CharField(max_length=200)
    store_description = forms.CharField(widget=forms.Textarea, required=False)
    primary_currency = forms.CharField(max_length=3)
    country = forms.CharField(max_length=2)
    timezone = forms.CharField(max_length=50, required=False)
    contact_email = forms.EmailField(required=False)
    support_phone = forms.CharField(max_length=30, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                f: getattr(instance, f, '')
                for f in (
                    'store_name', 'store_description', 'primary_currency',
                    'country', 'timezone', 'contact_email', 'support_phone',
                )
            }
        super().__init__(*args, **kwargs)

    def save(self):
        from core.models import StoreSettings
        instance = self.instance or StoreSettings.objects.first() or StoreSettings()
        for field, value in self.cleaned_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class StoreNotificationsForm(DashboardFormMixin, forms.Form):
    """SMTP / outbound email — under Settings → Notifications."""

    default_from_email = forms.CharField(max_length=200, required=False)
    smtp_host = forms.CharField(max_length=200, required=False)
    smtp_port = forms.IntegerField(min_value=1, required=False, initial=587)
    smtp_user = forms.CharField(max_length=200, required=False)
    smtp_password = forms.CharField(max_length=200, required=False, widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                f: getattr(instance, f, '')
                for f in ('default_from_email', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password')
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
