"""The vendor form: one set of rules for the dashboard and for Linda."""

from __future__ import annotations

from django import forms
from django.urls import Resolver404, resolve
from django.utils.text import slugify

from plugins.installed.catalog.models import Vendor


class VendorForm(forms.ModelForm):
    """A vendor's name, web address, description, logo and status.

    A changed address keeps the old one working: seo's slug watcher 301s
    /vendor/<old>/ to the new one, whatever saves the vendor. An address the
    vendor portal itself answers (/vendor/me/, /vendor/apply/) is refused, or the
    vendor's page could never be reached.
    """

    class Meta:
        model = Vendor
        fields = ['name', 'slug', 'description', 'logo', 'is_active']
        labels = {'slug': 'Web address', 'is_active': 'Active'}
        help_texts = {'slug': 'The vendor page is at /vendor/<web address>/.'}
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea)):
                field.widget.attrs.setdefault('class', 'input')

    def clean_slug(self) -> str:
        slug = slugify(self.cleaned_data.get('slug') or '')
        if not slug:
            raise forms.ValidationError('A web address needs at least one letter or number.')
        if Vendor.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another vendor already has this address.')
        try:
            match = resolve(f'/vendor/{slug}/')
        except Resolver404:
            match = None
        if match is not None and match.url_name != 'vendor_detail':
            raise forms.ValidationError('The vendor portal uses this address.')
        return slug
