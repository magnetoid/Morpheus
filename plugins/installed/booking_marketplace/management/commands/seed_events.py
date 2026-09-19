"""Seed Montenegro's annual events calendar — idempotent.

    python manage.py seed_events

These are long-running annual fixtures (carnivals, festival seasons, regattas),
not one-off dates, which is why each carries an editorial `when_label` and a
`month` sort key rather than hard dates: exact dates for most editions are
announced only weeks ahead, and a hardcoded 2026 date would be wrong by 2027.

Where an event clearly belongs to a destination we already publish, it is
linked to that Place by slug so the two pages can point at each other.

No ticket prices or booking links are invented here — each event is run by a
municipality or festival body that sells through its own channel, and
`official_url` is left empty unless a stable official site is known.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

# name, category, region, place_slug, venue, when_label, month, summary,
# description, highlights, faqs, featured
EVENTS = [
    {
        'name': 'Kotor Carnival',
        'category': 'tradition',
        'region': 'kotor',
        'place_slug': 'kotor',
        'venue': 'Kotor Old Town and the waterfront',
        'when_label': 'February',
        'month': 2,
        'featured': True,
        'summary': 'A winter carnival of masks, brass and satire through the streets of the old town.',
        'description': (
            'Kotor’s winter carnival fills the walled town with masked groups, brass bands and '
            'floats, closing with a parade along the waterfront and the ceremonial burning of '
            'a effigy blamed for the past year’s misfortunes. It descends from the Venetian '
            'carnival tradition of the eastern Adriatic and keeps its satirical edge — local '
            'politics is fair game.'
        ),
        'highlights': [
            'Masked parade through the old town',
            'Brass bands and costumed groups',
            'Satirical floats',
            'Waterfront finale',
        ],
        'faqs': [
            {
                'q': 'When is Kotor Carnival held?',
                'a': 'In February, with the main parade usually on a weekend; exact dates are set by the town each year.',
            },
            {
                'q': 'Is Kotor Carnival free to attend?',
                'a': 'Yes — the parades and street events are open to the public, with no ticket needed to watch.',
            },
            {
                'q': 'Is February a good time to visit Kotor?',
                'a': 'It is cold and quiet outside the carnival, but that is part of the appeal: the old town belongs to residents rather than cruise crowds.',
            },
        ],
    },
    {
        'name': 'Mimosa Festival',
        'category': 'tradition',
        'region': 'kotor',
        'place_slug': 'herceg-novi',
        'venue': 'Herceg Novi',
        'when_label': 'February',
        'month': 2,
        'featured': True,
        'summary': 'Herceg Novi celebrates the first flowering of mimosa with weeks of parades and seafood.',
        'description': (
            'One of the oldest continuous festivals on the Montenegrin coast, the Mimosa '
            'Festival marks the early flowering of mimosa in the subtropical gardens of '
            'Herceg Novi. It runs across several weeks with parades, majorettes, boat '
            'processions, fish and wine evenings, and choirs from around the region.'
        ),
        'highlights': [
            'Mimosa parades through the town',
            'Fish and wine evenings',
            'Boat processions on the bay',
            'Regional choirs and brass',
        ],
        'faqs': [
            {
                'q': 'What is the Mimosa Festival?',
                'a': 'A weeks-long February festival in Herceg Novi celebrating the early bloom of mimosa, with parades, seafood evenings and concerts.',
            },
            {
                'q': 'Why is it held in February?',
                'a': 'Herceg Novi’s sheltered, subtropical microclimate brings mimosa into flower while the rest of the region is still in winter.',
            },
        ],
    },
    {
        'name': 'Boka Night (Bokeljska noć)',
        'category': 'tradition',
        'region': 'kotor',
        'place_slug': 'kotor',
        'venue': 'Kotor bay and waterfront',
        'when_label': 'Mid-August',
        'month': 8,
        'featured': True,
        'summary': 'Decorated boats, fireworks and an all-night party on the water at Kotor.',
        'description': (
            'The biggest night of the Boka summer. Local clubs and crews decorate boats to a '
            'theme and parade them across the bay in front of Kotor, judged from the shore, '
            'with fireworks over the water and music on the quay until dawn. It draws people '
            'from the whole bay, so the town is at its fullest.'
        ),
        'highlights': [
            'Illuminated boat parade',
            'Fireworks over the bay',
            'Live music on the waterfront',
            'One of the busiest nights of the year',
        ],
        'faqs': [
            {
                'q': 'When is Boka Night?',
                'a': 'In August, usually on a Saturday in the second half of the month; the date is announced by the town each summer.',
            },
            {
                'q': 'Where do you watch Boka Night?',
                'a': 'From the Kotor waterfront and the walls above it; arrive early, as the quay and approach roads fill up well before dark.',
            },
        ],
    },
    {
        'name': 'Grad teatar Budva (Theatre City)',
        'category': 'culture',
        'region': 'budva',
        'place_slug': 'budva',
        'venue': 'Budva Old Town squares and the citadel',
        'when_label': 'July–August',
        'month': 7,
        'featured': True,
        'summary': 'Montenegro’s flagship summer arts festival, staged in Budva’s old town.',
        'description': (
            'Founded in 1987, Grad teatar turns Budva’s walled town into a stage for six weeks '
            'each summer: drama in the squares and the citadel, poetry evenings, concerts and '
            'a long-running book programme. It is the country’s most established arts festival '
            'and the reason many people visit Budva for something other than the beach.'
        ),
        'highlights': [
            'Theatre in the citadel and old-town squares',
            'Poetry and literary evenings',
            'Classical and contemporary concerts',
            'Programme runs across July and August',
        ],
        'faqs': [
            {
                'q': 'What is Grad teatar?',
                'a': 'Budva’s Theatre City festival — a summer-long programme of drama, music and literature staged in the old town, running since 1987.',
            },
            {
                'q': 'Do you need tickets for Grad teatar?',
                'a': 'Ticketed for most theatre and concert performances, with some open-air and literary events free; tickets are sold locally during the season.',
            },
            {
                'q': 'Are performances in English?',
                'a': 'Most drama is in Montenegrin or Serbian; music and dance travel well regardless, and the programme lists language for each event.',
            },
        ],
    },
    {
        'name': 'Kotor Art',
        'category': 'culture',
        'region': 'kotor',
        'place_slug': 'kotor',
        'venue': 'Kotor Old Town',
        'when_label': 'July–August',
        'month': 7,
        'featured': False,
        'summary': 'An umbrella summer season of classical music, theatre and children’s arts in Kotor.',
        'description': (
            'Kotor Art gathers several long-running strands into one summer season inside the '
            'walled town — among them an international classical music programme and a '
            'children’s theatre festival that has run for decades. Performances use churches, '
            'palaces and squares as venues, which is much of the draw.'
        ),
        'highlights': [
            'Classical concerts in churches and palaces',
            'Long-running children’s theatre festival',
            'Open-air performances in the squares',
        ],
        'faqs': [
            {
                'q': 'What is Kotor Art?',
                'a': 'The umbrella summer arts season in Kotor, covering classical music, theatre and a children’s festival, staged in old-town venues.',
            },
            {
                'q': 'When does Kotor Art take place?',
                'a': 'Across July and August, with individual strands running on their own dates within the season.',
            },
        ],
    },
    {
        'name': 'Lake Fest',
        'category': 'music',
        'region': 'other',
        'place_slug': '',
        'venue': 'Krupac Lake, Nikšić',
        'when_label': 'Late July or August',
        'month': 8,
        'featured': False,
        'summary': 'Rock and alternative music on a lakeside beach outside Nikšić.',
        'description': (
            'Montenegro’s best-known rock festival, staged on the shore of Krupac Lake near '
            'Nikšić. Regional and international bands play over several nights to a camping '
            'crowd, with swimming in the lake between stages — an unusually relaxed setting '
            'for a festival of its size.'
        ),
        'highlights': [
            'Lakeside main stage',
            'Camping by the water',
            'Regional and international rock line-ups',
        ],
        'faqs': [
            {
                'q': 'Where is Lake Fest held?',
                'a': 'On the beach at Krupac Lake, a short drive from Nikšić in central Montenegro.',
            },
            {
                'q': 'Can you camp at Lake Fest?',
                'a': 'Yes — camping by the lake is part of the festival, and most attendees stay on site rather than in Nikšić.',
            },
        ],
    },
    {
        'name': 'Southern Soul Festival',
        'category': 'music',
        'region': 'ulcinj',
        'place_slug': 'ulcinj',
        'venue': 'Velika Plaža, Ulcinj',
        'when_label': 'August',
        'month': 8,
        'featured': False,
        'summary': 'Beach-side electronic and soul music on Ulcinj’s long sandy beach.',
        'description': (
            'Held on the sand at Velika Plaža, Southern Soul pairs house, soul and electronic '
            'line-ups with the most swimmable beach in the country. It is a beach festival in '
            'the literal sense — the stages sit on the shore, and the programme runs from late '
            'afternoon into the night.'
        ),
        'highlights': [
            'Stages on Velika Plaža',
            'House, soul and electronic line-ups',
            'Swimming between sets',
        ],
        'faqs': [
            {
                'q': 'Where is Southern Soul Festival?',
                'a': 'On Velika Plaža, the long sandy beach south of Ulcinj on Montenegro’s southern coast.',
            },
            {
                'q': 'When is it held?',
                'a': 'In August; exact dates are announced by the organisers each summer.',
            },
        ],
    },
    {
        'name': 'Petrovac Jazz Festival',
        'category': 'music',
        'region': 'budva',
        'place_slug': 'petrovac',
        'venue': 'Petrovac seafront',
        'when_label': 'Late August',
        'month': 8,
        'featured': False,
        'summary': 'Open-air jazz on the seafront as the summer season winds down.',
        'description': (
            'A small, long-running jazz festival staged outdoors on Petrovac’s promenade at the '
            'end of the season, when the crowds have thinned. Regional ensembles dominate the '
            'bill, and the setting — a bay, a fort and the sea behind the stage — does a lot of '
            'the work.'
        ),
        'highlights': [
            'Open-air seafront stage',
            'Regional jazz ensembles',
            'End-of-season timing, smaller crowds',
        ],
        'faqs': [
            {
                'q': 'When is the Petrovac Jazz Festival?',
                'a': 'Late August, as the main summer season ends; dates are set locally each year.',
            },
        ],
    },
    {
        'name': 'Fašinada',
        'category': 'tradition',
        'region': 'kotor',
        'place_slug': 'perast',
        'venue': 'Perast and Our Lady of the Rocks',
        'when_label': '22 July',
        'month': 7,
        'featured': True,
        'summary': 'Perast’s boat procession that has been adding stones to an island for centuries.',
        'description': (
            'On the evening of 22 July the men of Perast row a line of decorated boats out to '
            'Our Lady of the Rocks and drop stones around the islet, continuing the practice '
            'that built it. It is one of the oldest living customs on the Adriatic and, unlike '
            'most festival events, is a working ritual rather than a performance.'
        ),
        'highlights': [
            'Evening boat procession from Perast',
            'Stones cast around Our Lady of the Rocks',
            'One of the Adriatic’s oldest surviving customs',
        ],
        'faqs': [
            {
                'q': 'What is the Fašinada?',
                'a': 'A centuries-old Perast custom in which a procession of boats carries stones out to Our Lady of the Rocks each 22 July, continuing the islet’s construction.',
            },
            {
                'q': 'Can visitors watch the Fašinada?',
                'a': 'Yes — it is watched from the Perast waterfront and from boats, and takes place in the evening of 22 July each year.',
            },
        ],
    },
    {
        'name': 'Njeguši Prosciutto and Cheese Days',
        'category': 'food',
        'region': 'cetinje',
        'place_slug': 'njegusi',
        'venue': 'Njeguši village',
        'when_label': 'Summer',
        'month': 7,
        'featured': False,
        'summary': 'The mountain village behind Kotor celebrates the ham and cheese it is named for.',
        'description': (
            'Njeguši sits on the Lovćen road above Kotor and gives its name to Montenegro’s '
            'best-known cured ham and its accompanying cheese in oil. Its summer food days put '
            'producers, tastings and traditional cooking in the village itself — worth pairing '
            'with the serpentine drive up from the bay.'
        ),
        'highlights': [
            'Njeguški pršut tastings',
            'Cheese in oil from village producers',
            'The Kotor–Njeguši serpentine drive',
        ],
        'faqs': [
            {
                'q': 'What is Njeguši famous for?',
                'a': 'Njeguški pršut — air-dried, lightly smoked ham — and a cheese matured in oil, both produced in the village above Kotor.',
            },
            {
                'q': 'How do you get to Njeguši?',
                'a': 'By the serpentine road climbing from Kotor toward Lovćen, about 40 minutes, or from Cetinje on the other side.',
            },
        ],
    },
    {
        'name': 'Tivat Wine and Fish Festival',
        'category': 'food',
        'region': 'tivat',
        'place_slug': 'tivat',
        'venue': 'Tivat waterfront',
        'when_label': 'Spring',
        'month': 5,
        'featured': False,
        'summary': 'Boka seafood and Montenegrin wine along the Tivat waterfront.',
        'description': (
            'A waterfront food festival pairing the bay’s seafood with wines from Crmnica and '
            'the Podgorica plain. Producers set up along the promenade, with grilled fish, '
            'mussels from the bay and tastings of Vranac and Krstač.'
        ),
        'highlights': [
            'Bay mussels and grilled fish',
            'Vranac and Krstač tastings',
            'Waterfront setting in shoulder season',
        ],
        'faqs': [
            {
                'q': 'When is the Tivat wine and fish festival?',
                'a': 'In spring, outside the main tourist season; dates are announced locally each year.',
            },
        ],
    },
    {
        'name': 'Ski season on Bjelasica',
        'category': 'sport',
        'region': 'durmitor',
        'place_slug': 'kolasin',
        'venue': 'Kolašin 1450 and Kolašin 1600',
        'when_label': 'December–March',
        'month': 1,
        'featured': True,
        'summary': 'Montenegro’s main ski season, above the mountain town of Kolašin.',
        'description': (
            'Bjelasica carries the country’s most reliable skiing, served by two centres above '
            'Kolašin: the older Kolašin 1450 directly above the town and the newer, higher '
            'Kolašin 1600 on the far slopes. Snow is most dependable in January and February, '
            'and the town below keeps a proper mountain-town feel rather than a resort one.'
        ),
        'highlights': [
            'Kolašin 1600 gondola and upper runs',
            'Kolašin 1450 above the town',
            'Most reliable snow in January–February',
            'Rafting and hiking in the same valleys come summer',
        ],
        'faqs': [
            {
                'q': 'When can you ski in Montenegro?',
                'a': 'Roughly December to March, with the most dependable snow in January and February at the higher Kolašin 1600 centre on Bjelasica.',
            },
            {
                'q': 'Where is the best skiing in Montenegro?',
                'a': 'Bjelasica above Kolašin has the main lift-served terrain; Savin Kuk at Žabljak in Durmitor is the other option.',
            },
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed the Montenegro events calendar. Idempotent.'

    def handle(self, *args, **opts):
        from plugins.installed.booking_marketplace.models import Event, Place

        created = existing = 0
        for i, e in enumerate(EVENTS):
            slug = slugify(e['name'])
            place = None
            if e['place_slug']:
                place = Place.objects.filter(slug=e['place_slug']).first()

            event, was_created = Event.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': e['name'],
                    'category': e['category'],
                    'region': e['region'],
                    'place': place,
                    'venue': e['venue'],
                    'when_label': e['when_label'],
                    'month': e['month'],
                    'summary': e['summary'],
                    'description': e['description'],
                    'highlights': e['highlights'],
                    'faqs': e['faqs'],
                    'is_featured': e['featured'],
                    'sort_order': i,
                    'is_active': True,
                },
            )
            # Backfill only empty fields — never clobber an admin edit.
            dirty = []
            if not event.highlights:
                event.highlights = e['highlights']
                dirty.append('highlights')
            if not event.faqs:
                event.faqs = e['faqs']
                dirty.append('faqs')
            if not event.summary:
                event.summary = e['summary']
                dirty.append('summary')
            if event.place_id is None and place is not None:
                event.place = place
                dirty.append('place')
            if dirty:
                event.save(update_fields=dirty)

            created += was_created
            existing += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f'Events seeded: {created} created, {existing} already present '
                f'({Event.objects.count()} total).'
            )
        )
