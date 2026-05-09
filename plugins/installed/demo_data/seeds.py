"""
Demo seed data for a small modern bookstore.

All copy/data is fictional. The intent is to give a fresh Morpheus install
something to look at on first boot — not a complete product catalog.
"""
from __future__ import annotations

CATEGORIES = [
    {'name': 'Fiction',     'slug': 'fiction'},
    {'name': 'Non-fiction', 'slug': 'nonfiction'},
    {'name': 'Poetry',      'slug': 'poetry'},
    {'name': 'Essays',      'slug': 'essays'},
    {'name': 'Children',    'slug': 'children'},
    {'name': 'Art & Design', 'slug': 'art-design'},
]

COLLECTIONS = [
    {
        'name': 'Editor\'s pick — April',
        'slug': 'editors-pick-april',
        'description': 'One title a month. April: a quiet novel that earned the spotlight by being unflashy.',
        'is_featured': True,
    },
    {
        'name': 'Reading the spring',
        'slug': 'reading-the-spring',
        'description': 'Light enough for the train, sharp enough for the desk.',
        'is_featured': True,
    },
    {
        'name': 'Independent presses we love',
        'slug': 'independent-presses',
        'description': 'Tiny shops doing the work that big houses won\'t.',
        'is_featured': False,
    },
]

VENDORS = [
    {'name': 'Pelican Press',     'slug': 'pelican-press',     'commission_rate': '15.00'},
    {'name': 'Lantern Books',     'slug': 'lantern-books',     'commission_rate': '15.00'},
    {'name': 'Foxglove Editions', 'slug': 'foxglove-editions', 'commission_rate': '20.00'},
]


# (name, slug, sku, category_slug, vendor_slug, price, short_description, description, featured)
BOOKS = [
    (
        'On Quiet Hours', 'on-quiet-hours', 'OQH-01', 'fiction', 'pelican-press',
        '18.00',
        'A novel that listens more than it speaks.',
        'A long-form debut about three siblings, a coastal house, and the quiet hours that arrive when no one is watching. Sparing prose, large emotional weight.',
        True,
    ),
    (
        'The Last Letter Home', 'last-letter-home', 'LLH-01', 'fiction', 'lantern-books',
        '16.50',
        'Wartime fiction that resists nostalgia.',
        'A correspondence-form novel that uses the silence between letters to do most of the work.',
        True,
    ),
    (
        'Unfinished Light', 'unfinished-light', 'UL-01', 'poetry', 'foxglove-editions',
        '14.00',
        'A debut collection threading grief and ordinary mornings.',
        'Sixty-two poems written across two years, edited down from twice that. The book that the poet didn\'t want to publish, until she did.',
        True,
    ),
    (
        'A Small History of Listening', 'small-history-listening', 'SHL-01', 'nonfiction', 'pelican-press',
        '22.00',
        'Five centuries of attention, from monasteries to podcasts.',
        'Less a study of sound and more a study of who got to be heard. The chapter on call centers alone is worth the cover price.',
        True,
    ),
    (
        'Rooms We Didn\'t Choose', 'rooms-we-didnt-choose', 'RWC-01', 'essays', 'foxglove-editions',
        '17.00',
        'Twelve essays on inheritance, real estate, and family.',
        'A debut collection from a critic who has been writing for fifteen years and selecting carefully.',
        True,
    ),
    (
        'How To Read A Building', 'how-to-read-building', 'HRB-01', 'art-design', 'pelican-press',
        '28.00',
        'A field guide for everyone tired of "midcentury".',
        'Lovingly photographed, sharply written. The chapter on stairwells will change how you walk through any city.',
        False,
    ),
    (
        'Notes from a Borrowed Garden', 'borrowed-garden', 'BG-01', 'nonfiction', 'lantern-books',
        '19.50',
        'A year in someone else\'s plot.',
        'A memoir disguised as gardening manual. Or the other way around.',
        False,
    ),
    (
        'The Archive of Almost', 'archive-of-almost', 'AA-01', 'fiction', 'foxglove-editions',
        '17.50',
        'Stories that end one breath before resolution.',
        'Twenty-two short fictions on the long form of nearly. A reader\'s favorite.',
        False,
    ),
    (
        'River Light', 'river-light', 'RL-01', 'poetry', 'lantern-books',
        '13.50',
        'Pamphlet-length, paperback-thin.',
        'A travelling pamphlet of poems that fit in a coat pocket. Read on the move.',
        False,
    ),
    (
        'The Map We Carried', 'map-we-carried', 'MWC-01', 'fiction', 'pelican-press',
        '15.00',
        'Roadtrip novel for people who don\'t drive.',
        'Two friends, a borrowed car, and a country that keeps changing under them.',
        True,
    ),
    (
        'Field Notes for a Calmer Mind', 'field-notes-calmer', 'FNCM-01', 'nonfiction', 'lantern-books',
        '20.00',
        'A working notebook, not a self-help book.',
        'Practices, exercises, and quiet observations from a clinical psychologist who refuses to call this a "system".',
        False,
    ),
    (
        'Nine Letters to a Younger Reader', 'nine-letters', 'NLR-01', 'essays', 'pelican-press',
        '15.50',
        'Letters across thirty years.',
        'A retired teacher writes to the version of herself who first opened a library card.',
        False,
    ),
    (
        'Rabbit Almanac', 'rabbit-almanac', 'RA-01', 'children', 'foxglove-editions',
        '14.00',
        'Twelve tiny adventures, one per month.',
        'Illustrated short stories for ages 6–10. Pelican Press\'s most-borrowed children\'s title.',
        True,
    ),
    (
        'The Slow Press Manifesto', 'slow-press-manifesto', 'SPM-01', 'nonfiction', 'foxglove-editions',
        '12.00',
        'A short pamphlet on independent publishing.',
        'Why the world doesn\'t need another bestseller, and what to do about it.',
        False,
    ),
    (
        'Glasswork', 'glasswork', 'GW-01', 'art-design', 'pelican-press',
        '36.00',
        'Studio photographs from a forgotten Murano workshop.',
        'A coffee-table monograph about a craft most of us have only seen as souvenirs.',
        False,
    ),
    (
        'The Long Quiet', 'long-quiet', 'LQ-01', 'fiction', 'lantern-books',
        '16.00',
        'A modern Western about land and waiting.',
        'Spare, slow, and strange. Read it twice; it gets better.',
        True,
    ),
    (
        'Notes Between Songs', 'notes-between-songs', 'NBS-01', 'essays', 'lantern-books',
        '15.00',
        'A musician on the gaps in their own albums.',
        'An essay collection from a touring songwriter who treats silence as a primary instrument.',
        False,
    ),
    (
        'A Brief Atlas of Ordinary Weather', 'ordinary-weather', 'OW-01', 'poetry', 'pelican-press',
        '13.00',
        'Forty-seven small poems on the sky.',
        'Slim and quietly devastating.',
        False,
    ),
    (
        'The Cabinetmaker\'s Daughter', 'cabinetmakers-daughter', 'CD-01', 'fiction', 'foxglove-editions',
        '18.00',
        'A novel about inheritance, in every sense of the word.',
        'Three generations, one small workshop, a mountain of unmade chairs.',
        False,
    ),
    (
        'How to Be Alone Without Becoming Lonely', 'be-alone', 'BA-01', 'nonfiction', 'pelican-press',
        '17.00',
        'A working book, not a manifesto.',
        'A philosopher\'s notebook on solitude as practice.',
        True,
    ),
    (
        'Window Light', 'window-light', 'WL-01', 'art-design', 'lantern-books',
        '32.00',
        'Domestic interiors photographed in available light.',
        'A photobook about how light enters a room when no one\'s rearranged it for the camera.',
        False,
    ),
    (
        'The Forager\'s Confidence', 'foragers-confidence', 'FC-01', 'nonfiction', 'foxglove-editions',
        '21.00',
        'A practical and philosophical handbook.',
        'Fewer recipes than you\'d expect; more about decisions in the field.',
        False,
    ),
    (
        'The Little Books of Big Things', 'little-books', 'LBBT-01', 'children', 'pelican-press',
        '11.00',
        'Picture-book primers on hard ideas.',
        'Five small board books for kids 3–6: time, kindness, sharing, no, and waiting.',
        False,
    ),
    (
        'Rain on the Train', 'rain-on-the-train', 'ROT-01', 'children', 'lantern-books',
        '13.00',
        'A bedtime book for early readers.',
        'A small story about being safe in transit. Will be read 200 times.',
        False,
    ),
    (
        'The Fold-Out Cookbook', 'fold-out-cookbook', 'FOC-01', 'nonfiction', 'foxglove-editions',
        '24.00',
        'Twelve poster-recipes you actually want to put on the wall.',
        'A kitchen object first, a cookbook second.',
        False,
    ),
]


# Book-specific metadata, indexed by slug. Written as Metafields with
# namespace='book' during seeding — picked up by the storefront PDP
# "About this edition" card. Only the seven fields below are surfaced;
# add more here + in storefront.views._BOOK_SPEC_FIELDS to render them.
BOOK_METADATA = {
    'on-quiet-hours': {
        'author': 'Hanna Rieder', 'publisher': 'Pelican Press', 'published_year': 2024,
        'format': 'Paperback', 'pages': 224, 'language': 'English', 'isbn': '978-1-911557-24-1',
    },
    'last-letter-home': {
        'author': 'Theo Marlow', 'publisher': 'Lantern Books', 'published_year': 2023,
        'format': 'Paperback', 'pages': 312, 'language': 'English', 'isbn': '978-1-913665-02-7',
    },
    'unfinished-light': {
        'author': 'Ines Cabral', 'publisher': 'Foxglove Editions', 'published_year': 2024,
        'format': 'Paperback', 'pages': 96, 'language': 'English', 'isbn': '978-1-908009-44-3',
    },
    'small-history-listening': {
        'author': 'Daniel Eshun', 'publisher': 'Pelican Press', 'published_year': 2023,
        'format': 'Hardback', 'pages': 384, 'language': 'English', 'isbn': '978-1-911557-31-9',
    },
    'rooms-we-didnt-choose': {
        'author': 'Mira Lazlo', 'publisher': 'Foxglove Editions', 'published_year': 2024,
        'format': 'Paperback', 'pages': 256, 'language': 'English', 'isbn': '978-1-908009-51-1',
    },
    'how-to-read-building': {
        'author': 'Adrian Pell', 'publisher': 'Pelican Press', 'published_year': 2022,
        'format': 'Hardback', 'pages': 248, 'language': 'English', 'isbn': '978-1-911557-08-1',
    },
    'borrowed-garden': {
        'author': 'Caro Spence', 'publisher': 'Lantern Books', 'published_year': 2023,
        'format': 'Paperback', 'pages': 196, 'language': 'English', 'isbn': '978-1-913665-15-7',
    },
    'archive-of-almost': {
        'author': 'Yusra Hamdan', 'publisher': 'Foxglove Editions', 'published_year': 2024,
        'format': 'Paperback', 'pages': 178, 'language': 'English', 'isbn': '978-1-908009-58-0',
    },
    'river-light': {
        'author': 'Otto Renn', 'publisher': 'Lantern Books', 'published_year': 2023,
        'format': 'Pamphlet', 'pages': 32, 'language': 'English', 'isbn': '978-1-913665-22-5',
    },
    'map-we-carried': {
        'author': 'Lucia Mendel', 'publisher': 'Pelican Press', 'published_year': 2024,
        'format': 'Paperback', 'pages': 288, 'language': 'English', 'isbn': '978-1-911557-40-1',
    },
    'field-notes-calmer': {
        'author': 'Dr. R. Asante', 'publisher': 'Lantern Books', 'published_year': 2023,
        'format': 'Paperback', 'pages': 208, 'language': 'English', 'isbn': '978-1-913665-09-6',
    },
    'nine-letters': {
        'author': 'Eleanor Vines', 'publisher': 'Pelican Press', 'published_year': 2022,
        'format': 'Paperback', 'pages': 144, 'language': 'English', 'isbn': '978-1-911557-15-9',
    },
    'rain-on-the-train': {
        'author': 'Sam Beck', 'publisher': 'Lantern Books', 'published_year': 2023,
        'format': 'Picture book', 'pages': 32, 'language': 'English', 'isbn': '978-1-913665-30-0',
    },
    'fold-out-cookbook': {
        'author': 'Park & Reid', 'publisher': 'Foxglove Editions', 'published_year': 2024,
        'format': 'Hardback', 'pages': 64, 'language': 'English', 'isbn': '978-1-908009-66-5',
    },
}
