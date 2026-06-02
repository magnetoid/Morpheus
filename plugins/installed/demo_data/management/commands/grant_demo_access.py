"""Grant a user full test access: affiliate + vendor + sandbox payment gateways.

Idempotent admin/demo utility so the store owner can exercise the affiliate,
vendor, and checkout flows end to end. Safe to re-run.

    manage.py grant_demo_access --email you@example.com

WARNING: this enables the **Test** payment gateway, which always succeeds.
On a live store that means anyone can place a FREE order while it's on —
disable it in Settings → Payments once you've finished testing. Pass
--cod-only to enable just Cash-on-delivery (a real, safe method).
"""

# ruff: noqa: PLC0415 — cross-plugin model imports are lazy (optional plugins).
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Make a user an approved affiliate + a vendor, and enable Test + COD gateways.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Customer email to grant access to.')
        parser.add_argument(
            '--cod-only',
            action='store_true',
            help='Enable only Cash-on-delivery (skip the always-succeeds Test gateway).',
        )

    def handle(self, *args, **opts):
        email = (opts['email'] or '').strip()
        user = get_user_model().objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f'No user with email {email!r}. Create the account first.')

        local = (email.split('@', 1)[0] or 'user').lower()
        base = slugify(local) or 'partner'
        out = []

        # 1) Affiliate (approved) under a default program.
        try:
            from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

            program, _ = AffiliateProgram.objects.get_or_create(
                slug='default',
                defaults={'name': 'Default program', 'commission_value': 10, 'is_active': True},
            )
            aff, created = Affiliate.objects.get_or_create(
                program=program,
                user=user,
                defaults={
                    'handle': self._unique(Affiliate, 'handle', base),
                    'status': 'approved',
                    'display_name': (user.get_full_name() or local).strip(),
                    'payout_email': email,
                    'approved_at': timezone.now(),
                },
            )
            if not created and aff.status != 'approved':
                aff.status = 'approved'
                aff.approved_at = aff.approved_at or timezone.now()
                aff.save(update_fields=['status', 'approved_at'])
            out.append(f'affiliate /{aff.handle} ({aff.status})')
        except Exception as e:  # noqa: BLE001
            out.append(f'affiliate SKIPPED ({e})')

        # 2) Vendor owned by the user.
        try:
            from plugins.installed.catalog.models import Vendor

            vendor = Vendor.objects.filter(owner=user).first()
            if vendor is None:
                vendor = Vendor.objects.create(
                    slug=self._unique(Vendor, 'slug', base),
                    name=f'{local.title()} Books',
                    owner=user,
                    is_active=True,
                )
            elif not vendor.is_active:
                vendor.is_active = True
                vendor.save(update_fields=['is_active'])
            out.append(f'vendor /{vendor.slug}')
        except Exception as e:  # noqa: BLE001
            out.append(f'vendor SKIPPED ({e})')

        # 3) Enable gateways so the checkout picker offers them.
        try:
            from plugins.installed.payments.models import PaymentGatewayConfig

            slugs = ['cod'] if opts['cod_only'] else ['cod', 'test']
            for slug in slugs:
                PaymentGatewayConfig.objects.update_or_create(slug=slug, defaults={'enabled': True})
            out.append('gateways enabled: ' + ', '.join(slugs))
        except Exception as e:  # noqa: BLE001
            out.append(f'gateways SKIPPED ({e})')

        self.stdout.write(self.style.SUCCESS(f'Granted access to {email}: ' + ' · '.join(out)))
        if not opts['cod_only']:
            self.stdout.write(
                self.style.WARNING(
                    'Test gateway is now live + publicly selectable — anyone can place a FREE '
                    'order. Disable it in Settings → Payments after testing.'
                )
            )

    @staticmethod
    def _unique(model, field, base):
        val, n = base, 2
        while model.objects.filter(**{field: val}).exists():
            val, n = f'{base}-{n}', n + 1
        return val
