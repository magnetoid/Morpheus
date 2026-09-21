"""Seed the marketplace-only policy/support CMS pages so the footer resolves.

Mirrors the slugs the reference montenegro site used (help-center, safety-info,
cancellation-policy, hosting-resources). These are placeholder pages the
merchant edits later in the dashboard's Content area. Idempotent: safe to run
on every deploy.

It used to seed `privacy-policy` and `terms-of-service` too — two-paragraph
stubs whose own text said "replace it with your finalised text". But the gdpr
app already seeds `privacy` and `terms` on every Morpheus store, so the site
served BOTH: four live URLs, two of them titled "Privacy Policy", each with its
own self-canonical, splitting the signal between a real policy and a placeholder
(the Sep 2026 audit found the duplicate title). One concept, one owner: gdpr
owns legal text, this command retires the stubs and `seed_seo_redirects` 301s
their paths. Retiring is `state='draft'`, never a delete — a merchant may have
edited the stub, and a draft is recoverable.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

# Retired in favour of gdpr's `privacy` / `terms`; see the module docstring.
SUPERSEDED_SLUGS = ('privacy-policy', 'terms-of-service')

PAGES = [
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
        retired = (
            Page.objects.filter(slug__in=SUPERSEDED_SLUGS)
            .exclude(state='draft')
            .update(state='draft')
        )
        self.stdout.write(
            f'CMS pages: {created} created, {published} re-published, '
            f'{len(PAGES) - created} already present ({len(PAGES)} total); '
            f'{retired} duplicate legal page(s) retired to draft.'
        )
