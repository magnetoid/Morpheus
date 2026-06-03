"""Collection create/edit form for the admin dashboard.

A ModelForm over ``catalog.Collection`` (metadata + SEO) plus a ``products``
multi-select. ``Product.collections`` is the M2M (Collection.products is the
reverse), so products isn't a model field on Collection — we bind it manually
and ``.set()`` it on save. Slug auto-fills from the name when left blank.
"""

from __future__ import annotations

from django import forms
from django.utils.text import slugify

from plugins.installed.catalog.models import Collection, Product


class CollectionForm(forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.filter(status='active').order_by('name'),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 14, 'class': 'input'}),
        help_text='Products shown on this collection page.',
    )

    class Meta:
        model = Collection
        fields = [
            'name',
            'slug',
            'description',
            'image',
            'is_active',
            'is_featured',
            'sort_order',
            'meta_title',
            'meta_description',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.NumberInput)):
                field.widget.attrs.setdefault('class', 'input')
        if self.instance and self.instance.pk:
            self.fields['products'].initial = self.instance.products.all()

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get('slug') or '').strip()
        if not slug:
            slug = slugify(self.cleaned_data.get('name') or self.data.get('name') or '')
        # Keep it unique (excluding self) — append -2, -3, … if taken.
        base, n = slug, 2
        qs = (
            Collection.objects.exclude(pk=self.instance.pk)
            if self.instance.pk
            else Collection.objects.all()
        )
        while slug and qs.filter(slug=slug).exists():
            slug = f'{base}-{n}'
            n += 1
        return slug

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            obj.products.set(self.cleaned_data.get('products') or [])
        return obj
