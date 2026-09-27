"""Seed the three baked-in journal entries as Page rows so the merchant has
something to edit in the dashboard the first time the journal page loads.

They are drafts: they are one bookshop's essays, and published they went live
on every new store under that store's brand."""
from __future__ import annotations

from django.db import migrations
from django.utils import timezone


SEED = [
    {
        'slug': 'a-short-note-on-patience',
        'title': 'A short note on patience and the long sentence',
        'excerpt': 'On Cusk, on Sebald, on the way a long paragraph teaches you how to wait.',
        'body': (
            "There's a particular pleasure in a sentence that takes a breath you didn't know "
            "you had to give it. Cusk does this. Sebald does this. The reader is asked to slow "
            "down — to hold a thought in suspension — and in that suspension something settles. "
            "We carry a few of these books on the shelf this season because we believe in the "
            "case for the long take."
        ),
    },
    {
        'slug': 'why-we-dont-carry-books-we-havent-read',
        'title': "Why we don't carry books we haven't read",
        'excerpt': 'A diary of how the shelf gets curated, and why it\'s a small one on purpose.',
        'body': (
            "Every title in the shop has been read by at least one of us before it makes it to "
            "the shelf. That's both a constraint and a promise. The constraint: the shop will "
            "always be small. The promise: if a book is here, it earned the spot. We trade "
            "breadth for trust."
        ),
    },
    {
        'slug': 'the-case-for-the-small-press',
        'title': 'The case for the small press, made in numbers',
        'excerpt': "Three years of receipts, and what they say about who's actually publishing the work that lasts.",
        'body': (
            "Pull three years of receipts and the picture is unambiguous: the books that customers "
            "come back to, the books they recommend to a friend, the books they buy a second copy "
            "of — they're disproportionately from independent presses. Not because indie is "
            "automatically better, but because the editors there have time to be wrong on purpose."
        ),
    },
]


def seed(apps, schema_editor):
    Page = apps.get_model('cms', 'Page')
    now = timezone.now()
    for i, entry in enumerate(SEED):
        if Page.objects.filter(slug=entry['slug']).exists():
            continue
        Page.objects.create(
            slug=entry['slug'],
            title=entry['title'],
            excerpt=entry['excerpt'],
            body=entry['body'],
            state='draft',
            publish_at=now,
            metadata={'category': 'journal', 'source': 'seed'},
        )


def unseed(apps, schema_editor):
    Page = apps.get_model('cms', 'Page')
    slugs = [e['slug'] for e in SEED]
    Page.objects.filter(slug__in=slugs, metadata__source='seed').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0003_pagesection'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
