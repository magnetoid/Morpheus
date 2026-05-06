"""Gift cards dashboard forms."""
from __future__ import annotations

from decimal import Decimal

from django import forms


class IssueGiftCardForm(forms.Form):
    """Issue a new gift card from the dashboard."""

    amount = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
        help_text='Initial balance in store currency.',
    )
    currency = forms.CharField(
        max_length=3, initial='USD',
        help_text='ISO currency code (USD, EUR, GBP…).',
    )
    issued_to_email = forms.EmailField(
        required=False,
        help_text='Recipient address — optional.',
    )
    note = forms.CharField(
        max_length=240, required=False, widget=forms.Textarea(attrs={'rows': 2}),
        help_text='Internal note. Not shown to the recipient.',
    )
    expires_at = forms.DateTimeField(
        required=False,
        help_text='Optional expiry. Leave blank for no expiry.',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def clean_currency(self):
        return (self.cleaned_data.get('currency') or 'USD').strip().upper()
