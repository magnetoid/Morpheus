"""Break-glass: clear a staff user's MFA device.

Use when a staffer loses their device with no recovery codes, or to recover
the very first admin before anyone else has enrolled. The reset is audited
(``mfa.admin_reset``); the user re-enrolls on next sign-in.

    python manage.py reset_mfa someone@example.com
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Clear a staff user's MFA device (break-glass / lost device). Audited."

    def add_arguments(self, parser):
        parser.add_argument('email', help='Email of the staff user to reset.')

    def handle(self, *args, **options):
        from plugins.installed.staff_mfa.models import StaffMfaDevice
        from plugins.installed.staff_mfa.services import audit

        email = (options['email'] or '').strip().lower()
        user = get_user_model().objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f'No user with email {email!r}.')

        deleted, _ = StaffMfaDevice.objects.filter(user=user).delete()
        audit(
            'mfa.admin_reset', target=email, metadata={'deleted_rows': deleted}, severity='warning'
        )

        if deleted:
            self.stdout.write(
                self.style.SUCCESS(f'Reset MFA for {email} — they will re-enroll on next sign-in.')
            )
        else:
            self.stdout.write(f'{email} had no MFA device; nothing to reset.')
