"""Customer + address create/edit forms."""
from __future__ import annotations

from typing import Any

from morpheus import forms


class CustomerForm(forms.Form):
    """Create/edit a `customers.Customer` (a.k.a. Contact in the dashboard).

    `source` marks where the contact arrived from — orders, lead form,
    signup, etc. `company` is exposed so B2B contacts captured via the
    storefront or CRM lead form land in the same record without
    needing a separate Lead row.
    """

    email = forms.EmailField()
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=30, required=False)
    company = forms.CharField(max_length=200, required=False)
    source = forms.ChoiceField(choices=[
        ('order', 'Order'),
        ('signup', 'Signup'),
        ('lead_form', 'Lead form'),
        ('newsletter', 'Newsletter'),
        ('import', 'Import'),
        ('manual', 'Manual entry'),
        ('agent', 'Agent-captured'),
        ('referral', 'Referral'),
        ('other', 'Other'),
    ], required=False, initial='manual')
    accepts_marketing = forms.BooleanField(required=False)
    is_verified = forms.BooleanField(required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'email': instance.email,
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'phone': instance.phone,
                'company': getattr(instance, 'company', '') or '',
                'source': getattr(instance, 'source', '') or 'other',
                'accepts_marketing': instance.accepts_marketing,
                'is_verified': instance.is_verified,
                'notes': instance.notes,
            }
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A customer with this email already exists.')
        return email

    def save(self) -> Any:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        cd = self.cleaned_data
        customer = self.instance or User()
        customer.email = cd['email']
        # Username is required by AbstractUser but we run email-first auth.
        if not customer.username:
            customer.username = cd['email']
        customer.first_name = cd.get('first_name') or ''
        customer.last_name = cd.get('last_name') or ''
        customer.phone = cd.get('phone') or ''
        if hasattr(customer, 'company'):
            customer.company = cd.get('company') or ''
        if hasattr(customer, 'source'):
            customer.source = cd.get('source') or 'manual'
        customer.accepts_marketing = bool(cd.get('accepts_marketing'))
        customer.is_verified = bool(cd.get('is_verified'))
        customer.notes = cd.get('notes') or ''
        if self.instance is None:
            # New customers default to unusable password — they must reset.
            customer.set_unusable_password()
            customer.is_active = True
        customer.save()
        return customer


class AddressForm(forms.Form):
    """Create/edit a `customers.Address` belonging to a given customer."""

    address_type = forms.ChoiceField(choices=[
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
    ], initial='shipping')
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=200, required=False)
    address_line1 = forms.CharField(max_length=255)
    address_line2 = forms.CharField(max_length=255, required=False)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    postal_code = forms.CharField(max_length=20)
    country = forms.CharField(max_length=2, initial='US')
    phone = forms.CharField(max_length=30, required=False)
    is_default = forms.BooleanField(required=False)

    def __init__(self, *args, instance=None, customer=None, **kwargs):
        self.instance = instance
        self.customer = customer or (instance.customer if instance else None)
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'address_type': instance.address_type,
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'company': instance.company,
                'address_line1': instance.address_line1,
                'address_line2': instance.address_line2,
                'city': instance.city,
                'state': instance.state,
                'postal_code': instance.postal_code,
                'country': instance.country,
                'phone': instance.phone,
                'is_default': instance.is_default,
            }
        super().__init__(*args, **kwargs)

    def save(self) -> Any:
        from plugins.installed.customers.models import Address
        if self.customer is None:
            raise ValueError('AddressForm.save() requires a customer.')

        cd = self.cleaned_data
        address = self.instance or Address(customer=self.customer)
        for field in (
            'address_type', 'first_name', 'last_name', 'company',
            'address_line1', 'address_line2', 'city', 'state',
            'postal_code', 'country', 'phone',
        ):
            setattr(address, field, cd.get(field) or '')
        address.is_default = bool(cd.get('is_default'))
        address.save()
        return address
