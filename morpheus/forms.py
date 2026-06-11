"""Form primitives for plugin authors.

A thin re-export of the Django forms surface so plugin authors don't
import ``django.forms`` directly. Use ``morpheus.forms`` exactly the
way you'd use ``django.forms``::

    from morpheus import forms

    class CouponForm(forms.Form):
        code = forms.CharField(max_length=32)
        amount = forms.DecimalField(max_digits=12, decimal_places=2)
"""

from __future__ import annotations

from django.forms import *  # noqa: F401, F403
from django.forms import (  # noqa: F401 — re-export for convenience
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    Form,
    HiddenInput,
    IntegerField,
    ModelForm,
    PasswordInput,
    Textarea,
    TextInput,
    URLField,
    UUIDField,
    ValidationError,
)
