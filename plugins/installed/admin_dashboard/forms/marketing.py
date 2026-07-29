"""Marketing forms: coupon create/edit."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.plugin import forms

from ._helpers import _money


class CouponForm(forms.Form):
    """Create/edit a `marketing.Coupon`."""

    code = forms.CharField(max_length=50)
    name = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    discount_type = forms.ChoiceField(
        choices=[
            ('percentage', 'Percentage'),
            ('fixed_amount', 'Fixed amount'),
            ('free_shipping', 'Free shipping'),
            ('buy_x_get_y', 'Buy X get Y'),
        ]
    )
    discount_value = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    minimum_order_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    maximum_discount_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    usage_limit = forms.IntegerField(min_value=0, required=False)
    usage_limit_per_customer = forms.IntegerField(min_value=0, required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    starts_at = forms.DateTimeField(required=False)
    expires_at = forms.DateTimeField(required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'code': instance.code,
                'name': instance.name,
                'description': instance.description,
                'discount_type': instance.discount_type,
                'discount_value': instance.discount_value,
                'minimum_order_amount': (
                    instance.minimum_order_amount.amount if instance.minimum_order_amount else None
                ),
                'maximum_discount_amount': (
                    instance.maximum_discount_amount.amount
                    if instance.maximum_discount_amount
                    else None
                ),
                'usage_limit': instance.usage_limit,
                'usage_limit_per_customer': instance.usage_limit_per_customer,
                'is_active': instance.is_active,
                'starts_at': instance.starts_at,
                'expires_at': instance.expires_at,
            }
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if not code:
            raise forms.ValidationError('Code is required.')
        from plugins.installed.marketing.models import Coupon

        qs = Coupon.objects.filter(code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another coupon already uses this code.')
        return code

    def save(self) -> Any:
        from plugins.installed.marketing.models import Coupon

        cd = self.cleaned_data
        coupon = self.instance or Coupon()
        coupon.code = cd['code']
        coupon.name = cd['name']
        coupon.description = cd.get('description') or ''
        coupon.discount_type = cd['discount_type']
        coupon.discount_value = cd['discount_value']
        coupon.minimum_order_amount = _money(cd.get('minimum_order_amount'))
        coupon.maximum_discount_amount = _money(cd.get('maximum_discount_amount'))
        coupon.usage_limit = cd.get('usage_limit')
        coupon.usage_limit_per_customer = cd.get('usage_limit_per_customer')
        coupon.is_active = bool(cd.get('is_active'))
        coupon.starts_at = cd.get('starts_at')
        coupon.expires_at = cd.get('expires_at')
        coupon.save()
        return coupon
