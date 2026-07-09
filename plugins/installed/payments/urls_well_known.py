"""/.well-known/ routes owned by payments (Apple Pay domain verification)."""

from django.urls import path

from plugins.installed.payments import views

app_name = 'payments_well_known'

urlpatterns = [
    path(
        'apple-developer-merchantid-domain-association',
        views.apple_pay_domain_association,
        name='apple_pay_domain_association',
    ),
]
