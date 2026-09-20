"""Seed baseline policy/support CMS pages so the footer links resolve (not 404).

Mirrors the slugs the reference montenegro site used (help-center, safety-info,
cancellation-policy, hosting-resources, privacy-policy, terms-of-service). These
are placeholder pages the merchant edits later in the dashboard's Content area.
Idempotent: safe to run on every deploy.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

PAGES = [
    (
        'privacy-policy',
        'Privacy Policy',
        'How Montenegro Experience collects, uses and protects your data.',
        '<p>This Privacy Policy explains what information Montenegro Experience collects, '
        'how we use it, and the choices you have. We collect only what we need to run the '
        'marketplace — your account details, enquiries and bookings — and we never sell your '
        'data.</p><p>For any privacy question, contact us via the Contact page. This is a '
        'starter policy; replace it with your finalised text in the dashboard.</p>',
    ),
    (
        'terms-of-service',
        'Terms of Service',
        'The terms that govern your use of Montenegro Experience.',
        '<p>By using Montenegro Experience you agree to these terms. Experiences are offered by '
        'independent local hosts; Montenegro Experience connects you with them and facilitates '
        'enquiries and bookings.</p><p>This is a starter document — replace it with your '
        'finalised terms in the dashboard.</p>',
    ),
    (
        'help-center',
        'Help Center',
        'Answers to common questions about booking experiences in Montenegro.',
        '<p>Need a hand? Most questions about finding, enquiring about and booking experiences '
        "are answered here. Can't find what you need? Reach us through the Contact page and "
        "we'll get back to you.</p>",
    ),
    (
        'safety-info',
        'Safety information',
        'How we keep guests and hosts safe.',
        '<p>Your safety matters. Every host on Montenegro Experience is vetted, and we ask hosts '
        'to follow local regulations and safety practices for every activity. If anything feels '
        'off during an experience, contact us right away.</p>',
    ),
    (
        'cancellation-policy',
        'Cancellation options',
        'Flexible cancellation on most experiences.',
        '<p>Most experiences offer flexible cancellation. Specific terms are shown on each '
        "experience page under the host's cancellation policy. For help with a cancellation, "
        'contact us with your enquiry or booking details.</p>',
    ),
    (
        'hosting-resources',
        'Hosting resources',
        'Everything you need to host experiences in Montenegro.',
        '<p>Thinking of hosting? Montenegro Experience gives local hosts the tools to list '
        'experiences, manage enquiries and grow. Apply to become a host and our team will help '
        'you get set up.</p>',
    ),
]


class Command(BaseCommand):
    help = 'Seed baseline policy/support CMS pages (idempotent).'

    def handle(self, *args, **options):
        from plugins.installed.cms.models import Page

        created = 0
        published = 0
        for slug, title, excerpt, body in PAGES:
            obj, was_created = Page.objects.get_or_create(
                slug=slug,
                defaults={'title': title, 'excerpt': excerpt, 'body': body, 'state': 'published'},
            )
            if was_created:
                created += 1
            elif obj.state != 'published':
                obj.state = 'published'
                obj.save(update_fields=['state'])
                published += 1
        self.stdout.write(
            f'CMS pages: {created} created, {published} re-published, '
            f'{len(PAGES) - created} already present ({len(PAGES)} total).'
        )
