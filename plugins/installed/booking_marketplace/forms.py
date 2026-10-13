"""The dashboard's listing editor (experiences and local goods)."""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils.text import slugify
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService

#: JSON list fields edited as one item per line; languages as a comma list.
_LINE_LISTS = ('highlights', 'included', 'not_included', 'what_to_bring')


class ListingForm(forms.ModelForm):
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    original_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        help_text='Shown struck through beside the price. Leave empty for no discount.',
    )
    languages = forms.CharField(
        required=False, help_text='Comma-separated, e.g. English, Montenegrin.'
    )
    highlights = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 4}), help_text='One per line.'
    )
    included = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text='One per line.'
    )
    not_included = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text='One per line.'
    )
    what_to_bring = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text='One per line.'
    )

    class Meta:
        model = BookableService
        fields = [
            'name',
            'slug',
            'listing_kind',
            'vendor',
            'category',
            'region',
            'location',
            'short_description',
            'description',
            'duration_minutes',
            'duration_label',
            'meeting_point',
            'cancellation_policy',
            'image',
            'is_active',
            'is_bestseller',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 8}),
            'cancellation_policy': forms.Textarea(attrs={'rows': 3}),
            'meeting_point': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {'is_bestseller': 'Top pick', 'listing_kind': 'Type', 'vendor': 'Host'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['vendor'].queryset = self.fields['vendor'].queryset.order_by('name')
        inst = self.instance
        if inst.pk:
            self.initial['price'] = inst.price.amount if inst.price else Decimal('0')
            self.initial['original_price'] = (
                inst.original_price.amount if inst.original_price else None
            )
            self.initial['languages'] = ', '.join(inst.languages or [])
            for name in _LINE_LISTS:
                self.initial[name] = '\n'.join(str(x) for x in (getattr(inst, name) or []))
        for field in self.fields.values():
            if isinstance(
                field.widget, (forms.TextInput, forms.Textarea, forms.NumberInput, forms.Select)
            ):
                field.widget.attrs.setdefault('class', 'input')

    def clean_slug(self):
        slug = slugify(self.cleaned_data.get('slug') or self.cleaned_data.get('name') or '')
        if not slug:
            raise forms.ValidationError('A name or a URL slug is required.')
        clash = BookableService.objects.filter(slug=slug)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError('Another listing already uses this URL slug.')
        return slug

    def save(self, commit=True):
        obj = super().save(commit=False)
        currency = obj.price.currency if obj.price else 'EUR'
        obj.price = Money(self.cleaned_data['price'], currency)
        was = self.cleaned_data.get('original_price')
        obj.original_price = Money(was, currency) if was else None
        obj.languages = [
            s.strip() for s in (self.cleaned_data.get('languages') or '').split(',') if s.strip()
        ]
        for name in _LINE_LISTS:
            raw = self.cleaned_data.get(name) or ''
            setattr(obj, name, [line.strip() for line in raw.splitlines() if line.strip()])
        if commit:
            obj.save()
        return obj
