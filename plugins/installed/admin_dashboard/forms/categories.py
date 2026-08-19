"""Category create/edit form for the admin dashboard.

A ModelForm over ``catalog.Category`` (an MPTT tree node): name, slug,
parent, description, image (multipart), is_active and sort_order.
SEO is NOT here: it is edited in the card the seo app contributes through
CATEGORY_FORM_CARDS and stored on SeoMeta, so every entity in the platform
shares one editor. The native meta_* columns survive for one release and are
read as a fallback.
Slug auto-fills from the name when left blank and is kept unique. The
``parent`` choices exclude the node itself and all of its descendants so
a merchant can't create a cycle.
"""

from __future__ import annotations

from django import forms
from django.utils.text import slugify

from plugins.installed.catalog.models import Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = [
            'name',
            'slug',
            'parent',
            'description',
            'image',
            'is_active',
            'sort_order',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = '— Top level —'
        # Exclude self + descendants from the parent choices to prevent a
        # cycle (MPTT would raise on save, but we keep it out of the UI).
        parent_qs = Category.objects.all().order_by('tree_id', 'lft')
        if self.instance and self.instance.pk:
            parent_qs = parent_qs.exclude(
                pk__in=self.instance.get_descendants(include_self=True).values_list('pk', flat=True)
            )
        self.fields['parent'].queryset = parent_qs
        for field in self.fields.values():
            if isinstance(
                field.widget, (forms.TextInput, forms.Textarea, forms.NumberInput, forms.Select)
            ):
                field.widget.attrs.setdefault('class', 'input')

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get('slug') or '').strip()
        if not slug:
            slug = slugify(self.cleaned_data.get('name') or self.data.get('name') or '')
        # Reject a duplicate (excluding self) — surfaced as a field error,
        # not a 500/IntegrityError.
        qs = (
            Category.objects.exclude(pk=self.instance.pk)
            if self.instance.pk
            else Category.objects.all()
        )
        if slug and qs.filter(slug=slug).exists():
            raise forms.ValidationError('That slug is already in use. Choose another.')
        return slug

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        if parent and self.instance.pk:
            # Defence in depth — the queryset already excludes these, but a
            # crafted POST could still smuggle a descendant's pk in.
            descendant_pks = set(
                self.instance.get_descendants(include_self=True).values_list('pk', flat=True)
            )
            if parent.pk in descendant_pks:
                raise forms.ValidationError("A category can't be its own parent or descendant.")
        return parent
