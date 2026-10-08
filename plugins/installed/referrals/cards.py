"""The referrals card on the Customers list (DashboardCard)."""

from __future__ import annotations


def referrals_card(request) -> dict:
    """Referrals that earned their reward, and the ones still waiting."""
    from plugins.installed.referrals.models import Referral

    credited = Referral.objects.filter(state='credited').count()
    pending = Referral.objects.filter(state='pending').count()
    if not (credited or pending):
        return {'empty': 'No referral orders yet.'}
    return {
        'value': str(credited),
        'caption': 'referrals rewarded',
        'rows': [('Waiting for the order to qualify', pending)],
    }
