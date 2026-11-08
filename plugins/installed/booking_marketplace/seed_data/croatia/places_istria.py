"""Istria destinations for croatia-experience.me (Places seed data).

Editorial guides for real Istrian towns and sites. English, plain and factual: no prices or
opening hours, no ratings, and only facts that do not change quickly. Imported by the
``seed_croatia`` command and keyed by slug.
"""

from __future__ import annotations

PLACES: list[dict] = [
    {
        'name': 'Pula',
        'slug': 'pula',
        'region': 'istria',
        'place_type': 'cities',
        'featured': True,
        'summary': (
            'Istria’s largest city, with a 1st-century Roman amphitheatre, Roman temple and'
            ' a working port.'
        ),
        'description': (
            'Pula is the largest city in Istria and keeps a set of well-preserved Roman '
            'buildings, led by the 1st-century amphitheatre known as the Arena. Venetian '
            'and Austro-Hungarian layers sit beside them, around a working harbour at the '
            'southern tip of the peninsula.'
        ),
        'highlights': [
            'Pula Arena (Roman amphitheatre)',
            'Temple of Augustus on the Forum',
            'Arch of the Sergii',
            'Venetian fortress (Kaštel) and its museum',
            'Old town streets and Twin Gates',
        ],
        'overview': (
            'Pula, known to the Romans as Pola, lies at the southern end of the Istrian '
            'peninsula on a sheltered bay. The Arena, built in the 1st century AD, still '
            'stands with its outer walls largely intact, and concerts and other events are '
            'held inside it. Close by, the Temple of Augustus faces the old Forum square, '
            'and the Arch of the Sergii marks the edge of the Roman town. The Venetians '
            'built the star-shaped fortress on the central hill in the 17th century, and it'
            ' now holds the Historical and Maritime Museum of Istria. In the 19th century '
            'Pula became the main naval base of the Austro-Hungarian Empire, which left '
            'behind fortifications and civic buildings across the city. Today it is a '
            'working port city with a lively centre and a long coastline of rocky shore and'
            ' small beaches, and it is the usual gateway to southern Istria.'
        ),
        'faqs': [
            {
                'q': 'Is Pula worth visiting?',
                'a': (
                    'Yes, for its Roman monuments in a living city. The Arena, Temple of '
                    'Augustus and Arch of the Sergii are all within a short walk of each '
                    'other in the centre.'
                ),
            },
            {
                'q': 'How do I get to Pula?',
                'a': (
                    'Pula Airport (PUY) is under 10 km from the city. Pula is also linked '
                    'by road to the rest of Istria and by regional bus services.'
                ),
            },
            {
                'q': 'What is there to do in Pula?',
                'a': (
                    'Visit the Arena, walk the Roman Forum and the Arch of the Sergii, '
                    'climb to the Venetian fortress for views over the harbour, and use the'
                    ' city as a base for beaches and for Brijuni and Cape Kamenjak.'
                ),
            },
            {
                'q': 'How long should I spend in Pula?',
                'a': (
                    'One day covers the main Roman sights; two or three days lets you add '
                    'the coast and day trips south and north.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September for swimming; spring and autumn for sightseeing',
            },
            {
                'label': 'Ideal for',
                'value': 'Roman history, city breaks, coastal day trips',
            },
            {
                'label': 'Time needed',
                'value': 'One to three days',
            },
            {
                'label': 'Getting there',
                'value': 'Pula Airport (PUY) under 10 km; road and bus links across Istria',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), under 10 km',
            },
        ],
        'good_for': [
            'history lovers',
            'city breaks',
            'couples',
            'day-trip base',
            'families',
        ],
        'sections': [
            {
                'heading': 'A Roman and Habsburg city',
                'body': (
                    'Pula was a Roman colony and its Roman monuments survive in the middle '
                    'of the modern city. After centuries of Venetian rule it passed to the '
                    'Habsburg monarchy, and from the mid-19th century the Austrian navy '
                    'made it a major base. The city’s grid of streets, parks and public '
                    'buildings from that period sits close to the Roman core, so the centre'
                    ' shows both eras within a few blocks.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The Arena is the city’s landmark, and visitors can walk through its '
                    'arcades and the underground galleries. The Temple of Augustus stands '
                    'on the Forum, and the Arch of the Sergii and the Twin Gates mark old '
                    'entrances to the Roman town. The Kaštel fortress on the hill gives a '
                    'view over the old town and the port, and the city museums add '
                    'archaeology and maritime history.'
                ),
            },
            {
                'heading': 'Using Pula as a base',
                'body': (
                    'Pula is the transport hub of southern Istria. The airport is close, '
                    'beaches and coves lie along the coast towards Premantura, the Brijuni '
                    'islands are reached by boat from nearby Fažana, and Vodnjan, Rovinj '
                    'and the hill towns are a short drive away. That makes it a practical '
                    'base for a stay of several days.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Pula — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Pula',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.8666,
        'longitude': 13.8496,
    },
    {
        'name': 'Rovinj',
        'slug': 'rovinj',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': True,
        'summary': (
            'A harbour town on Istria’s west coast, built on a former island and crowned by'
            ' the church of St Euphemia.'
        ),
        'description': (
            'Rovinj is a fishing and tourist town on Istria’s west coast. Its old centre '
            'rises up a small peninsula, with narrow stone streets climbing to the baroque '
            'church of St Euphemia and its bell tower, and a scatter of islands lies just '
            'offshore.'
        ),
        'highlights': [
            'Church of St Euphemia and its bell tower',
            'Old town streets and the harbour',
            'Balbi Arch',
            'Golden Cape (Zlatni rt) forest park',
            'Islands off the coast',
        ],
        'overview': (
            'Rovinj (Rovigno in Italian) grew on an island that was joined to the mainland '
            'in the 18th century, which is why the old town is a compact oval of stone '
            'houses and steep lanes around the harbour. At the top stands the church of St '
            'Euphemia, with a bell tower that is a landmark visible from the sea. The town '
            'was under Venetian rule for centuries, and Italian remains an official '
            'language alongside Croatian in this part of Istria. South of the centre, the '
            'Golden Cape forest park has paths, rocky shore and pine woods, and a group of '
            'islands just offshore can be reached by boat. Fishing, art galleries and '
            'harbour-side cafés give the town its character.'
        ),
        'faqs': [
            {
                'q': 'Is Rovinj worth visiting?',
                'a': (
                    'Yes, for its old town, harbour and nearby coast. It works for a day '
                    'trip or a longer stay, and the surrounding Golden Cape park adds walks'
                    ' and swimming spots.'
                ),
            },
            {
                'q': 'How do I get to Rovinj?',
                'a': (
                    'Rovinj is roughly 40 km from Pula Airport (PUY) by road. Buses and car'
                    ' routes connect it with Pula, Poreč and the rest of Istria.'
                ),
            },
            {
                'q': 'What is there to do in Rovinj?',
                'a': (
                    'Walk the old town up to St Euphemia, watch the harbour, swim along the'
                    ' Golden Cape, and take a boat to the nearby islands.'
                ),
            },
            {
                'q': 'How long should I spend in Rovinj?',
                'a': (
                    'A day covers the old town and a swim; two or three days allows the '
                    'coast, the islands and trips to nearby places such as Lim Bay.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September for swimming; spring and autumn for quieter streets',
            },
            {
                'label': 'Ideal for',
                'value': 'Old-town walks, sea swimming, couples',
            },
            {
                'label': 'Time needed',
                'value': 'One day to a few days',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 40 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 40 km',
            },
        ],
        'good_for': [
            'couples',
            'old-town walks',
            'swimming',
            'photography',
            'short breaks',
        ],
        'sections': [
            {
                'heading': 'A town on a former island',
                'body': (
                    'Rovinj was an island until a channel was filled in during the 18th '
                    'century. The resulting peninsula holds the old town, which is why its '
                    'streets run steeply and radiate from the hilltop church. Venetian rule'
                    ' left its mark in the architecture and in the Balbi Arch, one of the '
                    'old town gates, while a long tradition of fishing and boat building '
                    'shaped the harbour.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'Climb through the lanes to the church of St Euphemia, which holds the '
                    'relics of the saint, and look out over the sea from its terrace. The '
                    'harbour is the centre of town life, with cafés and galleries on the '
                    'lanes behind it. A short walk or ride south leads to the Golden Cape '
                    'park, where marked paths run through woodland to the rocky shore.'
                ),
            },
            {
                'heading': 'The coast and islands',
                'body': (
                    'Boats leave Rovinj harbour for the islands off the coast, including '
                    'those used for swimming and short excursions. North of the town, the '
                    'long inlet of Lim Bay is within easy reach for a day out. The '
                    'surrounding area also has olive groves and countryside to explore by '
                    'car or bike.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Rovinj — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Rovinj',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.0812,
        'longitude': 13.6387,
    },
    {
        'name': 'Poreč',
        'slug': 'porec',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A coastal town on Istria’s west coast, home to the UNESCO-listed Euphrasian Basilica.'
        ),
        'description': (
            'Poreč is a coastal town on Istria’s west coast. Its old centre sits on a small'
            ' peninsula and keeps its Roman street layout, and the Euphrasian Basilica, a '
            'Byzantine-era church with mosaics, is inscribed on the UNESCO World Heritage '
            'List.'
        ),
        'highlights': [
            'Euphrasian Basilica (UNESCO World Heritage)',
            'Decumanus, the old Roman main street',
            'Old town and the seafront promenade',
            'Remains of the Temple of Neptune',
            'Beaches and coves along the coast',
        ],
        'overview': (
            'Poreč was founded as a Roman settlement, and the main street of the old town, '
            'the Decumanus, still follows the Roman layout. The Euphrasian Basilica, built '
            'in the 6th century, is the town’s best-known monument and was inscribed on the'
            ' UNESCO World Heritage List in 1997, noted for its early Byzantine mosaics. '
            'The old town is a short peninsula of stone houses, small squares and a '
            'seafront promenade. Beyond it, the coast to the north and south has beaches, '
            'pine woods and resort areas, and Poreč has a long history as a holiday town. '
            'The surrounding countryside is dotted with vineyards and olive groves, and the'
            ' inland towns of Istria are within an easy drive.'
        ),
        'faqs': [
            {
                'q': 'Is Poreč worth visiting?',
                'a': (
                    'Yes, for the Euphrasian Basilica and the old town on the sea, together'
                    ' with the beaches around it.'
                ),
            },
            {
                'q': 'How do I get to Poreč?',
                'a': (
                    'Poreč is roughly 60 km from Pula Airport (PUY) by road, with regular '
                    'bus links to Pula, Rovinj and other Istrian towns.'
                ),
            },
            {
                'q': 'What is there to do in Poreč?',
                'a': (
                    'See the basilica and its mosaics, walk the Decumanus, stroll the '
                    'seafront, swim along the coast and explore the inland villages.'
                ),
            },
            {
                'q': 'How long should I spend in Poreč?',
                'a': (
                    'A half day covers the old town; a longer stay suits those who want the'
                    ' beaches and day trips to Motovun, Rovinj or Lim Bay.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September for the coast; spring and autumn for sightseeing',
            },
            {
                'label': 'Ideal for',
                'value': 'Beach stays, history, families',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to several days',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 60 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 60 km',
            },
        ],
        'good_for': [
            'families',
            'beach holidays',
            'history lovers',
            'couples',
            'day-trip base',
        ],
        'sections': [
            {
                'heading': 'A Roman layout and a Byzantine church',
                'body': (
                    'The street grid of Poreč’s old centre goes back to the Roman period, '
                    'with the Decumanus running the length of the peninsula. In the 6th '
                    'century, Bishop Euphrasius had a basilica built on the site of an '
                    'earlier church. The complex of church, atrium, baptistery and bishop’s'
                    ' palace is the reason for the UNESCO listing.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The basilica’s mosaics are the main draw, and the bell tower can be '
                    'climbed for a view over the old town. Along the Decumanus there are '
                    'shops, cafés and small museums, and a few Roman remains, including the'
                    ' Temple of Neptune, can be seen near the shore. The seafront promenade'
                    ' is a pleasant walk in the evening.'
                ),
            },
            {
                'heading': 'The surrounding coast',
                'body': (
                    'North and south of the old town, the coast has beaches, rocky '
                    'stretches and wooded headlands, with tourist resorts that grew up from'
                    ' the mid-20th century. Boats run to nearby islands and along the '
                    'shore, and the vineyards and villages inland are reachable by car or '
                    'bike.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Poreč — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Poreč',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.2269,
        'longitude': 13.5944,
    },
    {
        'name': 'Novigrad',
        'slug': 'novigrad',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small walled town on a peninsula on Istria’s northwest coast, with a harbour'
            ' and quiet seafront.'
        ),
        'description': (
            'Novigrad (Cittanova in Italian) is a small coastal town on Istria’s northwest '
            'coast. The old centre sits on a short peninsula behind remains of town walls, '
            'with a harbour on one side and a promenade along the sea on the other.'
        ),
        'highlights': [
            'Old town on the peninsula',
            'Remains of the town walls',
            'Parish church and bell tower',
            'Harbour and marina',
            'Seafront promenade',
        ],
        'overview': (
            'Novigrad is one of the smaller towns on the Istrian west coast, between Poreč '
            'and Umag. The old town occupies a peninsula, with narrow streets, small '
            'squares and parts of the medieval walls still in place. It has been inhabited '
            'since Roman times, and for centuries it was a bishopric. The parish church, '
            'with its bell tower, stands at the end of the peninsula by the sea. The town '
            'has a harbour used by fishing boats and visiting yachts, and a promenade runs '
            'along the shore, with rocky and pebble coves nearby. The surrounding area is '
            'quiet, with olive groves and vineyards,. Novigrad is a relaxed base for those '
            'who prefer a smaller place to the larger resorts nearby.'
        ),
        'faqs': [
            {
                'q': 'Is Novigrad worth visiting?',
                'a': (
                    'Yes, as a calm, small coastal town with an old centre, and as a base '
                    'for the northwest of Istria.'
                ),
            },
            {
                'q': 'How do I get to Novigrad?',
                'a': (
                    'Novigrad is roughly 70 km from Pula Airport (PUY) by road, between '
                    'Poreč and Umag, with bus links along the coast.'
                ),
            },
            {
                'q': 'What is there to do in Novigrad?',
                'a': (
                    'Walk the old town and the seafront, see the parish church, sit by the '
                    'harbour, swim from the coves and cycle or drive through the nearby '
                    'countryside.'
                ),
            },
            {
                'q': 'How long should I spend in Novigrad?',
                'a': (
                    'A few hours covers the old town; a longer stay suits a quiet seaside break.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September for swimming; spring and autumn for quiet walks',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet seaside stays, short breaks',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a few days',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 70 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 70 km',
            },
        ],
        'good_for': [
            'quiet breaks',
            'couples',
            'swimming',
            'cycling',
            'old-town walks',
        ],
        'sections': [
            {
                'heading': 'A small town with a long history',
                'body': (
                    'Novigrad has been settled since antiquity, and its Italian name, '
                    'Cittanova, means “new town”. The old centre grew on a peninsula and '
                    'was enclosed by walls, parts of which can still be seen. For a long '
                    'period it was the seat of a bishop, and the old streets and church '
                    'reflect that history.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The old town can be walked in an hour or two, with the parish church '
                    'and bell tower at the tip of the peninsula and views along the coast. '
                    'The harbour and promenade are the centre of daily life, with cafés and'
                    ' small restaurants facing the water.'
                ),
            },
            {
                'heading': 'Around Novigrad',
                'body': (
                    'The coast around the town has small beaches and rocky coves, and the '
                    'countryside inland has olive groves, vineyards and quiet roads for '
                    'cycling. Poreč to the south and Umag to the north are both within a '
                    'short drive.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Novigrad — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Novigrad,_Istria_County',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.3178,
        'longitude': 13.5594,
    },
    {
        'name': 'Umag',
        'slug': 'umag',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A coastal town at the northwestern tip of Istria, with an old town on a '
            'peninsula and a long stretch of shore.'
        ),
        'description': (
            'Umag is a coastal town at the northwestern tip of Istria, close to the '
            'Slovenian border. The old centre sits on a small peninsula, and the town is '
            'known for its seaside, its marina and the tennis tournament that has been '
            'played here.'
        ),
        'highlights': [
            'Old town on the peninsula',
            'Marina and seafront',
            'Tennis tournament venue',
            'Coastal paths and beaches',
            'Countryside of olive groves and vineyards',
        ],
        'overview': (
            'Umag lies at the far northwest of Istria, not far from the borders with '
            'Slovenia and Italy. Its old town stands on a peninsula and has narrow streets '
            'and small squares, and some older buildings that show its Venetian past. South'
            ' of the centre, the coast is lined with beaches, pine woods and tourist '
            'developments, and there is a marina for visiting boats. Umag is also known for'
            ' tennis: the town has hosted an international professional tournament, and has'
            ' sport facilities that draw visitors. The countryside behind it is gentle, '
            'with olive groves, vineyards and small villages, and the nearby coast and '
            'inland towns can be explored by bike or car. It is a straightforward base for '
            'the northwest of the peninsula.'
        ),
        'faqs': [
            {
                'q': 'Is Umag worth visiting?',
                'a': (
                    'Yes, for a seaside stay in the northwest of Istria, with a small old '
                    'town and easy access to the coast and countryside.'
                ),
            },
            {
                'q': 'How do I get to Umag?',
                'a': (
                    'Umag is roughly 90 km from Pula Airport (PUY) by road. Buses link Umag'
                    ' with other Istrian towns.'
                ),
            },
            {
                'q': 'What is there to do in Umag?',
                'a': (
                    'Walk the old town and seafront, swim along the coast, cycle through '
                    'the countryside and visit nearby towns such as Novigrad and Poreč.'
                ),
            },
            {
                'q': 'How long should I spend in Umag?',
                'a': 'A few hours covers the old town; a beach stay can last several days.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September for swimming; spring and autumn for cycling',
            },
            {
                'label': 'Ideal for',
                'value': 'Seaside stays, sport, cycling',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to several days',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 90 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 90 km',
            },
        ],
        'good_for': [
            'beach holidays',
            'sport',
            'cycling',
            'families',
            'short breaks',
        ],
        'sections': [
            {
                'heading': 'A border town on the sea',
                'body': (
                    'Umag has been inhabited since Roman times and later belonged to '
                    'Venice. Its position near the present-day borders with Slovenia and '
                    'Italy has made it a crossing point for travellers and traders. The old'
                    ' town on the peninsula has kept its compact layout and some of its '
                    'older buildings.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The old centre is small and easy to walk, with a few churches and '
                    'houses of interest and a harbour front for an evening stroll. South of'
                    ' the centre, paths run along the shore through pine woods, and the '
                    'marina is a focus of activity for visiting boats.'
                ),
            },
            {
                'heading': 'The surrounding area',
                'body': (
                    'Inland there are olive groves, vineyards and farms, and nearby '
                    'villages can be reached on country roads. The towns of Novigrad and '
                    'Poreč to the south are within a short drive.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Umag — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Umag',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.4311,
        'longitude': 13.5226,
    },
    {
        'name': 'Vrsar',
        'slug': 'vrsar',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small hilltop town above the sea on Istria’s west coast, near the mouth of Lim Bay.'
        ),
        'description': (
            'Vrsar is a small town on Istria’s west coast, on a hill above the sea with a '
            'harbour at its foot. A castle once belonging to the bishops of Poreč stands at'
            ' its top, and a group of islands lies offshore.'
        ),
        'highlights': [
            'Hilltop old town',
            'The castle (Kaštel)',
            'Harbour',
            'Views over the offshore islands',
            'Nearby Lim Bay',
        ],
        'overview': (
            'Vrsar sits on a rise above the Adriatic between Poreč and Rovinj. The old town'
            ' climbs the hill in narrow lanes of stone houses, ending near a castle that '
            'was once a summer residence of the bishops of Poreč. At the foot of the hill, '
            'the harbour is the centre of town life, with fishing boats and small '
            'restaurants. Offshore lie a group of small islands, and the long inlet of Lim '
            'Bay opens just to the south. The coast near Vrsar has beaches and rocky coves,'
            ' and pine woods and olive groves are close behind. The town is small and easy '
            'to walk, which makes it a calm base for a stay on the west coast. Poreč and '
            'Rovinj are each a short drive away.'
        ),
        'faqs': [
            {
                'q': 'Is Vrsar worth visiting?',
                'a': (
                    'Yes, as a small hilltop town on the sea, particularly for a quiet stay'
                    ' near Lim Bay.'
                ),
            },
            {
                'q': 'How do I get to Vrsar?',
                'a': (
                    'Vrsar is roughly 55 km from Pula Airport (PUY) by road, between Poreč '
                    'and Rovinj.'
                ),
            },
            {
                'q': 'What is there to do in Vrsar?',
                'a': (
                    'Walk the old town to the castle, sit by the harbour, swim along the '
                    'coast and visit Lim Bay nearby.'
                ),
            },
            {
                'q': 'How long should I spend in Vrsar?',
                'a': ('A few hours covers the town; a longer stay suits a quiet seaside break.'),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September for swimming; spring and autumn for walks',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet seaside stays, short breaks',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a few days',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 55 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 55 km',
            },
        ],
        'good_for': [
            'quiet breaks',
            'couples',
            'swimming',
            'old-town walks',
            'boat trips',
        ],
        'sections': [
            {
                'heading': 'A town on a hill',
                'body': (
                    'Vrsar occupies a hilltop on the Adriatic coast, with a harbour at the '
                    'bottom and old stone houses climbing the slope. The castle at the top '
                    'was built for the bishops of Poreč, who held the town for centuries. '
                    'The layout of narrow lanes and small squares has changed little.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The walk up through the old town ends at the castle area and a church '
                    'with a view over the sea and the islands. Down at the harbour, cafés '
                    'and restaurants line the front. The pine-shaded coast around the town '
                    'has places to swim.'
                ),
            },
            {
                'heading': 'Lim Bay and the islands',
                'body': (
                    'Just south of Vrsar, Lim Bay cuts deep inland, and boats from the area'
                    ' run to the bay and to the islands off the coast. Rovinj to the south '
                    'and Poreč to the north are both an easy drive.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Vrsar — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Vrsar',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.1508,
        'longitude': 13.6064,
    },
    {
        'name': 'Lim Bay',
        'slug': 'lim-bay',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A long, narrow sea inlet in western Istria, between Vrsar and Rovinj, known '
            'for its steep wooded sides.'
        ),
        'description': (
            'Lim Bay (Limski zaljev, also called Lim Fjord) is a long, narrow inlet that '
            'cuts inland on Istria’s west coast, between Vrsar and Rovinj. Wooded hills '
            'rise steeply on both sides, and shellfish farming is a local tradition.'
        ),
        'highlights': [
            'Viewpoints over the inlet',
            'Boat trips on the bay',
            'Romuald’s Cave',
            'Shellfish farms and local seafood',
            'Walking and cycling trails around the bay',
        ],
        'overview': (
            'Lim Bay is a drowned river valley, a narrow arm of sea that reaches several '
            'kilometres inland from the Adriatic. The slopes on both sides are covered in '
            'oak and other woodland, and the water is calm, which suits boat trips and '
            'kayaking. The bay is known for its farmed mussels and oysters, which are '
            'served in restaurants in the area. According to tradition, a cave on the '
            'northern slope, known as Romuald’s Cave, was the home of the hermit St '
            'Romuald. The area is protected, and walking and cycling routes run around the '
            'rim of the bay, with viewpoints over the water. It lies between Vrsar and '
            'Rovinj, so it is easily visited as a half-day trip from either town, or from '
            'Poreč.'
        ),
        'faqs': [
            {
                'q': 'Is Lim Bay worth visiting?',
                'a': (
                    'Yes, for the view and the quiet water, as a half-day trip from Rovinj,'
                    ' Vrsar or Poreč.'
                ),
            },
            {
                'q': 'How do I get to Lim Bay?',
                'a': (
                    'Lim Bay is roughly 50 km from Pula Airport (PUY). It is reached by '
                    'road from Rovinj or Vrsar, and boats run to it from nearby harbours.'
                ),
            },
            {
                'q': 'What is there to do at Lim Bay?',
                'a': (
                    'Take a boat or kayak trip on the inlet, walk or cycle the trails on '
                    'the rim, look out from the viewpoints and try local shellfish.'
                ),
            },
            {
                'q': 'How long should I spend at Lim Bay?',
                'a': 'A few hours to half a day is enough.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Boat trips, walks, scenery',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to half a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Rovinj or Vrsar; boat trips from nearby harbours',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 50 km',
            },
        ],
        'good_for': [
            'nature',
            'boat trips',
            'walkers',
            'cyclists',
            'seafood lovers',
        ],
        'sections': [
            {
                'heading': 'A drowned river valley',
                'body': (
                    'The bay formed when the sea flooded the lower part of a river valley, '
                    'leaving a long inlet with steep sides. The calm water and the green '
                    'slopes give the place a distinct look compared with the open coast '
                    'nearby. Its shores are largely wooded and little built up.'
                ),
            },
            {
                'heading': 'What to do',
                'body': (
                    'Boat trips run along the bay from nearby towns, and the quiet water is'
                    ' suited to kayaking. Walking and cycling routes follow the rim, with '
                    'viewpoints over the inlet. At the head and along the shore, the bay’s '
                    'oysters and mussels are farmed and served in local restaurants.'
                ),
            },
            {
                'heading': 'Romuald’s Cave',
                'body': (
                    'On the northern side of the bay, a cave is traditionally linked to the'
                    ' hermit St Romuald, who is said to have lived there in the early 11th '
                    'century. It is a stop on some local excursions and a reminder that the'
                    ' bay has long been a place apart from the coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Lim Bay — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Lim_Bay',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.1333,
        'longitude': 13.7167,
    },
    {
        'name': 'Motovun',
        'slug': 'motovun',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A medieval hill town in central Istria, ringed by walls and surrounded by the '
            'Motovun Forest.'
        ),
        'description': (
            'Motovun is a medieval hill town in central Istria, standing on a hilltop above'
            ' the Mirna river valley and surrounded by old walls. The nearby Motovun Forest'
            ' is known for truffles, and the town hosts a well-known film festival.'
        ),
        'highlights': [
            'Town walls and the walk around them',
            'Main square and parish church',
            'Views over the Mirna valley',
            'Motovun Forest',
            'Local truffles and wine',
        ],
        'overview': (
            'Motovun rises from a hilltop in the Mirna river valley, a compact town of '
            'stone houses within walls that date from the medieval period. A road or a path'
            ' leads up to the gate, and a walk along the ramparts gives wide views over '
            'vineyards and forest. The main square holds the parish church and a town '
            'loggia. Below the hill, the Motovun Forest, along the Mirna, is known for '
            'white truffles, and local restaurants serve dishes made with them in season. '
            'The town is also known for the Motovun Film Festival, which has been held in '
            'the town since 1999. Motovun is among the best-known inland places in Istria '
            'and is often combined with Grožnjan, Hum and Buzet on a tour of the interior.'
        ),
        'faqs': [
            {
                'q': 'Is Motovun worth visiting?',
                'a': ('Yes, for the hilltop setting, the walls and the views over central Istria.'),
            },
            {
                'q': 'How do I get to Motovun?',
                'a': (
                    'Motovun is roughly 80 km from Pula Airport (PUY) by road. A car is the'
                    ' easiest way to reach it, and the town sits above the Mirna valley '
                    'road.'
                ),
            },
            {
                'q': 'What is there to do in Motovun?',
                'a': (
                    'Walk the walls, visit the square and church, taste local truffle '
                    'dishes and wines, and walk in the forest below.'
                ),
            },
            {
                'q': 'How long should I spend in Motovun?',
                'a': (
                    'Two to three hours cover the town; a half day also covers a meal and '
                    'the walk around the ramparts.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and autumn; September–October for truffle season',
            },
            {
                'label': 'Ideal for',
                'value': 'Hill-town walks, food and wine, photography',
            },
            {
                'label': 'Time needed',
                'value': 'Two hours to half a day',
            },
            {
                'label': 'Getting there',
                'value': 'By car; roughly 80 km from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 80 km',
            },
        ],
        'good_for': [
            'food and wine',
            'photography',
            'couples',
            'road trips',
            'history lovers',
        ],
        'sections': [
            {
                'heading': 'A hill town above the Mirna',
                'body': (
                    'Motovun’s position on a hilltop made it a defensible site for '
                    'centuries, and the walls and towers reflect its time under Venetian '
                    'control. The old centre is small and car-free, and the walk up from '
                    'the lower car park takes a few minutes.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'Walking the line of the ramparts gives views over the valley and '
                    'distant hills. The main square holds the church of St Stephen and the '
                    'town loggia. Small shops sell truffle products and local wine and '
                    'olive oil.'
                ),
            },
            {
                'heading': 'Truffles and the forest',
                'body': (
                    'The Motovun Forest in the valley below is one of the areas in Istria '
                    'associated with truffles. Local guides and restaurants offer truffle '
                    'hunting and tasting experiences, and the film festival gives the town '
                    'a busy week each summer. Check dates directly with the organisers '
                    'before planning around it.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Motovun — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Motovun',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.3375,
        'longitude': 13.8286,
    },
    {
        'name': 'Grožnjan',
        'slug': 'groznjan',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A small hilltop town in northwest Istria, known for its artists’ studios and '
            'summer music events.'
        ),
        'description': (
            'Grožnjan (Grisignana in Italian) is a small hilltop town in northwest Istria. '
            'Its stone streets are home to artists’ studios and galleries, and the town is '
            'associated with music schools and concerts held in summer.'
        ),
        'highlights': [
            'Old town and its stone lanes',
            'Artists’ studios and galleries',
            'Views over the Mirna valley',
            'Summer music events',
            'Parish church and loggia',
        ],
        'overview': (
            'Grožnjan stands on a ridge between the Mirna valley and the coast, inland from'
            ' Novigrad. After the Second World War the town lost much of its population, '
            'and in the 1960s artists began to move into the empty houses, opening studios '
            'that now line the lanes. It has since become known for music as well: '
            'Jeunesses Musicales organises summer music schools and concerts here. The old '
            'town is compact and best walked on foot, with the parish church, a loggia and '
            'viewpoints looking out over the vineyards. Italian is used alongside Croatian '
            'on signs. Grožnjan is often visited with Motovun and Buzet on a drive through '
            'the interior of Istria, and it is also close enough to the coast to combine '
            'with a day at the seaside.'
        ),
        'faqs': [
            {
                'q': 'Is Grožnjan worth visiting?',
                'a': (
                    'Yes, for its quiet stone lanes, the artists’ studios and the views, as'
                    ' a stop on a tour of inland Istria.'
                ),
            },
            {
                'q': 'How do I get to Grožnjan?',
                'a': (
                    'Grožnjan is roughly 85 km from Pula Airport (PUY) by road. A car is '
                    'the easiest way, and the town is a short drive inland from Novigrad.'
                ),
            },
            {
                'q': 'What is there to do in Grožnjan?',
                'a': (
                    'Walk the lanes, visit the studios and galleries, look out over the '
                    'valley and attend a concert if one is on.'
                ),
            },
            {
                'q': 'How long should I spend in Grožnjan?',
                'a': 'One to two hours covers the town.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn; summer for events',
            },
            {
                'label': 'Ideal for',
                'value': 'Art, music, hill-town walks',
            },
            {
                'label': 'Time needed',
                'value': 'One to two hours',
            },
            {
                'label': 'Getting there',
                'value': 'By car; roughly 85 km from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 85 km',
            },
        ],
        'good_for': [
            'art lovers',
            'music lovers',
            'photography',
            'road trips',
            'couples',
        ],
        'sections': [
            {
                'heading': 'A town revived by artists',
                'body': (
                    'Like several Istrian hill towns, Grožnjan lost people in the decades '
                    'after the war, and many of its houses stood empty. From the 1960s, '
                    'artists took over buildings and set up studios, and the town gained a '
                    'reputation as a place for creative work. That tradition continues, and'
                    ' many of the studios are open to visitors.'
                ),
            },
            {
                'heading': 'Music in Grožnjan',
                'body': (
                    'The town hosts summer music schools and concerts organised by '
                    'Jeunesses Musicales, which bring young musicians from different '
                    'countries. Small concerts can sometimes be heard in the lanes and '
                    'churches during the season. Check the programme with the organisers '
                    'before travelling.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The old town is small, with the parish church, a loggia and a few '
                    'viewpoints at the edge of the ridge. Lanes lead between galleries and '
                    'small shops. The surroundings are vineyards and woodland, and the sea '
                    'at Novigrad and Umag is a short drive away.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Grožnjan — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Grožnjan',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.3703,
        'longitude': 13.7222,
    },
    {
        'name': 'Hum',
        'slug': 'hum',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A tiny hilltop settlement in central Istria, officially a town, with a strong '
            'Glagolitic heritage.'
        ),
        'description': (
            'Hum is a very small walled settlement on a hill in central Istria, officially '
            'classed as a town. A few dozen people live there. It is associated with the '
            'Glagolitic script, and a road lined with monuments in that script leads to it.'
        ),
        'highlights': [
            'The walled settlement and its gate',
            'Church of the Assumption',
            'Glagolitic Alley (Aleja glagoljaša)',
            'Local biska brandy',
            'Views over the Istrian interior',
        ],
        'overview': (
            'Hum stands on a hilltop in the interior of Istria, near Roč and Buzet. It is a'
            ' compact cluster of stone houses within a wall, and a single main street runs '
            'through it. The settlement is officially a town, though it has only a few '
            'dozen residents. Hum is closely linked to the Glagolitic script, an early '
            'Slavic alphabet used in this region for centuries. The Glagolitic Alley, a '
            'road between Roč and Hum, is lined with monuments recalling this tradition, '
            'and the Church of the Assumption holds old Glagolitic inscriptions. The '
            'settlement is known locally for biska, a mistletoe brandy. Hum is a small stop'
            ' rather than a destination for a full day, and it is often visited together '
            'with Roč, Buzet or Motovun.'
        ),
        'faqs': [
            {
                'q': 'Is Hum worth visiting?',
                'a': (
                    'Yes, as a short stop for its tiny size, old walls and Glagolitic '
                    'heritage, ideally combined with other places in the interior.'
                ),
            },
            {
                'q': 'How do I get to Hum?',
                'a': (
                    'Hum is roughly 80 km from Pula Airport (PUY) by road. A car is the '
                    'practical way to reach it, usually via Pazin or Buzet.'
                ),
            },
            {
                'q': 'What is there to do in Hum?',
                'a': (
                    'Walk the main street, see the church, try biska brandy and walk part '
                    'of the Glagolitic Alley from Roč.'
                ),
            },
            {
                'q': 'How long should I spend in Hum?',
                'a': 'About an hour covers the settlement.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Short stops, history, quiet scenery',
            },
            {
                'label': 'Time needed',
                'value': 'About one hour',
            },
            {
                'label': 'Getting there',
                'value': 'By car; roughly 80 km from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 80 km',
            },
        ],
        'good_for': [
            'history lovers',
            'road trips',
            'photography',
            'quiet places',
            'cultural heritage',
        ],
        'sections': [
            {
                'heading': 'A very small town',
                'body': (
                    'Hum has been settled for centuries on a hill in the interior of the '
                    'peninsula. Its walls enclose a handful of houses, a church and a small'
                    ' square. Its official status as a town is a matter of history rather '
                    'than size, and the settlement has remained very small.'
                ),
            },
            {
                'heading': 'The Glagolitic script',
                'body': (
                    'The Glagolitic alphabet was used in churches and records in parts of '
                    'Croatia, including Istria, in the medieval period. The Glagolitic '
                    'Alley between Roč and Hum is a road with monuments that recall that '
                    'heritage. Inscriptions inside the Church of the Assumption in Hum also'
                    ' use the script.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'The settlement can be seen in about an hour, so it fits well into a '
                    'day in the Istrian interior. Roč is a short distance away along the '
                    'Alley, Buzet is nearby, and Motovun and Pazin are within a short '
                    'drive.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Hum — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Hum,_Croatia',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.2292,
        'longitude': 14.0764,
    },
    {
        'name': 'Buzet',
        'slug': 'buzet',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A hilltop town in northern Istria, above the Mirna river, associated with '
            'truffles and the forests around it.'
        ),
        'description': (
            'Buzet is a town in northern Istria. Its old centre stands on a hill above the '
            'Mirna river, with a lower town beneath, and the forests of the Mirna valley '
            'are known for truffles.'
        ),
        'highlights': [
            'Old town on the hill',
            'Views over the Mirna valley',
            'Local truffle dishes',
            'Nearby hill towns Roč and Hum',
            'Walking and cycling routes',
        ],
        'overview': (
            'Buzet sits in northern Istria, not far from the border with Slovenia. The old '
            'town occupies a hilltop, reached by steps and lanes from the lower town, and '
            'looks out over the valley of the Mirna river. The forests along the river are '
            'known for truffles, which are used in the local cooking, and restaurants in '
            'and around Buzet serve them in season. The surrounding hills have marked '
            'trails for walkers and cyclists. Buzet is also a good starting point for '
            'visits to the nearby hill settlements of Roč and Hum, and to Motovun. The town'
            ' is quiet outside the main season and is used mostly by those exploring the '
            'interior of the peninsula, rather than as a beach destination.'
        ),
        'faqs': [
            {
                'q': 'Is Buzet worth visiting?',
                'a': (
                    'Yes, for a quiet hilltop town and as a base for the interior of '
                    'northern Istria.'
                ),
            },
            {
                'q': 'How do I get to Buzet?',
                'a': (
                    'Buzet is roughly 85 km from Pula Airport (PUY) by road. A car is the '
                    'easiest way, and the town is on the road between Pazin and the '
                    'Slovenian border.'
                ),
            },
            {
                'q': 'What is there to do in Buzet?',
                'a': (
                    'Walk the old town, eat local truffle dishes, hike or cycle in the '
                    'surrounding hills and visit Roč and Hum.'
                ),
            },
            {
                'q': 'How long should I spend in Buzet?',
                'a': 'A few hours cover the old town and a meal.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and autumn; truffle season in autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Food, walking, interior Istria',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours',
            },
            {
                'label': 'Getting there',
                'value': 'By car; roughly 85 km from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 85 km',
            },
        ],
        'good_for': [
            'food lovers',
            'walkers',
            'cyclists',
            'road trips',
            'quiet places',
        ],
        'sections': [
            {
                'heading': 'A town on two levels',
                'body': (
                    'Buzet has an upper town on the hill and a newer lower town beside the '
                    'river. The upper town keeps old walls, stone houses and a view over '
                    'the valley. The two parts are linked by steps and a road, and the '
                    'climb takes a few minutes.'
                ),
            },
            {
                'heading': 'Truffles and local food',
                'body': (
                    'The Mirna valley forests around Buzet are known for truffles, and '
                    'local restaurants and shops sell dishes and products made with them. '
                    'The area also produces olive oil and wine, and the cooking of inland '
                    'Istria is a reason many visitors come.'
                ),
            },
            {
                'heading': 'Around Buzet',
                'body': (
                    'Roč and Hum are both nearby and are linked by the Glagolitic Alley. '
                    'Motovun is a short drive west down the Mirna valley, and the hills '
                    'around Buzet have walking and cycling routes with views over the '
                    'interior.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Buzet — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Buzet',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.4106,
        'longitude': 13.9631,
    },
    {
        'name': 'Pazin',
        'slug': 'pazin',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'The administrative centre of Istria County, with a medieval castle above a '
            'deep chasm and a museum inside it.'
        ),
        'description': (
            'Pazin is a town in the centre of Istria and the seat of Istria County. Its '
            'castle stands at the edge of the Pazin Chasm, a deep gorge where the Pazinčica'
            ' stream disappears underground, and it houses the Ethnographic Museum of '
            'Istria.'
        ),
        'highlights': [
            'Pazin Castle (Kaštel)',
            'Pazin Chasm (Pazinska jama)',
            'Ethnographic Museum of Istria',
            'Old town and its lanes',
            'Walking trails in central Istria',
        ],
        'overview': (
            'Pazin is in the middle of the Istrian peninsula, on the border between the '
            'green interior and the dry limestone of the south. Its main landmark is the '
            'castle, built on a cliff above a deep chasm into which the Pazinčica stream '
            'flows and disappears. Inside the castle, the Ethnographic Museum of Istria '
            'shows traditional life in the region. The chasm is linked in literature to '
            'Jules Verne, who set part of his novel Mathias Sandorf here. The town itself '
            'is a working administrative and school centre, with an old quarter of small '
            'streets and squares. Pazin is a convenient stop between the coast and the hill'
            ' towns of the north, and trails lead from the town into the countryside.'
        ),
        'faqs': [
            {
                'q': 'Is Pazin worth visiting?',
                'a': (
                    'Yes, for the castle above the chasm and the museum, as a stop in the '
                    'middle of Istria.'
                ),
            },
            {
                'q': 'How do I get to Pazin?',
                'a': (
                    'Pazin is roughly 50 km from Pula Airport (PUY) by road, in the centre '
                    'of the peninsula. Buses and trains connect it with Pula and other '
                    'towns.'
                ),
            },
            {
                'q': 'What is there to do in Pazin?',
                'a': (
                    'Visit the castle and museum, look into the chasm from the viewpoint, '
                    'walk the old quarter and use the town as a stop on the way to Motovun,'
                    ' Hum or Buzet.'
                ),
            },
            {
                'q': 'How long should I spend in Pazin?',
                'a': 'Two to three hours cover the castle and the old town.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Castles, museums, interior Istria',
            },
            {
                'label': 'Time needed',
                'value': 'Two to three hours',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 50 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 50 km',
            },
        ],
        'good_for': [
            'history lovers',
            'families',
            'museum visitors',
            'road trips',
            'walkers',
        ],
        'sections': [
            {
                'heading': 'A castle on a cliff',
                'body': (
                    'Pazin Castle was built on the edge of a limestone cliff, with the '
                    'chasm below it. It is first mentioned in the 10th century, and was '
                    'held by a series of counts and ruling families. Today it forms the '
                    'town’s main landmark and contains the town museum and the Ethnographic'
                    ' Museum of Istria.'
                ),
            },
            {
                'heading': 'The chasm',
                'body': (
                    'The Pazinčica stream flows into the chasm and continues underground, a'
                    ' typical karst feature. The place has inspired stories and legends, '
                    'and Jules Verne used it as a setting in Mathias Sandorf. A viewpoint '
                    'near the castle lets visitors look into the gorge.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Pazin is a short drive from Motovun, Buzet and Hum, and from the coast'
                    ' at Rovinj and Poreč. It makes a good midday stop between the coast '
                    'and the hill towns of the north.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Pazin — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Pazin',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.24,
        'longitude': 13.9358,
    },
    {
        'name': 'Labin',
        'slug': 'labin',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A hilltop town in eastern Istria with a walled old centre, a history of coal '
            'mining and views of the Kvarner Bay.'
        ),
        'description': (
            'Labin is a town in eastern Istria. Its old centre stands on a hill about 300 m'
            ' above the sea, with narrow stone streets, and a lower town below grew up '
            'around the coal mines of the area. The beach resort of Rabac lies just below.'
        ),
        'highlights': [
            'Old town on the hill',
            'National Museum of Labin',
            'Lookouts over the Kvarner Bay and Cres',
            'Mining heritage in the lower town (Podlabin)',
            'Rabac beach nearby',
        ],
        'overview': (
            'Labin sits on a hill in the east of Istria, with views to the Kvarner Bay and '
            'the island of Cres. The old town (Stari Grad) is a maze of stone lanes and '
            'small squares, with a Venetian-era loggia and the parish church of the Birth '
            'of the Blessed Virgin Mary. The National Museum of Labin holds collections on '
            'local history and has a reconstruction of a mine gallery, a reminder that coal'
            ' was mined in the area into the 20th century. The lower part of the town, '
            'Podlabin, grew around the mines. In recent decades, Labin has been known for '
            'its artists and its cultural events. The resort of Rabac, with its beaches, is'
            ' a short drive down to the coast, and many visitors combine the old town with '
            'a swim there.'
        ),
        'faqs': [
            {
                'q': 'Is Labin worth visiting?',
                'a': (
                    'Yes, for the old town, the museum and the view, and for its location '
                    'just above Rabac.'
                ),
            },
            {
                'q': 'How do I get to Labin?',
                'a': (
                    'Labin is roughly 50 km from Pula Airport (PUY) by road. Rabac is a few'
                    ' kilometres below it on the coast.'
                ),
            },
            {
                'q': 'What is there to do in Labin?',
                'a': (
                    'Walk the old town, visit the National Museum, enjoy the viewpoints and'
                    ' combine the visit with a swim at Rabac.'
                ),
            },
            {
                'q': 'How long should I spend in Labin?',
                'a': 'Two to three hours cover the old town and the museum.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Old-town walks, museums, seaside combinations',
            },
            {
                'label': 'Time needed',
                'value': 'Two to three hours',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 50 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 50 km',
            },
        ],
        'good_for': [
            'history lovers',
            'museum visitors',
            'photography',
            'couples',
            'beach holidays',
        ],
        'sections': [
            {
                'heading': 'A town above the sea',
                'body': (
                    'Labin’s hilltop position gave it a long view over the Kvarner Bay and '
                    'made it a defensible site for centuries. The old town was shaped under'
                    ' Venetian rule and keeps buildings from that time. From the 19th '
                    'century coal mining changed the area, and the lower town grew with the'
                    ' mines.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The old town’s lanes lead past churches, a loggia and small galleries '
                    'to viewpoints over the coast. The National Museum of Labin, in a '
                    'palace in the old town, shows archaeology, local history and the '
                    'mining past, including a reconstructed mine gallery.'
                ),
            },
            {
                'heading': 'Labin and Rabac',
                'body': (
                    'Rabac, a former fishing village that became a seaside resort, lies a '
                    'few kilometres below Labin by road. Together the two make a '
                    'combination of old town and beach, easily done in a day.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Labin — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Labin',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.0942,
        'longitude': 14.1228,
    },
    {
        'name': 'Rabac',
        'slug': 'rabac',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A former fishing village turned seaside resort on Istria’s east coast, below '
            'the hill town of Labin.'
        ),
        'description': (
            'Rabac is a seaside resort on the east coast of Istria, a few kilometres below '
            'the hill town of Labin. A curved bay of pebble beaches and a promenade give it'
            ' a holiday character, and the Kvarner coast and island of Cres are visible '
            'across the water.'
        ),
        'highlights': [
            'Pebble beaches around the bay',
            'Seafront promenade',
            'Coastal walking paths',
            'Boat trips along the coast',
            'Nearby Labin old town',
        ],
        'overview': (
            'Rabac began as a small fishing village on a bay below Labin and developed into'
            ' a tourist resort from the late 19th century onward. Today it has a string of '
            'pebble beaches along a sheltered bay, backed by a promenade with cafés and '
            'restaurants. Coastal paths run along the shore beyond the bay to small coves, '
            'and in summer boats run along the coast. Across the water lies the island of '
            'Cres, and the hills of the Kvarner coast rise behind. Rabac is quieter than '
            'the west coast resorts, and it is often combined with a visit to the old town '
            'of Labin, which stands on the hill above it.'
        ),
        'faqs': [
            {
                'q': 'Is Rabac worth visiting?',
                'a': (
                    'Yes, for a beach stay on the east coast of Istria, combined with a '
                    'visit to Labin.'
                ),
            },
            {
                'q': 'How do I get to Rabac?',
                'a': (
                    'Rabac is roughly 55 km from Pula Airport (PUY) by road, a few '
                    'kilometres below Labin.'
                ),
            },
            {
                'q': 'What is there to do in Rabac?',
                'a': (
                    'Swim at the pebble beaches, walk the promenade and coastal paths, take'
                    ' a boat trip and visit Labin above.'
                ),
            },
            {
                'q': 'How long should I spend in Rabac?',
                'a': 'A day for the beach, or several days for a seaside stay.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming',
            },
            {
                'label': 'Ideal for',
                'value': 'Beach stays, families, coastal walks',
            },
            {
                'label': 'Time needed',
                'value': 'A day to several days',
            },
            {
                'label': 'Getting there',
                'value': 'Roughly 55 km by road from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 55 km',
            },
        ],
        'good_for': [
            'beach holidays',
            'families',
            'swimming',
            'walkers',
            'couples',
        ],
        'sections': [
            {
                'heading': 'From fishing village to resort',
                'body': (
                    'Rabac grew from a handful of fishermen’s houses into a tourist town as'
                    ' visitors came to Labin and the east coast. Hotels and villas were '
                    'built along the bay over the 20th century, and the seafront today is a'
                    ' mix of older houses and newer resort buildings.'
                ),
            },
            {
                'heading': 'Beaches and the sea',
                'body': (
                    'The beaches around the bay are mainly pebbles, with clear shallow '
                    'water. Coastal paths lead to quieter coves, and boats run along the '
                    'coast in season. The view across to Cres and the Kvarner coast is a '
                    'feature of the east coast.'
                ),
            },
            {
                'heading': 'With Labin above',
                'body': (
                    'The old town of Labin is a short drive uphill and is worth a visit for'
                    ' its lanes, museum and viewpoints. Many visitors split a day between '
                    'the two, with the old town in the morning and the beach later.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Rabac — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Rabac',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.0792,
        'longitude': 14.1536,
    },
    {
        'name': 'Vodnjan',
        'slug': 'vodnjan',
        'region': 'istria',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A small town in southern Istria, north of Pula, known for its church of St '
            'Blaise and its olive growing.'
        ),
        'description': (
            'Vodnjan (Dignano in Italian) is a small town in southern Istria, about 10 km '
            'north of Pula. Its church of St Blaise holds a collection of sacred art that '
            'includes the preserved remains of several saints, and the surrounding land is '
            'known for olive growing.'
        ),
        'highlights': [
            'Church of St Blaise and its sacred art collection',
            'Old town and the main square',
            'Olive groves and oil',
            'Nearby Brijuni islands',
            'Short drive to Pula',
        ],
        'overview': (
            'Vodnjan lies on the red-soil plain of southern Istria, a short distance north '
            'of Pula. The old town has narrow streets and a main square, and the large '
            'church of St Blaise (Sv. Blaž) dominates it. Inside, the collection of sacred '
            'art includes the preserved bodies of saints, a feature that draws many '
            'visitors. The town has an Italian-speaking community, and Italian and Croatian'
            ' are both used on local signs. The land around Vodnjan is covered in olive '
            'groves, and olive oil from the area is sold from local farms and shops. The '
            'coast at Fažana, from which boats leave for the Brijuni islands, is a few '
            'kilometres west.'
        ),
        'faqs': [
            {
                'q': 'Is Vodnjan worth visiting?',
                'a': (
                    'Yes, as a short stop north of Pula for its church and its olive-'
                    'growing countryside.'
                ),
            },
            {
                'q': 'How do I get to Vodnjan?',
                'a': (
                    'Vodnjan is about 10 km north of Pula and close to Pula Airport (PUY). '
                    'It is reached by road and local bus.'
                ),
            },
            {
                'q': 'What is there to do in Vodnjan?',
                'a': (
                    'Visit the church of St Blaise and its collection, walk the old town, '
                    'taste local olive oil and use the town as a stop on the way to Fažana '
                    'and Brijuni.'
                ),
            },
            {
                'q': 'How long should I spend in Vodnjan?',
                'a': 'One to two hours cover the town.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Short stops, sacred art, olive oil',
            },
            {
                'label': 'Time needed',
                'value': 'One to two hours',
            },
            {
                'label': 'Getting there',
                'value': 'About 10 km north of Pula by road',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 10 km',
            },
        ],
        'good_for': [
            'cultural heritage',
            'food lovers',
            'road trips',
            'history lovers',
            'day trips from Pula',
        ],
        'sections': [
            {
                'heading': 'A town of the red plain',
                'body': (
                    'Vodnjan sits on the fertile plain of southern Istria, where the soil '
                    'is red and the land is farmed. The old town developed around its '
                    'parish church and keeps the layout of a market town. Italian is still '
                    'widely spoken alongside Croatian.'
                ),
            },
            {
                'heading': 'The church of St Blaise',
                'body': (
                    'The Baroque church of St Blaise is the largest parish church in '
                    'Istria, and its collection of sacred art within the church complex '
                    'includes the preserved remains of saints. A visit usually takes under '
                    'an hour. Visitors should dress respectfully, as it is an active place '
                    'of worship.'
                ),
            },
            {
                'heading': 'Olive oil country',
                'body': (
                    'The land around Vodnjan is part of one of the main olive-growing areas'
                    ' of Istria, and local farms produce oil that is sold in shops and from'
                    ' the farms themselves. Fažana and the boats to Brijuni are a few '
                    'kilometres to the west, making Vodnjan a good halfway stop.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Vodnjan — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Vodnjan',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.9606,
        'longitude': 13.8556,
    },
    {
        'name': 'Brijuni National Park',
        'slug': 'brijuni-national-park',
        'region': 'istria',
        'place_type': 'national_parks',
        'featured': False,
        'summary': (
            'A national park of fourteen islands off the southwest coast of Istria, reached'
            ' by boat from Fažana.'
        ),
        'description': (
            'Brijuni is an archipelago of fourteen islands just off the southwest coast of '
            'Istria, protected as a national park since 1983. Visitors reach the largest '
            'island, Veli Brijun, by boat from Fažana, and see Roman remains, parkland and '
            'a small safari park.'
        ),
        'highlights': [
            'Veli Brijun island and its parkland',
            'Roman villa remains at Verige Bay',
            'Safari park and zoo',
            'Dinosaur footprints',
            'Boat trip from Fažana',
        ],
        'overview': (
            'The Brijuni islands lie a few kilometres off the southwest coast of Istria, '
            'opposite the village of Fažana. Of the fourteen islands, Veli Brijun is the '
            'largest and is the one most visitors see. Much of the group was used as a '
            'presidential summer residence by Josip Broz Tito from 1947, and was later '
            'opened to visitors; it has been a national park since 1983. The islands hold '
            'Roman and Byzantine remains, including a large Roman villa complex at Verige '
            'Bay, and traces of dinosaur footprints in the rock. A small safari park and a '
            'collection of Mediterranean plants and animals, some given as gifts to Tito, '
            'add to the visit. Access is by boat from Fažana, and the park manages visitor '
            'numbers and routes.'
        ),
        'faqs': [
            {
                'q': 'Is Brijuni National Park worth visiting?',
                'a': ('Yes, for a day out combining nature, history and a boat trip from Istria.'),
            },
            {
                'q': 'How do I get to Brijuni?',
                'a': (
                    'Boats run from Fažana, which is roughly 20 km from Pula Airport (PUY) '
                    'by road. Check the national park’s website for current sailing '
                    'arrangements.'
                ),
            },
            {
                'q': 'What is there to do on Brijuni?',
                'a': (
                    'Tour Veli Brijun, see the Roman remains, visit the safari park and '
                    'walk or cycle through the parkland.'
                ),
            },
            {
                'q': 'How long should I spend on Brijuni?',
                'a': 'A half day to a full day, depending on the programme chosen.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Nature, history, day trips',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'Boat from Fažana, roughly 20 km from Pula Airport (PUY)',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 20 km',
            },
        ],
        'good_for': [
            'nature',
            'history lovers',
            'families',
            'day trips',
            'cyclists',
        ],
        'sections': [
            {
                'heading': 'An archipelago with a long history',
                'body': (
                    'People have lived on the islands since prehistoric times, and the '
                    'Romans built villas and farms there. In the late 19th century, the '
                    'industrialist Paul Kupelwieser bought the islands and turned them into'
                    ' a health resort. Later they became the summer residence of Tito, '
                    'which shaped much of what visitors see today.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'On Veli Brijun, visitors travel by small train or bicycle through '
                    'parkland, past the remains of the Roman villa at Verige Bay, a '
                    'Byzantine fortress, and a small safari park. Dinosaur footprints can '
                    'be seen on some of the islands’ shores. A museum on the island covers '
                    'its natural and cultural history.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Visits are organised through the national park, with boats from Fažana'
                    ' to Veli Brijun. Details of sailings and programmes should be '
                    'confirmed with the park before travel. Fažana can be combined with a '
                    'stop in nearby Vodnjan and a return to Pula.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Brijuni National Park — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Brijuni',
            },
            {
                'label': 'Brijuni National Park',
                'url': 'https://www.np-brijuni.hr/en',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.9144,
        'longitude': 13.7639,
    },
    {
        'name': 'Cape Kamenjak',
        'slug': 'cape-kamenjak',
        'region': 'istria',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A wild, rocky peninsula at the southern tip of Istria, with coves, low scrub '
            'and a protected coastline.'
        ),
        'description': (
            'Cape Kamenjak is the southernmost tip of Istria, a flat limestone peninsula '
            'near Premantura with rocky coves, low scrub and a protected coastline. Dirt '
            'tracks and paths cross it, and several small islands lie off its shore.'
        ),
        'highlights': [
            'Rocky coves for swimming',
            'Walking and cycling tracks',
            'Offshore islets',
            'Dinosaur footprints on the shore',
            'Views south to the Kvarner Bay',
        ],
        'overview': (
            'Kamenjak is a narrow peninsula at the very southern tip of Istria, close to '
            'the village of Premantura and about 10 km from Pula. The land is low and '
            'rocky, covered in Mediterranean scrub and open meadows, with a coast of '
            'limestone ledges and small coves. It is protected as a nature area, and the '
            'paths and tracks that cross it are used for walking and cycling. Swimming '
            'spots are mostly rock platforms and small pebble coves with clear water. '
            'Several small islands lie just offshore, and traces of dinosaur footprints can'
            ' be seen in the rock. The peninsula is mostly undeveloped, with few '
            'facilities, so visitors should bring water, sun protection and suitable '
            'footwear. It is a popular day trip from Pula and from the nearby resorts.'
        ),
        'faqs': [
            {
                'q': 'Is Cape Kamenjak worth visiting?',
                'a': (
                    'Yes, for a natural, undeveloped stretch of coast with swimming and '
                    'walking close to Pula.'
                ),
            },
            {
                'q': 'How do I get to Cape Kamenjak?',
                'a': (
                    'Kamenjak is about 10 km from Pula, via Premantura. Pula Airport (PUY) '
                    'is roughly 20 km away by road. Access to the peninsula may be subject '
                    'to an entry fee or restrictions, so check locally.'
                ),
            },
            {
                'q': 'What is there to do at Cape Kamenjak?',
                'a': (
                    'Swim from the rocks and coves, walk or cycle the tracks, and look for '
                    'the small islands and the dinosaur footprints.'
                ),
            },
            {
                'q': 'How long should I spend at Cape Kamenjak?',
                'a': 'Half a day to a full day, depending on how far you walk or cycle.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Swimming, walking, cycling, nature',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road via Premantura, about 10 km from Pula',
            },
            {
                'label': 'Region',
                'value': 'Istria',
            },
            {
                'label': 'Nearest airport',
                'value': 'Pula Airport (PUY), roughly 20 km',
            },
        ],
        'good_for': [
            'nature',
            'swimming',
            'cyclists',
            'walkers',
            'families',
        ],
        'sections': [
            {
                'heading': 'The southern tip of Istria',
                'body': (
                    'Kamenjak forms the southern end of the peninsula, with the Kvarner Bay'
                    ' to the east and the Adriatic to the west. The land is flat and open, '
                    'shaped by limestone and shrubby vegetation, and it has remained '
                    'largely undeveloped. The protected status keeps building to a minimum.'
                ),
            },
            {
                'heading': 'What to do',
                'body': (
                    'Tracks run across the peninsula to the shore, and cycling is a common '
                    'way to explore. The coastline offers many places to swim, mostly from '
                    'rock ledges or small coves. In some spots, the shoreline preserves '
                    'dinosaur footprints. Facilities are limited, so bring what you need '
                    'for the day.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Kamenjak is reached through Premantura, a short drive south of Pula. '
                    'Entry arrangements and fees can change, so check locally before you '
                    'go. Late afternoon and early evening are cooler, and the peninsula '
                    'offers open views over the sea.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Premantura — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Premantura',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.7667,
        'longitude': 13.9167,
    },
]
