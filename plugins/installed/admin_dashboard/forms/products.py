"""Product + variant create/edit forms."""

# ruff: noqa: PLC0415, I001, B904, PLR5501, PLR0912, PLR0915
# Inline imports are intentional throughout — every clean_* / save
# method only imports the models it needs, keeping form import time
# low and breaking would-be circular deps between admin_dashboard ↔
# catalog. PLR0912 on save() reflects the size of the create+edit
# atomic boundary, not unrelated branches.
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils.text import slugify
from morpheus.app import forms

from ._helpers import _ensure_html, _money


class ProductForm(forms.Form):
    """Create/edit a `catalog.Product`. Variants/images live in their own flows."""

    name = forms.CharField(max_length=300)
    # `slug` is the URL component (/products/<slug>/). Optional in
    # the form — left blank we slugify(name) at save time, matching
    # the historical create flow. When set, the form save updates the
    # row's slug in place.
    slug = forms.SlugField(max_length=300, required=False)
    sku = forms.CharField(max_length=100, required=False)
    status = forms.ChoiceField(
        choices=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ]
    )
    product_type = forms.ChoiceField(
        choices=[
            ('simple', 'Simple'),
            ('variable', 'Variable'),
            ('digital', 'Digital'),
            ('bundle', 'Bundle'),
        ],
        initial='simple',
    )
    # Variable products have a per-variant price, so the parent's `price` is
    # cosmetic — the form-level clean() lets it default to 0 when the user
    # picks Variable. `required=False` here flips the field from "always
    # required" to "validated in clean() based on product_type".
    price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False
    )
    compare_at_price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    cost_price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    short_description = forms.CharField(widget=forms.Textarea, required=False)
    description = forms.CharField(widget=forms.Textarea, required=False)
    category = forms.UUIDField(required=False)
    # Multi-category — Product.additional_categories M2M. The template
    # POSTs `additional_categories` as a list of UUID strings (one per
    # checked checkbox); we parse + validate in clean().
    additional_categories = forms.CharField(required=False, widget=forms.HiddenInput)
    vendor = forms.UUIDField(required=False)
    is_featured = forms.BooleanField(required=False)
    is_taxable = forms.BooleanField(required=False, initial=True)
    track_inventory = forms.BooleanField(required=False, initial=True)
    requires_shipping = forms.BooleanField(required=False, initial=True)
    weight = forms.DecimalField(
        max_digits=8,
        decimal_places=3,
        required=False,
        min_value=Decimal('0'),
    )
    weight_unit = forms.CharField(max_length=5, required=False, initial='kg')

    # Digital products: file upload + delivery toggles. Only persisted
    # when product_type == 'digital'; the front-end hides this section
    # for non-digital products.
    digital_file = forms.FileField(required=False)
    digital_file_clear = forms.BooleanField(required=False)

    # NO SEO fields here any more. Title, description, focus keyword, canonical,
    # Open Graph, Twitter and the robots flags are edited in the SEO card the seo
    # app contributes through PRODUCT_FORM_CARDS, and stored on SeoMeta — which
    # already outranked these columns at render time, so a merchant could type a
    # meta title here and watch the storefront ignore it. The columns survive for
    # one release and are read as a fallback (seo.services.panel).
    #
    # They were `required=False` and written unconditionally in save(), so
    # leaving the fields while dropping the template block would have blanked
    # every product's SEO on the next save. The two go together, always.
    # ── SEO — extra structured data (JSON; loose-typed for flexibility) ─
    # Stays for now: it is the one SEO field with real validation, and the
    # structured-data work that gives it a proper home is the next phase.
    structured_data = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text='Optional JSON object merged into auto-generated JSON-LD.',
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            import json

            kwargs['initial'] = {
                'name': instance.name,
                'slug': instance.slug,
                'sku': instance.sku,
                'status': instance.status,
                'product_type': instance.product_type,
                'price': instance.price.amount if instance.price else None,
                'compare_at_price': (
                    instance.compare_at_price.amount if instance.compare_at_price else None
                ),
                'cost_price': (instance.cost_price.amount if instance.cost_price else None),
                # TipTap stores HTML; legacy rows from populate_descriptions
                # are Markdown — convert on read so the editor renders them.
                'short_description': _ensure_html(instance.short_description),
                'description': _ensure_html(instance.description),
                'category': instance.category_id,
                'additional_categories': ','.join(
                    str(c) for c in instance.additional_categories.values_list('pk', flat=True)
                ),
                'vendor': instance.vendor_id,
                'is_featured': instance.is_featured,
                'is_taxable': instance.is_taxable,
                'track_inventory': instance.track_inventory,
                'requires_shipping': instance.requires_shipping,
                'weight': instance.weight,
                'weight_unit': instance.weight_unit,
                # SEO lives in the contributed SEO card now — see above.
                'structured_data': (
                    json.dumps(instance.structured_data, indent=2)
                    if getattr(instance, 'structured_data', None)
                    else ''
                ),
            }
        super().__init__(*args, **kwargs)

    def clean_structured_data(self):
        raw = (self.cleaned_data.get('structured_data') or '').strip()
        if not raw:
            return {}
        import json

        try:
            value = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f'Not valid JSON: {e}')
        if not isinstance(value, dict):
            raise forms.ValidationError('Structured data must be a JSON object.')
        return value

    def clean_sku(self):
        sku = (self.cleaned_data.get('sku') or '').strip()
        if not sku:
            return ''
        from plugins.installed.catalog.models import Product

        qs = Product.objects.filter(sku=sku)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another product already uses this SKU.')
        return sku

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip()
        if not slug:
            return ''
        from plugins.installed.catalog.models import Product

        qs = Product.objects.filter(slug=slug)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('That URL slug is already used by another product.')
        return slug

    def clean(self):
        """Variable products: per-variant price/weight/shipping is canonical.
        The parent product's pricing/inventory/shipping fields are hidden in
        the UI and irrelevant at the model level, so we let them slide and
        default the required `price` to 0 instead of failing validation.
        """
        cleaned = super().clean()
        product_type = (cleaned.get('product_type') or '').strip()
        if product_type == 'variable':
            if not cleaned.get('price'):
                cleaned['price'] = Decimal('0')
        else:
            # Simple / digital / bundle still need a real price.
            if cleaned.get('price') is None:
                self.add_error('price', 'Price is required for this product type.')
        return cleaned

    def save(self) -> Any:
        from plugins.installed.catalog.models import Product, Category, Vendor

        cd = self.cleaned_data
        product = self.instance or Product()
        product.name = cd['name']
        product.sku = cd['sku'] or ''
        product.status = cd['status']
        product.product_type = cd['product_type']
        product.price = _money(cd['price']) or product.price
        product.compare_at_price = _money(cd.get('compare_at_price'))
        product.cost_price = _money(cd.get('cost_price'))
        product.short_description = cd.get('short_description') or ''
        product.description = cd.get('description') or ''
        product.is_featured = bool(cd.get('is_featured'))
        product.is_taxable = bool(cd.get('is_taxable'))
        product.track_inventory = bool(cd.get('track_inventory'))
        product.requires_shipping = bool(cd.get('requires_shipping'))
        product.weight = cd.get('weight')
        product.weight_unit = cd.get('weight_unit') or 'kg'

        # The SEO columns are NOT written here any more. They used to be
        # assigned unconditionally from cleaned_data, which meant any POST that
        # did not carry them — and after the SEO card moved into the seo app,
        # that is every POST — blanked them. They are now read-only fallbacks;
        # the SEO card writes SeoMeta via PRODUCT_FORM_SAVED.
        if hasattr(product, 'structured_data'):
            product.structured_data = cd.get('structured_data') or {}

        if cd.get('category'):
            product.category = Category.objects.filter(pk=cd['category']).first()
        else:
            product.category = None
        if cd.get('vendor'):
            product.vendor = Vendor.objects.filter(pk=cd['vendor']).first()
        else:
            product.vendor = None

        # Digital products don't ship — force the related flags off so a
        # merchant can't accidentally save a digital product as needing
        # shipping (and so tax/shipping calculation paths skip them).
        if cd['product_type'] == 'digital':
            product.requires_shipping = False
            product.weight = None
            product.weight_unit = ''

        # Digital file: upload, clear, or leave alone. Only meaningful
        # when the product is digital — otherwise we ignore it (so
        # toggling type doesn't unexpectedly drop the file).
        if hasattr(product, 'digital_file') and cd['product_type'] == 'digital':
            if cd.get('digital_file_clear'):
                if product.digital_file:
                    product.digital_file.delete(save=False)
                product.digital_file = None
            new_file = self.files.get('digital_file') if hasattr(self, 'files') else None
            if new_file:
                product.digital_file = new_file

        # Slug: explicit form value wins; on create, fall back to a
        # slugified product name. On edit with no value supplied, the
        # existing slug stays untouched (we don't auto-replace it from
        # the name, otherwise renaming a product would silently break
        # its URL and every inbound link).
        new_slug = (cd.get('slug') or '').strip()
        if new_slug:
            product.slug = new_slug
        elif not product.slug:
            product.slug = slugify(product.name)[:300] or 'product'
        product.save()

        # Multi-category — the template POSTs a comma-separated list of
        # UUIDs (one per checked checkbox). Set the M2M after save() so
        # we have a pk on create.
        raw_additional = (cd.get('additional_categories') or '').strip()
        if raw_additional:
            ids = [s.strip() for s in raw_additional.split(',') if s.strip()]
            valid = list(Category.objects.filter(pk__in=ids).values_list('pk', flat=True))
            product.additional_categories.set(valid)
        else:
            product.additional_categories.clear()

        return product


class VariantForm(forms.Form):
    """Create/edit a `catalog.ProductVariant` for a given product.

    Surfaces the six Shopify-parity fields (commit b74aaf9 +
    migration 0010_variant_shopify_parity): variant_type,
    requires_shipping, is_taxable, inventory_policy, barcode,
    digital_file.
    """

    VARIANT_TYPE_CHOICES = [
        ('physical', 'Physical — ships to a customer address'),
        ('digital', 'Digital — downloadable file'),
        ('virtual', 'Virtual — service / gift card / booking, no shipment'),
    ]
    INVENTORY_POLICY_CHOICES = [
        ('deny', 'Deny — refuse orders when out of stock'),
        ('continue', 'Continue — accept backorders'),
    ]

    name = forms.CharField(max_length=200)
    sku = forms.CharField(max_length=100)
    size = forms.CharField(max_length=50, required=False)
    short_description = forms.CharField(widget=forms.Textarea, required=False)
    description = forms.CharField(widget=forms.Textarea, required=False)
    price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    compare_at_price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    cost_price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    weight = forms.DecimalField(
        max_digits=8,
        decimal_places=3,
        required=False,
        min_value=Decimal('0'),
    )
    # Shopify-parity fields.
    variant_type = forms.ChoiceField(
        choices=VARIANT_TYPE_CHOICES,
        initial='physical',
        required=False,
    )
    requires_shipping = forms.BooleanField(required=False, initial=True)
    is_taxable = forms.BooleanField(required=False, initial=True)
    inventory_policy = forms.ChoiceField(
        choices=INVENTORY_POLICY_CHOICES,
        initial='deny',
        required=False,
    )
    barcode = forms.CharField(max_length=50, required=False)
    digital_file = forms.FileField(required=False)
    digital_file_clear = forms.BooleanField(required=False)
    # Per-variant image. Uploading creates a ProductImage row on the
    # parent product and points variant.image (FK → ProductImage) at
    # it, so the storefront variant picker can show each edition's own
    # cover. Blank leaves the existing image; image_clear detaches it.
    image = forms.ImageField(required=False)
    image_clear = forms.BooleanField(required=False)

    is_active = forms.BooleanField(required=False, initial=True)
    sort_order = forms.IntegerField(required=False, min_value=0, initial=0)

    def __init__(self, *args, instance=None, product=None, **kwargs):
        self.instance = instance
        self.product = product or (instance.product if instance else None)
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'name': instance.name,
                'sku': instance.sku,
                'size': getattr(instance, 'size', '') or '',
                'short_description': getattr(instance, 'short_description', '') or '',
                'description': getattr(instance, 'description', '') or '',
                'price': instance.price.amount if instance.price else None,
                'compare_at_price': (
                    instance.compare_at_price.amount if instance.compare_at_price else None
                ),
                'cost_price': (instance.cost_price.amount if instance.cost_price else None),
                'weight': instance.weight,
                'variant_type': getattr(instance, 'variant_type', 'physical'),
                'requires_shipping': getattr(instance, 'requires_shipping', True),
                'is_taxable': getattr(instance, 'is_taxable', True),
                'inventory_policy': getattr(instance, 'inventory_policy', 'deny'),
                'barcode': getattr(instance, 'barcode', ''),
                'is_active': instance.is_active,
                'sort_order': instance.sort_order,
            }
        super().__init__(*args, **kwargs)

    def clean_sku(self):
        sku = self.cleaned_data['sku'].strip()
        from plugins.installed.catalog.models import ProductVariant

        qs = ProductVariant.objects.filter(sku=sku)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another variant already uses this SKU.')
        return sku

    def clean(self):
        cleaned = super().clean()
        vt = cleaned.get('variant_type') or 'physical'
        # Auto-flip requires_shipping based on variant_type when the
        # merchant didn't explicitly set the checkbox. Digital + virtual
        # default to no shipping; physical defaults to requires shipping.
        if 'requires_shipping' not in self.data:
            cleaned['requires_shipping'] = vt == 'physical'
        return cleaned

    def save(self) -> Any:
        from plugins.installed.catalog.models import ProductVariant

        if self.product is None:
            raise ValueError('VariantForm.save() requires a product.')

        cd = self.cleaned_data
        variant = self.instance or ProductVariant(product=self.product)
        variant.name = cd['name']
        variant.sku = cd['sku']
        variant.size = (cd.get('size') or '').strip()
        variant.short_description = (cd.get('short_description') or '').strip()
        variant.description = (cd.get('description') or '').strip()
        variant.price = _money(cd.get('price'))
        variant.compare_at_price = _money(cd.get('compare_at_price'))
        variant.cost_price = _money(cd.get('cost_price'))
        variant.weight = cd.get('weight')
        variant.variant_type = cd.get('variant_type') or 'physical'
        variant.requires_shipping = bool(cd.get('requires_shipping'))
        variant.is_taxable = bool(cd.get('is_taxable'))
        variant.inventory_policy = cd.get('inventory_policy') or 'deny'
        variant.barcode = (cd.get('barcode') or '').strip()
        variant.is_active = bool(cd.get('is_active'))
        variant.sort_order = cd.get('sort_order') or 0
        # FileField needs explicit save with the upload, not direct assignment.
        # The order matters: a clear+upload in one POST should land on the new
        # file, not on an empty slot. Process clear first, then upload.
        if cd.get('digital_file_clear') and variant.digital_file:
            variant.digital_file.delete(save=False)
            variant.digital_file = None
        upload = cd.get('digital_file')
        if upload:
            variant.digital_file.save(upload.name, upload, save=False)

        # Per-variant image. clear first, then a fresh upload wins. The
        # uploaded file becomes a ProductImage on the parent product
        # (is_primary=False, high sort_order so it doesn't disturb the
        # product's own gallery ordering) and variant.image points at it.
        if cd.get('image_clear'):
            variant.image = None
        img_upload = cd.get('image')
        if img_upload:
            from plugins.installed.catalog.models import ProductImage

            pi = ProductImage(
                product=self.product,
                alt_text=(variant.name or self.product.name or '')[:255],
                is_primary=False,
                sort_order=900,
            )
            pi.image.save(img_upload.name, img_upload, save=True)
            variant.image = pi

        variant.save()
        return variant
