"""Croatia catalogue: places in the Zadar and Šibenik regions.

Real destinations with editorial text, coordinates and links, for the
`seed_croatia` command. Each dict follows the schema in
`docs/plans/croatia-catalogue-2026-11.md`.
"""

from __future__ import annotations

PLACES: list[dict] = [
    {
        'name': 'Zadar',
        'slug': 'zadar',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Zadar_BW_2024-09-29_10-04-47.jpg/1280px-Zadar_BW_2024-09-29_10-04-47.jpg',
            'author': 'Berthold Werner',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Zadar_BW_2024-09-29_10-04-47.jpg',
        },
        'region': 'zadar',
        'place_type': 'cities',
        'featured': True,
        'summary': (
            'A Dalmatian city on a peninsula, with Roman ruins, Venetian walls and the Sea Organ '
            'on its waterfront.'
        ),
        'description': (
            'Zadar’s old town sits on a narrow peninsula, with a Roman forum, the round Church of'
            ' St Donatus and Venetian-era walls inside a compact pedestrian centre. On the '
            'western waterfront, the Sea Organ and the Greeting to the Sun are modern '
            'installations by the architect Nikola Bašić. Ferries cross to the nearby islands.'
        ),
        'highlights': [
            'Roman Forum and Church of St Donatus',
            'Sea Organ and Greeting to the Sun',
            'Cathedral of St Anastasia and its bell tower',
            'Five Wells Square and the Land Gate',
            'Kalelarga, the main pedestrian street',
        ],
        'overview': (
            'Zadar has been settled since antiquity; the Romans called it Iader, and the remains '
            'of their forum still lie at the centre of the old town beside the Church of St '
            'Donatus, a round building from the ninth century. Venice bought the city in 1409 and'
            ' held it until 1797, and the ramparts and the Land Gate from that period are part of'
            ' the Venetian defence works inscribed by UNESCO in 2017. Much of the old town was '
            'destroyed by bombing in the Second World War and rebuilt. Today the peninsula is a '
            'walkable mix of churches, squares and cafés, with Kalelarga running through it from '
            'the Land Gate. On the western tip, the Sea Organ (2005) turns the movement of the '
            'sea into sound, and the Greeting to the Sun lies beside it. Zadar is also the main '
            'starting point for the islands and national parks of northern Dalmatia.'
        ),
        'faqs': [
            {
                'q': 'Is Zadar worth visiting?',
                'a': (
                    'Yes. The old town packs Roman, medieval and Venetian layers into a small '
                    'pedestrian area, and the waterfront installations are a draw in themselves. '
                    'It is also a practical base for the islands, Paklenica and Krka.'
                ),
            },
            {
                'q': 'How do I get to Zadar?',
                'a': (
                    'Zadar Airport (ZAD) is around 10 km from the centre. The city also has a bus'
                    ' station, a ferry port and road links via the A1 motorway, and Split Airport'
                    ' (SPU) is the alternative gateway.'
                ),
            },
            {
                'q': 'What is there to do in Zadar?',
                'a': (
                    'Walk the old town, see the Roman Forum and St Donatus, listen to the Sea '
                    'Organ at sunset, climb the cathedral bell tower and take a ferry to Ugljan '
                    'or another island.'
                ),
            },
            {
                'q': 'How long should I spend in Zadar?',
                'a': (
                    'One full day covers the old town; two or three nights lets you add island '
                    'trips and a day at a national park.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–June and September–October; July–August for swimming and island trips',
            },
            {
                'label': 'Ideal for',
                'value': 'City breaks, history, island hopping',
            },
            {
                'label': 'Time needed',
                'value': 'One to two days',
            },
            {
                'label': 'Getting there',
                'value': 'Zadar Airport (ZAD) about 10 km; bus, ferry and A1 motorway links',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'city breaks',
            'history lovers',
            'island hopping',
            'couples',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'A layered old town',
                'body': (
                    'The old town is only a few hundred metres wide, so the layers sit close '
                    'together. The Roman forum, the pre-Romanesque Church of St Donatus and the '
                    'Romanesque Cathedral of St Anastasia all share the same area. Narrow lanes '
                    'lead off Kalelarga to small squares, and the walls on the harbour side are '
                    'open to walk along.'
                ),
            },
            {
                'heading': 'The waterfront',
                'body': (
                    'Nikola Bašić’s Sea Organ, opened in 2005, hides pipes under marble steps so '
                    'that waves produce tones as they push air through. Next to it, the Greeting '
                    'to the Sun is a ring of glass plates set into the pavement that lights up '
                    'after dark. Both are on the Riva at the western end of the peninsula, a '
                    'short walk from the cathedral.'
                ),
            },
            {
                'heading': 'Beyond the walls',
                'body': (
                    'From the harbour, ferries and catamarans run to islands such as Ugljan and '
                    'Dugi Otok, and boat excursions leave for the Kornati and Telašćica. By road,'
                    ' Nin, Vrana Lake and the Paklenica canyons are each within a day trip. '
                    'Zadar’s mix of old stone and sea makes it an easy first stop on a Dalmatian '
                    'itinerary.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Zadar — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Zadar',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.1194,
        'longitude': 15.2314,
    },
    {
        'name': 'Nin',
        'slug': 'nin',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Crkva_sv._Kri%C5%BEa_u_Ninu_2010.jpg/1280px-Crkva_sv._Kri%C5%BEa_u_Ninu_2010.jpg',
            'author': 'Pudelek (Marcin Szala)',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Crkva_sv._Kri%C5%BEa_u_Ninu_2010.jpg',
        },
        'region': 'zadar',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A small lagoon town north of Zadar with early Croatian history, salt pans and a long'
            ' sandy beach.'
        ),
        'description': (
            'Nin is an old town on a tiny island in a shallow lagoon, linked to the mainland by '
            'two bridges. It was an early seat of Croatian rulers and keeps the Church of the '
            'Holy Cross, a small ninth-century church. Nearby are salt pans and Queen’s Beach, '
            'one of the few sandy beaches on this stretch of coast.'
        ),
        'highlights': [
            'Church of the Holy Cross',
            'Statue of Grgur Ninski (Gregory of Nin)',
            'Nin salt pans',
            'Queen’s Beach (Kraljičina plaža)',
            'Walk across the bridges into the old town',
        ],
        'overview': (
            'Nin lies about 17 km north of Zadar, on an islet in a shallow lagoon that is '
            'connected to the mainland by two stone bridges. In the early Middle Ages it was one '
            'of the centres of the Croatian state, and a seat of the early Croatian rulers and of'
            ' a bishopric. The bishop Grgur Ninski, who argued for the use of the Croatian '
            'language in church services, is remembered by a large bronze statue by Ivan '
            'Meštrović, which stands just inside the old town. The little Church of the Holy '
            'Cross dates from the ninth century and is the best-known building here. Outside the '
            'walls, the lagoon is used for salt production, and Queen’s Beach, a long shallow '
            'sandy beach, draws families in summer. The old town can be walked in under an hour.'
        ),
        'faqs': [
            {
                'q': 'Is Nin worth visiting?',
                'a': (
                    'Yes, for a short stop. It is a small old town with early Croatian history, '
                    'quiet streets and sandy shallows, and it combines easily with a day in '
                    'Zadar.'
                ),
            },
            {
                'q': 'How do I get to Nin?',
                'a': (
                    'Nin is about 17 km north of Zadar by road, and Zadar Airport (ZAD) is the '
                    'nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Nin?',
                'a': (
                    'Walk through the old town, see the Church of the Holy Cross and the statue '
                    'of Grgur Ninski, visit the salt pans and spend time on Queen’s Beach.'
                ),
            },
            {
                'q': 'How long should I spend in Nin?',
                'a': (
                    'A half day is enough for the old town and the beach; stay longer if you want'
                    ' to use it as a quiet base near Zadar.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for the beach; May and September for walking',
            },
            {
                'label': 'Ideal for',
                'value': 'Families, history, a quiet beach day',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day',
            },
            {
                'label': 'Getting there',
                'value': 'About 17 km north of Zadar by road',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'families',
            'history lovers',
            'beach days',
            'short stops',
            'quiet breaks',
        ],
        'sections': [
            {
                'heading': 'An early Croatian centre',
                'body': (
                    'Nin was already an important town in the early Middle Ages, and it is linked'
                    ' with the first Croatian rulers and with early church organisation in the '
                    'region. Today the small town holds an archaeological museum and the old '
                    'church, and the layout inside the walls is easy to follow on foot.'
                ),
            },
            {
                'heading': 'Salt and sand',
                'body': (
                    'The shallow lagoon around Nin has been used to make salt for a very long '
                    'time, and a working salt pan can still be seen. Beyond the pans, Queen’s '
                    'Beach is a long stretch of fine sand with very shallow water, which makes it'
                    ' popular with families. The lagoon’s mud is also used locally for skin '
                    'treatments, mainly in summer.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Nin is close enough to Zadar to see in half a day. Bring sun cover for the '
                    'open beach and salt pans, where shade is limited. In the evening, the old '
                    'town is quiet, and the walk back over the bridge gives a view of the lagoon '
                    'and the Velebit mountains on a clear day.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Nin — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Nin,_Croatia',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.2406,
        'longitude': 15.1789,
    },
    {
        'name': 'Pag',
        'slug': 'pag',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Basilica_of_the_Assumption_of_Mary%2C_Pag_01.jpg/1280px-Basilica_of_the_Assumption_of_Mary%2C_Pag_01.jpg',
            'author': 'Bernard Gagnon',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Basilica_of_the_Assumption_of_Mary,_Pag_01.jpg',
        },
        'region': 'zadar',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A salt-and-lace town on the island of Pag, known for its cheese, its stone landscape'
            ' and the old town laid out in 1443.'
        ),
        'description': (
            'Pag town lies on the island of Pag, a long, treeless island known for sheep’s '
            'cheese, lace and salt. The old town was planned in the fifteenth century by Juraj '
            'Dalmatinac, and the salt pans next to it are still in use. The island is joined to '
            'the mainland by the Pag Bridge.'
        ),
        'highlights': [
            'Old town laid out by Juraj Dalmatinac',
            'Pag lace',
            'Pag salt pans',
            'Paški sir (Pag cheese)',
            'The Pag Bridge and the stone landscape',
        ],
        'overview': (
            'The island of Pag is long and narrow, with bare, stony slopes shaped by the strong '
            'bora wind. Sheep graze the sparse vegetation, and their milk is made into Paški sir,'
            ' the island’s best-known product. Pag town sits at the head of a bay in the middle '
            'of the island. Its old town was laid out from 1443 to a plan by the architect Juraj '
            'Dalmatinac, who also worked on the cathedral in Šibenik, with a regular grid of '
            'streets around a central square and the parish church. Pag lace, a needle lace made '
            'by hand, has a long tradition here. The salt pans beside the town have been '
            'producing salt for centuries. The island is reached over the Pag Bridge from the '
            'mainland, or by ferry from Prizna to Žigljen in the north.'
        ),
        'faqs': [
            {
                'q': 'Is Pag worth visiting?',
                'a': (
                    'Yes, if you like an unusual landscape, local food and handmade crafts. Pag '
                    'cheese, lace and salt are all connected to the town, and the sea beyond is '
                    'clear.'
                ),
            },
            {
                'q': 'How do I get to Pag?',
                'a': (
                    'Pag town is reached by road over the Pag Bridge from the mainland; Zadar '
                    'Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Pag?',
                'a': (
                    'Walk the old town, look at Pag lace, taste Pag cheese, visit the salt pans '
                    'and drive across the island’s stone landscape.'
                ),
            },
            {
                'q': 'How long should I spend in Pag?',
                'a': (
                    'A half day to a day is enough for the town; add more time if you plan to '
                    'explore the island’s beaches.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Local food, crafts, landscape',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'Road over the Pag Bridge from the mainland; ferry Prizna–Žigljen in the north',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'food lovers',
            'crafts',
            'landscape drives',
            'short stops',
            'couples',
        ],
        'sections': [
            {
                'heading': 'The town plan',
                'body': (
                    'Juraj Dalmatinac, who was born in Zadar and also worked on the cathedral in '
                    'Šibenik, drew up the plan for the new town of Pag in the fifteenth century. '
                    'The square grid of streets and the central open space are still easy to '
                    'read. Walk from the main square through the lanes to the harbour and out '
                    'toward the salt pans.'
                ),
            },
            {
                'heading': 'Lace, cheese and salt',
                'body': (
                    'Pag lace is a needle lace made by hand and is a long-standing local craft. '
                    'Paški sir is a hard cheese made from the milk of the island’s sheep, which '
                    'feed on herbs and salt-sprayed plants. The pans next to the town produce sea'
                    ' salt, and all three products can be bought in and around the old town.'
                ),
            },
            {
                'heading': 'The island',
                'body': (
                    'The Pag Bridge, opened in 1968, links the island to the mainland. The '
                    'landscape on the northern part of the island is stony and bare, while the '
                    'coast has many small beaches and bays. Keep in mind that the bora can be '
                    'strong, so check the wind and ferry status before crossing on a rough day.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Pag (island) — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Pag_(island)',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.444,
        'longitude': 15.059,
    },
    {
        'name': 'Novalja',
        'slug': 'novalja',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Novalja_Hafen.jpg/1280px-Novalja_Hafen.jpg',
            'author': 'Palauenc05',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Novalja_Hafen.jpg',
        },
        'region': 'zadar',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small town on the island of Pag, with a long beach at Zrće and Roman remains near '
            'the town.'
        ),
        'description': (
            'Novalja is on the northern part of the island of Pag. It is best known for Zrće, a '
            'long pebble beach with bars and clubs in summer. Away from the beach, the town has '
            'Roman remains, including an aqueduct tunnel, and a museum.'
        ),
        'highlights': [
            'Zrće beach',
            'Roman aqueduct tunnel (Talijanova buža)',
            'Novalja city museum',
            'Caska bay and ruins',
            'Boat trips along the coast',
        ],
        'overview': (
            'Novalja lies on the northern part of the island of Pag, by the sea. Zrće, a few '
            'kilometres from the centre, is a pebble beach lined with bars and clubs that has '
            'become a destination for music events in summer; outside the season it is quiet. The'
            ' town itself has a long history: under the Romans, Novalja was a settlement called '
            'Navalia, and a stone tunnel carrying water to the town survives, known locally as '
            'Talijanova buža. The city museum shows finds from the area. Beyond the town, the '
            'island has many small beaches and coves, and the ruins at Caska in a nearby bay are '
            'reachable on foot or by boat. Ferries run from Žigljen to Prizna, on the mainland.'
        ),
        'faqs': [
            {
                'q': 'Is Novalja worth visiting?',
                'a': (
                    'Yes, particularly in summer if you want a lively beach, or in the shoulder '
                    'season if you prefer quiet coves and Roman remains.'
                ),
            },
            {
                'q': 'How do I get to Novalja?',
                'a': (
                    'Novalja is on the northern part of the island of Pag. You can drive over the'
                    ' Pag Bridge or take the ferry from Prizna on the mainland to Žigljen, then '
                    'continue by road. Zadar Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Novalja?',
                'a': (
                    'Spend time at Zrće, visit the Roman aqueduct tunnel and the city museum, '
                    'explore the coast by boat and walk to Caska.'
                ),
            },
            {
                'q': 'How long should I spend in Novalja?',
                'a': 'A day covers the town and a beach; stay several nights for island exploration.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for the beach scene; May and September for quieter stays',
            },
            {
                'label': 'Ideal for',
                'value': 'Beach days, nightlife in summer, Roman remains',
            },
            {
                'label': 'Time needed',
                'value': 'One day or more',
            },
            {
                'label': 'Getting there',
                'value': 'Over the Pag Bridge by road, or ferry Prizna–Žigljen',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'beach holidays',
            'nightlife',
            'history lovers',
            'boat trips',
            'groups of friends',
        ],
        'sections': [
            {
                'heading': 'Roman Navalia',
                'body': (
                    'In Roman times Novalja was a settlement known as Navalia. A stone tunnel '
                    'that carried water to it, can be seen and walked through near the town. The '
                    'small city museum shows finds from the area, including objects from the '
                    'Roman period.'
                ),
            },
            {
                'heading': 'Zrće and the coast',
                'body': (
                    'Zrće is a long pebble beach a short distance from town that is lined with '
                    'beach bars and clubs, mainly active from late June to early September. At '
                    'other times it is quiet. The rest of the coast near Novalja has smaller '
                    'coves, some reachable only by boat or on foot.'
                ),
            },
            {
                'heading': 'Getting around',
                'body': (
                    'The ferry crossing from Prizna to Žigljen is short, and the road across the '
                    'island from the bridge side is slower in high season. Plan extra time in '
                    'July and August, and book overnight stays early if you want to be close to '
                    'the beach.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Novalja — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Novalja',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.5578,
        'longitude': 14.8856,
    },
    {
        'name': 'Kornati National Park',
        'slug': 'kornati-national-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/Kornati_2.JPG/1280px-Kornati_2.JPG',
            'author': 'Ivana',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0/',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Kornati_2.JPG',
        },
        'region': 'zadar',
        'place_type': 'national_parks',
        'featured': False,
        'summary': (
            'A national park of dozens of mostly uninhabited islands, with dry-stone walls, '
            'cliffs on the open-sea side and many sheltered bays.'
        ),
        'description': (
            'Kornati National Park protects part of the Kornati archipelago, a group of dozens of'
            ' islands, islets and reefs. Most are uninhabited, bare and stony, divided by dry-'
            'stone walls. The park is visited by boat, with trips leaving from Murter, Zadar, '
            'Biograd, Šibenik and other towns.'
        ),
        'highlights': [
            'Boat day trip through the islands',
            'Dry-stone walls and old sheep pastures',
            'Cliffs on the open-sea side',
            'Swimming and snorkelling in sheltered bays',
            'Seasonal restaurants in coves',
        ],
        'overview': (
            'The Kornati archipelago is a scatter of limestone islands lying between Zadar and '
            'Šibenik. The national park, declared in 1980, covers the larger part of it, with '
            'some eighty islands, islets and reefs. The islands are bare of tall trees, with low '
            'scrub and grass, and are crossed by dry-stone walls built by farmers who came over '
            'from other islands to graze sheep and tend olives. Seen from a boat, the cliffs on '
            'the seaward side contrast with the quieter bays on the inner side. Most visitors '
            'come on an organised boat day trip, or by their own boat, and there are a few '
            'restaurants in coves that serve visitors in season. Access is regulated: you need a '
            'park ticket; rules cover anchoring, fishing and landing.'
        ),
        'faqs': [
            {
                'q': 'Is Kornati National Park worth visiting?',
                'a': (
                    'Yes, if you enjoy boat trips and quiet, bare landscapes. There are few '
                    'buildings, many small bays and clear water, which suits swimming and '
                    'snorkelling.'
                ),
            },
            {
                'q': 'How do I get to Kornati?',
                'a': (
                    'The park is reached by boat. Day trips depart from places such as Murter, '
                    'Zadar, Biograd na Moru and Šibenik, and Zadar Airport (ZAD) and Split '
                    'Airport (SPU) are the nearest airports.'
                ),
            },
            {
                'q': 'What is there to do in Kornati?',
                'a': (
                    'Cruise through the islands, swim and snorkel in the bays, walk to a '
                    'viewpoint where a trail is open and eat in one of the seasonal restaurants.'
                ),
            },
            {
                'q': 'How long should I spend in Kornati?',
                'a': 'Most trips last a day; sailors often spend a few nights.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September; July–August is the busiest',
            },
            {
                'label': 'Ideal for',
                'value': 'Boat trips, sailing, swimming',
            },
            {
                'label': 'Time needed',
                'value': 'One day',
            },
            {
                'label': 'Getting there',
                'value': 'By boat from Murter, Zadar, Biograd, Šibenik and other ports',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD) or Split Airport (SPU)',
            },
        ],
        'good_for': [
            'sailing',
            'boat trips',
            'swimming and snorkelling',
            'photographers',
            'quiet landscapes',
        ],
        'sections': [
            {
                'heading': 'A landscape shaped by shepherds',
                'body': (
                    'Tall trees are rare on the islands. The pattern of low stone walls you see '
                    'today was built by farmers, mostly from the island of Murter, who owned '
                    'plots here and visited to tend sheep and olive trees. Some of their small '
                    'stone houses are still used.'
                ),
            },
            {
                'heading': 'Seen from the water',
                'body': (
                    'The outer, open-sea side of many islands drops in steep cliffs, while the '
                    'inner side has gentler shores and shallow coves. The park also protects the '
                    'sea around the islands, so rules cover anchoring and fishing. Boats stop in '
                    'bays where this is allowed, and you can swim from the deck.'
                ),
            },
            {
                'heading': 'Visiting the park',
                'body': (
                    'A ticket is required to enter, and the park office is in Murter. A few '
                    'trails and viewpoints are signposted on the larger islands. Bring sun '
                    'protection, water and shoes for stony paths; shade is scarce.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Kornati — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Kornati',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.8,
        'longitude': 15.3,
    },
    {
        'name': 'Paklenica National Park',
        'slug': 'paklenica-national-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/NP05_Paklenica_Lika-Senj_1.jpg/1280px-NP05_Paklenica_Lika-Senj_1.jpg',
            'author': 'Miroslav.vajdic',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:NP05_Paklenica_Lika-Senj_1.jpg',
        },
        'region': 'zadar',
        'place_type': 'national_parks',
        'featured': False,
        'summary': (
            'A national park in the southern Velebit mountains, known for two karst canyons, '
            'hiking trails and rock climbing.'
        ),
        'description': (
            'Paklenica National Park lies in the southern part of the Velebit mountains, above '
            'the village of Starigrad-Paklenica on the coast. Its two canyons, Mala and Velika '
            'Paklenica, have steep limestone walls and are popular for hiking and rock climbing. '
            'The park also protects beech and pine forest, caves and mountain pastures.'
        ),
        'highlights': [
            'Velika Paklenica canyon',
            'Mala Paklenica canyon',
            'Rock climbing on Anića kuk',
            'Manita peć cave',
            'Mountain hiking trails',
        ],
        'overview': (
            'Paklenica National Park was established in 1949 and covers part of the southern '
            'Velebit range, a limestone mountain that runs along the Adriatic coast. The two '
            'canyons, Mala Paklenica and Velika Paklenica, cut into the mountain from the sea '
            'side, with walls that rise hundreds of metres. A marked path follows the floor of '
            'Velika Paklenica, and from there routes climb to mountain huts and higher peaks. '
            'Climbers come to the cliffs for routes of many grades, including the big wall of '
            'Anića kuk. The park also holds caves, including Manita peć, which can be visited '
            'with the park’s guides when it is open. The nearest village is Starigrad-Paklenica '
            'on the coastal road, where the main park entrance is. In summer, mornings are best '
            'for the canyon floor, since the afternoons are hot.'
        ),
        'faqs': [
            {
                'q': 'Is Paklenica National Park worth visiting?',
                'a': (
                    'Yes, for hikers and climbers. The canyons are dramatic, the trails are '
                    'marked and the park is a short drive from the sea.'
                ),
            },
            {
                'q': 'How do I get to Paklenica?',
                'a': (
                    'The park entrance is at Starigrad-Paklenica on the D8 coastal road, roughly '
                    '45 km from Zadar. Zadar Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Paklenica?',
                'a': (
                    'Walk through Velika Paklenica, hike to mountain huts, climb on the canyon '
                    'walls and visit Manita peć cave when it is open.'
                ),
            },
            {
                'q': 'How long should I spend in Paklenica?',
                'a': (
                    'A day is enough for the canyon walk; two or more days if you plan to climb '
                    'or reach the higher trails.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–June and September–October for hiking; summer mornings for the canyon',
            },
            {
                'label': 'Ideal for',
                'value': 'Hiking, rock climbing, nature',
            },
            {
                'label': 'Time needed',
                'value': 'One day or more',
            },
            {
                'label': 'Getting there',
                'value': 'Starigrad-Paklenica on the D8 coastal road, about 45 km from Zadar',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'hiking',
            'rock climbing',
            'nature lovers',
            'active families',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'The canyons',
                'body': (
                    'Velika Paklenica is the larger of the two canyons and the more visited. A '
                    'path follows its floor for several kilometres, with the limestone walls '
                    'rising on both sides. Mala Paklenica is narrower and quieter, with a trail '
                    'through the gorge that can be done as a shorter outing. Both start close to '
                    'Starigrad-Paklenica.'
                ),
            },
            {
                'heading': 'Climbing and hiking',
                'body': (
                    'The walls of the canyon, and the faces of Anića kuk, have routes of varied '
                    'difficulty and are used by climbers from many countries. Hikers can follow '
                    'marked paths to mountain huts and the high plateaus, where the landscape '
                    'opens into pasture and forest. Check conditions with the park before heading'
                    ' uphill.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Tickets are bought at the park entrance. Wear shoes with grip and carry '
                    'water; there is little shade on the canyon floor in summer. Storms and wind '
                    'on the upper slopes can change quickly, so start early and keep time to '
                    'return.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Paklenica — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Paklenica',
            },
            {
                'label': 'Paklenica National Park',
                'url': 'https://np-paklenica.hr/',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.35,
        'longitude': 15.4667,
    },
    {
        'name': 'Telašćica Nature Park',
        'slug': 'telascica-nature-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Tela%C5%A1%C4%87ica_Cliff.jpg/1280px-Tela%C5%A1%C4%87ica_Cliff.jpg',
            'author': 'julien',
            'licence': 'CC BY 2.0',
            'licence_url': 'https://creativecommons.org/licenses/by/2.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Tela%C5%A1%C4%87ica_Cliff.jpg',
        },
        'region': 'zadar',
        'place_type': 'national_parks',
        'featured': False,
        'summary': (
            'A large natural bay on the south-eastern end of Dugi Otok, with high sea cliffs, '
            'islets and the salt lake Mir.'
        ),
        'description': (
            'Telašćica is a large, sheltered bay at the south-eastern end of Dugi Otok, protected'
            ' as a nature park since 1988. On its seaward side, cliffs rise steeply from the '
            'water, while the bay itself is dotted with islets. Inland is Lake Mir, a small salt '
            'lake.'
        ),
        'highlights': [
            'Cliffs on the open-sea side',
            'Lake Mir, the salt lake',
            'The bay and its islets',
            'Viewpoint above the cliffs',
            'Boat trips from Sali',
        ],
        'overview': (
            'Telašćica is a bay on the south-eastern side of Dugi Otok, a large, well-sheltered '
            'natural harbour. The park was declared in 1988. It protects the bay, its islets, the'
            ' seabed and a stretch of high cliffs facing the open sea, which rise to well over a '
            'hundred metres. A short path from the bay leads to the cliff edge, where you can '
            'look down over the water. Inland, Lake Mir is a small salt lake separated from the '
            'sea by a narrow strip of land, where visitors swim in warm, salty water. The park is'
            ' reached by boat or by road from the village of Sali, and the park office is in '
            'Sali. A ticket is required to enter. The area borders the Kornati islands to the '
            'south east.'
        ),
        'faqs': [
            {
                'q': 'Is Telašćica worth visiting?',
                'a': (
                    'Yes, for sheltered water, a dramatic cliff view and the salt lake. It is '
                    'often combined with a boat trip to the Kornati.'
                ),
            },
            {
                'q': 'How do I get to Telašćica?',
                'a': (
                    'By boat from Zadar, Sali or nearby ports, or by road from Sali on Dugi Otok.'
                    ' Zadar Airport (ZAD) is the nearest airport, and ferries connect Zadar with '
                    'Dugi Otok.'
                ),
            },
            {
                'q': 'What is there to do in Telašćica?',
                'a': (
                    'Swim in the bay or in Lake Mir, walk to the cliff viewpoint, take a boat '
                    'trip and visit the small restaurants near the quays.'
                ),
            },
            {
                'q': 'How long should I spend in Telašćica?',
                'a': 'A half day is enough for the walk and a swim; a full day if you travel by boat.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–September',
            },
            {
                'label': 'Ideal for',
                'value': 'Boat trips, swimming, sailing',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'By boat, or by road from Sali on Dugi Otok',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'sailing',
            'swimming',
            'nature lovers',
            'boat trips',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'The bay',
                'body': (
                    'Telašćica is a long, irregular bay with islets and several smaller coves. '
                    'Its depth and shelter make it a popular anchorage for yachts in summer. The '
                    'nature park protects the seabed and its species, which is why anchoring is '
                    'regulated and boaters use marked moorings.'
                ),
            },
            {
                'heading': 'Cliffs and Lake Mir',
                'body': (
                    'On the seaward side the cliffs fall steeply into the sea. A footpath from '
                    'the bay leads to a viewpoint above them. Lake Mir is a small salt lake '
                    'behind the shore. Its water is shallow and warm in summer, and swimming '
                    'there is a short walk from the bay.'
                ),
            },
            {
                'heading': 'Visiting the park',
                'body': (
                    'The park office is in Sali. Check ferry and boat timetables before you plan '
                    'the day, because the connections thin out in the low season. Take water and '
                    'sun protection; the cliff path is exposed and there is little shade.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Telašćica — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Telašćica',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.88,
        'longitude': 15.17,
    },
    {
        'name': 'Dugi Otok',
        'slug': 'dugi-otok',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Isola_Lunga.JPG/1280px-Isola_Lunga.JPG',
            'author': 'No machine-readable author provided. Ivana51~commonswiki assumed (based on copyright claims).',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0/',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Isola_Lunga.JPG',
        },
        'region': 'zadar',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A long, narrow island in the Zadar archipelago, with small villages, quiet beaches '
            'and the Telašćica nature park at its southern end.'
        ),
        'description': (
            'Dugi Otok, meaning Long Island, is the largest island of the Zadar archipelago, more'
            ' than 40 km long and only a few kilometres wide. It has small villages such as Sali,'
            ' Božava and Veli Rat, quiet beaches and the Telašćica nature park at its south-'
            'eastern end.'
        ),
        'highlights': [
            'Telašćica Nature Park',
            'Sakarun beach',
            'Veli Rat lighthouse',
            'The village of Sali',
            'The village of Božava',
        ],
        'overview': (
            'Dugi Otok lies in the Zadar archipelago, a long, thin island running north-west to '
            'south-east. Its villages are small and quiet, and most of the island is open stony '
            'hills, olive groves and scrub. Sali, the main village on the south-eastern end, is '
            'the base for Telašćica. In the north-west, the Veli Rat lighthouse, built in the '
            'nineteenth century, stands above the sea. Sakarun, on the north-west coast, is a '
            'pale pebble beach with shallow water. Dugi Otok is reached by ferry from Zadar to '
            'Brbinj, a car ferry, and by passenger boats to Sali and other ports. Roads are '
            'narrow, and in summer many visitors rent bikes or small cars.'
        ),
        'faqs': [
            {
                'q': 'Is Dugi Otok worth visiting?',
                'a': (
                    'Yes, for a quiet island stay with clean water and few crowds, and for the '
                    'Telašćica nature park.'
                ),
            },
            {
                'q': 'How do I get to Dugi Otok?',
                'a': (
                    'By ferry from Zadar. A car ferry runs to Brbinj and passenger boats serve '
                    'Sali and other ports. Zadar Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do on Dugi Otok?',
                'a': (
                    'Swim at Sakarun, visit Telašćica, walk or cycle between villages, and see '
                    'the Veli Rat lighthouse.'
                ),
            },
            {
                'q': 'How long should I spend on Dugi Otok?',
                'a': (
                    'A day trip covers one or two highlights, but a stay of two or three nights '
                    'lets you see more.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet island stays, cycling, swimming',
            },
            {
                'label': 'Time needed',
                'value': 'One day to several nights',
            },
            {
                'label': 'Getting there',
                'value': 'Ferry from Zadar to Brbinj; passenger boats to Sali',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'quiet breaks',
            'cycling',
            'swimming',
            'couples',
            'nature lovers',
        ],
        'sections': [
            {
                'heading': 'Villages and landscape',
                'body': (
                    'Sali is the largest settlement and has a harbour with a few restaurants. '
                    'Božava lies on a bay in the north-west. Between them, the road crosses an '
                    'island of low hills, with stone walls and olive trees. Distances are long by'
                    ' island standards, so plan your route.'
                ),
            },
            {
                'heading': 'Beaches and the lighthouse',
                'body': (
                    'Sakarun is a bay with white pebbles and sand and shallow water, set between '
                    'pines. Veli Rat, at the north-western tip, has a lighthouse from the '
                    'nineteenth century that is still a landmark for ships. Both are reachable by'
                    ' road, and Veli Rat is a short walk from the village.'
                ),
            },
            {
                'heading': 'Getting around',
                'body': (
                    'Ferries are less frequent outside summer, so check the timetable before you '
                    'go and plan the last return. Taxis and rentals exist but are limited. Bikes '
                    'are a common option on the quieter roads, but the island has hills, so allow'
                    ' extra time.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Dugi Otok — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Dugi_Otok',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.0,
        'longitude': 15.05,
    },
    {
        'name': 'Biograd na Moru',
        'slug': 'biograd-na-moru',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Biograd-na-more-1.JPG/1280px-Biograd-na-more-1.JPG',
            'author': 'japus',
            'licence': 'CC BY 2.5',
            'licence_url': 'https://creativecommons.org/licenses/by/2.5',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Biograd-na-more-1.JPG',
        },
        'region': 'zadar',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small Adriatic resort town with a medieval royal past, a marina and boats to the '
            'Kornati and nearby islands.'
        ),
        'description': (
            'Biograd na Moru is a small coastal town between Zadar and Šibenik, facing the island'
            ' of Pašman. In the eleventh century it was a royal seat of the Croatian kings. Today'
            ' it has a promenade, a marina and beaches, and it is a departure point for boat '
            'trips to the Kornati and the nearby islands.'
        ),
        'highlights': [
            'Seafront promenade',
            'Biograd marina',
            'Biograd town museum',
            'Boat trips to the Kornati',
            'Ferry to Pašman island',
        ],
        'overview': (
            'Biograd na Moru sits on a low peninsula facing Pašman across a narrow channel. In '
            'the Middle Ages it was one of the royal centres of the Croatian kingdom, and in the '
            'eleventh century it was a seat of King Petar Krešimir IV. Venetians destroyed the '
            'town in 1125. The old centre is small, and a museum tells the story of the area. The'
            ' seafront promenade is lined with cafés, and the harbour and marina fill with boats '
            'in summer. Biograd is a convenient base for sailing and for boat trips to the '
            'Kornati and Telašćica, and from the quay a ferry crosses to Tkon on Pašman. Nearby, '
            'Vrana Lake Nature Park lies just inland.'
        ),
        'faqs': [
            {
                'q': 'Is Biograd na Moru worth visiting?',
                'a': (
                    'Yes, as a relaxed base with beaches, a promenade and boat connections. It is'
                    ' also a good starting point for the Kornati and Vrana Lake.'
                ),
            },
            {
                'q': 'How do I get to Biograd na Moru?',
                'a': (
                    'It is on the coast about 30 km south-east of Zadar, reached by road from the'
                    ' A1 motorway. Zadar Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Biograd na Moru?',
                'a': (
                    'Walk the promenade, visit the museum, take a boat trip to the Kornati or '
                    'Pašman, and cycle or drive to Vrana Lake.'
                ),
            },
            {
                'q': 'How long should I spend in Biograd na Moru?',
                'a': 'A day covers the town; stay a few nights to add boat trips and Vrana Lake.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Sailing, beaches, a base for boat trips',
            },
            {
                'label': 'Time needed',
                'value': 'A day or more',
            },
            {
                'label': 'Getting there',
                'value': 'About 30 km south-east of Zadar by road; ferry to Pašman',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'sailing',
            'beach holidays',
            'families',
            'boat trips',
            'cycling',
        ],
        'sections': [
            {
                'heading': 'A royal town',
                'body': (
                    'In the eleventh century, Biograd was an important town of the Croatian '
                    'kings, and King Petar Krešimir IV made it a seat. The Venetian attack in '
                    '1125 ended that role. The town museum gives a short introduction to the '
                    'local past.'
                ),
            },
            {
                'heading': 'On the water',
                'body': (
                    'Biograd has a marina, a seafront promenade and several beaches. From the '
                    'harbour, day boats run out to the Kornati and Telašćica, and a ferry '
                    'connects to Pašman, an island with olive groves and small villages that is '
                    'also joined to Ugljan by a bridge.'
                ),
            },
            {
                'heading': 'Around Biograd',
                'body': (
                    'Vrana Lake Nature Park lies just inland and can be reached by bike or car. '
                    'Zadar is about 30 km to the north-west, and Šibenik is further south-east '
                    'along the coast. In the low season the town is quiet, and many restaurants '
                    'and boats run on reduced schedules.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Biograd na Moru — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Biograd_na_Moru',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.9375,
        'longitude': 15.4442,
    },
    {
        'name': 'Vrana Lake Nature Park',
        'slug': 'vrana-lake-nature-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Jezero_Vrana.jpg/1280px-Jezero_Vrana.jpg',
            'author': 'This Photo was taken by Miha Peče . Feel free to use my photos, but please mention me as the author. I would much appreciate if you send me an email pc.osx.linux@gmail.com or write on my talk page , f',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Jezero_Vrana.jpg',
        },
        'region': 'zadar',
        'place_type': 'lakes',
        'featured': False,
        'summary': (
            'A nature park around the largest natural lake in Croatia, with a bird reserve, a '
            'hilltop viewpoint and cycling routes.'
        ),
        'description': (
            'Vrana Lake (Vransko jezero) lies just inland from the sea between Zadar and Šibenik.'
            ' It is the largest natural lake in Croatia by surface area, and the north-western '
            'part is an ornithological reserve. The park has cycling routes, a viewpoint at '
            'Kamenjak and trails along the shore.'
        ),
        'highlights': [
            'Kamenjak viewpoint',
            'Ornithological reserve',
            'Cycling around the lake',
            'Walking trails',
            'Fishing and birdwatching',
        ],
        'overview': (
            'Vransko jezero is a shallow lake separated from the sea by a narrow ridge, near '
            'Biograd na Moru. It is the largest natural lake in Croatia by surface area, and its '
            'bed lies below sea level. The north-western part is protected as an ornithological '
            'reserve, where many species of water birds nest or stop on migration. The park was '
            'declared in 1999. A road and cycling routes run along parts of the shore, and the '
            'Kamenjak viewpoint, on a hill above the lake, gives a view over the lake, the sea '
            'and the islands beyond. Fishing and birdwatching are common activities, and some '
            'areas are closed to protect the habitat. A channel connects the lake with the sea. '
            'Visit with binoculars, sun cover and water, and check park rules on paths and access'
            ' first.'
        ),
        'faqs': [
            {
                'q': 'Is Vrana Lake worth visiting?',
                'a': (
                    'Yes, for cyclists, birdwatchers and anyone who wants a quiet landscape '
                    'inland from the coast. The view from Kamenjak is the main sight.'
                ),
            },
            {
                'q': 'How do I get to Vrana Lake?',
                'a': (
                    'The lake is reached by road from Biograd na Moru, Pakoštane or the A1 '
                    'motorway. Zadar Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do at Vrana Lake?',
                'a': (
                    'Cycle on the park’s routes, walk to Kamenjak, watch birds and fish where '
                    'permitted.'
                ),
            },
            {
                'q': 'How long should I spend at Vrana Lake?',
                'a': (
                    'A half day is enough for the viewpoint and a short ride; a full day for a '
                    'longer circuit.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'April–June and September–October; spring and autumn for birds',
            },
            {
                'label': 'Ideal for',
                'value': 'Cycling, birdwatching, quiet landscapes',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Biograd na Moru or the A1 motorway',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'cycling',
            'birdwatching',
            'nature lovers',
            'photographers',
            'quiet breaks',
        ],
        'sections': [
            {
                'heading': 'The lake',
                'body': (
                    'The lake’s water is mostly shallow and lies close to the sea, separated from'
                    ' it by a ridge of land. A canal links the two. Because of this link, the '
                    'water is somewhat brackish. The surrounding fields and reed beds are home to'
                    ' fish and many kinds of birds.'
                ),
            },
            {
                'heading': 'Birds and protected areas',
                'body': (
                    'The ornithological reserve is on the north-western side of the lake, and '
                    'access there is restricted. Elsewhere in the park, birdwatchers use '
                    'observation points and paths. Spring and autumn migration are the usual '
                    'times to see the widest range of birds.'
                ),
            },
            {
                'heading': 'Cycling and views',
                'body': (
                    'A cycling route follows part of the shore, and Kamenjak, a hill above the '
                    'lake, is reached by road. From the top, the lake, the sea and the islands '
                    'can be seen on a clear day. There is little shade, so carry water and sun '
                    'protection.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Vrana Lake Nature Park',
                'url': 'https://pp-vransko-jezero.hr/',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.8667,
        'longitude': 15.5833,
    },
    {
        'name': 'Ugljan',
        'slug': 'ugljan',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Island_of_Ugljan_2011_02.jpg/1280px-Island_of_Ugljan_2011_02.jpg',
            'author': 'Photograph by Mike Peel ( www.mikepeel.net ).',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Island_of_Ugljan_2011_02.jpg',
        },
        'region': 'zadar',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'An island just across the channel from Zadar, with olive groves, small harbour towns'
            ' and a short ferry ride.'
        ),
        'description': (
            'Ugljan lies directly opposite Zadar, with a ferry from the city to Preko taking '
            'around 25 minutes. The island has olive groves, small harbour villages such as '
            'Preko, Kali and Kukljica, and quiet coves. A bridge at Ždrelac joins Ugljan to the '
            'neighbouring island of Pašman.'
        ),
        'highlights': [
            'Preko and the islet of Galevac',
            'St Michael’s fortress above Preko',
            'Olive groves',
            'Fishing village of Kali',
            'Bridge to Pašman at Ždrelac',
        ],
        'overview': (
            'Ugljan is the island closest to Zadar, separated from the city by a narrow channel. '
            'The car ferry from Zadar docks at Preko, the main town, where the islet of Galevac, '
            'with a Franciscan monastery, sits just offshore. Above Preko, a walk leads to the '
            'fortress of St Michael, which gives a long view over the channel and the Zadar '
            'archipelago. Away from Preko, the island is largely olive groves and small villages,'
            ' with Kali on the east coast known for its fishing tradition, and Kukljica and '
            'Sutomišćica with quiet bays. A bridge at Ždrelac joins Ugljan to Pašman, which can '
            'be reached by road. The island is a place to cycle, swim and eat simply, and it is '
            'easy to reach from Zadar even for a short stay.'
        ),
        'faqs': [
            {
                'q': 'Is Ugljan worth visiting?',
                'a': 'Yes, as an easy island day trip or a relaxed base for a few nights near Zadar.',
            },
            {
                'q': 'How do I get to Ugljan?',
                'a': (
                    'A ferry runs from Zadar to Preko, a crossing of around 25 minutes. Zadar '
                    'Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do on Ugljan?',
                'a': (
                    'Walk to St Michael’s fortress, cycle through the olive groves, swim in the '
                    'coves and visit Kali and the islet of Galevac.'
                ),
            },
            {
                'q': 'How long should I spend on Ugljan?',
                'a': (
                    'A day trip covers Preko and the fortress; a few nights lets you explore the '
                    'whole island.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Cycling, swimming, an easy island day',
            },
            {
                'label': 'Time needed',
                'value': 'A day or more',
            },
            {
                'label': 'Getting there',
                'value': 'Ferry from Zadar to Preko, about 25 minutes',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'cycling',
            'swimming',
            'families',
            'day trips',
            'quiet breaks',
        ],
        'sections': [
            {
                'heading': 'Preko and the fortress',
                'body': (
                    'Preko is a small harbour town facing Zadar, with a seafront promenade and '
                    'cafés. The islet of Galevac, just offshore, holds a Franciscan monastery. A '
                    'path from Preko climbs to the fortress of St Michael, above the town, and '
                    'the view from the top covers the channel, the neighbouring islands and Zadar'
                    ' on a clear day.'
                ),
            },
            {
                'heading': 'Olives and villages',
                'body': (
                    'Ugljan is known for its olive groves, and the oil is sold locally. Kali is a'
                    ' fishing village on the east coast, Kukljica and Sutomišćica have quiet '
                    'bays, and the road that follows the coast links them. Cycling is a common '
                    'way to explore, since the island is small.'
                ),
            },
            {
                'heading': 'Beyond Ugljan',
                'body': (
                    'At Ždrelac, a bridge links Ugljan to Pašman, which has its own villages, '
                    'beaches and a ferry to Biograd na Moru. Combine the two islands for a longer'
                    ' outing, and check ferry times from Zadar before you plan your return.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Ugljan — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Ugljan',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.0833,
        'longitude': 15.1833,
    },
    {
        'name': 'Zrmanja River',
        'slug': 'zrmanja-river',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Zadar_%28HR%29%2C_Krupa-Canyon%2C_Kudin-Br%C3%BCcke_--_2022_--_0059-68.jpg/1280px-Zadar_%28HR%29%2C_Krupa-Canyon%2C_Kudin-Br%C3%BCcke_--_2022_--_0059-68.jpg',
            'author': 'Anil Öztas',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Zadar_(HR),_Krupa-Canyon,_Kudin-Br%C3%BCcke_--_2022_--_0059-68.jpg',
        },
        'region': 'zadar',
        'place_type': 'lakes',
        'featured': False,
        'summary': (
            'A river flowing from the Lika highlands through a deep canyon to the sea near '
            'Obrovac, with waterfalls and rafting.'
        ),
        'description': (
            'The Zrmanja is a river of about 70 km that rises in the highlands of Lika and flows '
            'through a deep limestone canyon before reaching the Novigrad Sea near Obrovac. It is'
            ' known for clear, green water, waterfalls and travertine barriers, and is used for '
            'rafting and kayaking.'
        ),
        'highlights': [
            'Zrmanja canyon',
            'Waterfalls and travertine barriers',
            'Rafting and kayaking',
            'Town of Obrovac',
            'Views toward the Velebit mountains',
        ],
        'overview': (
            'The Zrmanja rises in Lika and runs toward the Adriatic for about 70 km. In its upper'
            ' part it flows through a deep canyon with steep limestone walls, then slows as it '
            'nears the sea. Along the way it forms rapids, waterfalls and travertine barriers, '
            'and the water is clear and green. The river is used for rafting and kayaking, and '
            'fishing is also popular. Near its mouth, the town of Obrovac lies on the river, and '
            'the Zrmanja then widens into the Novigrad Sea, an inlet that connects to the '
            'Adriatic. Its canyon lies near the Velebit mountains, within reach of Paklenica, so '
            'the two can be combined. Conditions change with the season and rainfall, so check '
            'water levels with a local operator before planning an outing.'
        ),
        'faqs': [
            {
                'q': 'Is the Zrmanja River worth visiting?',
                'a': (
                    'Yes, for people who like a river landscape and water sports. The canyon and '
                    'the green water are the main attractions.'
                ),
            },
            {
                'q': 'How do I get to the Zrmanja River?',
                'a': (
                    'By road from Zadar to Obrovac and the canyon, which takes some time. Zadar '
                    'Airport (ZAD) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do on the Zrmanja River?',
                'a': (
                    'Go rafting or kayaking with a local operator, walk along the river, fish '
                    'where permitted and visit Obrovac.'
                ),
            },
            {
                'q': 'How long should I spend at the Zrmanja River?',
                'a': 'A half day for a rafting trip; a full day if you add walks and Obrovac.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–October, depending on water level',
            },
            {
                'label': 'Ideal for',
                'value': 'Rafting, kayaking, river scenery',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Zadar to Obrovac and the canyon',
            },
            {
                'label': 'Region',
                'value': 'Zadar',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zadar Airport (ZAD)',
            },
        ],
        'good_for': [
            'rafting',
            'kayaking',
            'nature lovers',
            'photographers',
            'active travellers',
        ],
        'sections': [
            {
                'heading': 'The canyon',
                'body': (
                    'The upper Zrmanja cuts through limestone and is mostly reached on foot or by'
                    ' raft. Its walls close in around the water, and the river drops over small '
                    'falls and travertine steps. In some stretches the water runs fast, in others'
                    ' it is calm and deep.'
                ),
            },
            {
                'heading': 'On the water',
                'body': (
                    'Rafting and kayaking are run by local operators, who provide equipment and '
                    'guides. Water levels depend on the season and on rainfall, and are highest '
                    'in spring and after rain, so the character of the trip can change. Ask about'
                    ' difficulty and age limits when you book.'
                ),
            },
            {
                'heading': 'Obrovac and the estuary',
                'body': (
                    'Obrovac stands near the lower river, where the Zrmanja widens before it '
                    'reaches the Novigrad Sea. The estuary is shallow and sheltered, and the town'
                    ' offers a base for visits to the canyon, Paklenica and the Velebit coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Zrmanja — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Zrmanja',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.2,
        'longitude': 15.7,
    },
    {
        'name': 'Šibenik',
        'slug': 'sibenik',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/%C5%A0ibenik_BW_2024-09-30_10-50-35.jpg/1280px-%C5%A0ibenik_BW_2024-09-30_10-50-35.jpg',
            'author': 'Berthold Werner',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:%C5%A0ibenik_BW_2024-09-30_10-50-35.jpg',
        },
        'region': 'sibenik',
        'place_type': 'cities',
        'featured': True,
        'summary': (
            'A stone-built Dalmatian city on the Krka estuary, with a UNESCO-listed cathedral and'
            ' Venetian fortresses.'
        ),
        'description': (
            'Šibenik rises in terraces above a sheltered bay where the Krka river meets the sea. '
            'Its Cathedral of St James, built entirely of stone in the fifteenth and sixteenth '
            'centuries, is a UNESCO World Heritage Site, and St Nicholas Fortress guards the '
            'channel into the bay. The old town is a tangle of steps and lanes.'
        ),
        'highlights': [
            'Cathedral of St James',
            'St Nicholas Fortress',
            'St Michael’s Fortress',
            'Old town lanes and squares',
            'The waterfront promenade',
        ],
        'overview': (
            'Šibenik was first mentioned in 1066, in a charter of King Petar Krešimir IV, and '
            'unlike most Dalmatian towns it was founded by Croats rather than by Greeks or '
            'Romans. It climbs a hillside above a deep bay, reached from the sea through the '
            'narrow St Anthony Channel, which is guarded by St Nicholas Fortress. The Cathedral '
            'of St James, begun in 1431 and completed in 1536, with Juraj Dalmatinac and Nikola '
            'Firentinac among its master builders, was inscribed by UNESCO in 1991. It is built '
            'entirely of stone, and a frieze of carved heads runs around the apse. St Nicholas '
            'Fortress is part of the Venetian defence works that UNESCO listed in 2017, and St '
            'Michael’s and Barone fortresses stand above the town. The old town is made up of '
            'steep stepped lanes, small squares and churches. Šibenik is also the usual base for '
            'visits to Krka National Park.'
        ),
        'faqs': [
            {
                'q': 'Is Šibenik worth visiting?',
                'a': (
                    'Yes. Its cathedral, fortresses and old town are all close together, and it '
                    'is the gateway to Krka National Park.'
                ),
            },
            {
                'q': 'How do I get to Šibenik?',
                'a': (
                    'Šibenik is on the A1 motorway and the coastal road, and has a bus station '
                    'and a railway station. Split Airport (SPU) and Zadar Airport (ZAD) are each '
                    'about an hour away by road.'
                ),
            },
            {
                'q': 'What is there to do in Šibenik?',
                'a': (
                    'See the Cathedral of St James, climb to St Michael’s Fortress, walk the old '
                    'town, visit St Nicholas Fortress by boat and use the city as a base for Krka'
                    ' and the islands.'
                ),
            },
            {
                'q': 'How long should I spend in Šibenik?',
                'a': (
                    'A day covers the main sights; two or three nights lets you add Krka National'
                    ' Park and an island trip.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–June and September; July–August for swimming and festivals',
            },
            {
                'label': 'Ideal for',
                'value': 'History, city breaks, a base for Krka',
            },
            {
                'label': 'Time needed',
                'value': 'One to two days',
            },
            {
                'label': 'Getting there',
                'value': 'A1 motorway, coastal road, bus and rail',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'history lovers',
            'city breaks',
            'couples',
            'base for Krka',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'The cathedral',
                'body': (
                    'The Cathedral of St James took more than a century to build. Juraj '
                    'Dalmatinac and Nikola Firentinac were its best-known builders, and it is '
                    'made entirely of stone, including the roof, which is made of fitted slabs. A'
                    ' row of carved portrait heads runs around the outside of the apse. UNESCO '
                    'added it to the World Heritage List in 1991.'
                ),
            },
            {
                'heading': 'Fortresses',
                'body': (
                    'Several Venetian fortresses defend the town. St Nicholas stands on a small '
                    'island at the entrance of the channel and is reached by boat. St Michael’s '
                    'sits on the hill above the old town and has a terrace with views over the '
                    'bay and islands. St Nicholas is part of the Venetian defence works UNESCO '
                    'listed in 2017.'
                ),
            },
            {
                'heading': 'A base for exploring',
                'body': (
                    'From Šibenik, boats leave for Krka National Park, for the Kornati and for '
                    'the archipelago islands, including Zlarin and Prvić. By road, Skradin, '
                    'Primošten and Vodice are within a short drive. The waterfront has '
                    'restaurants and cafés, and the old town is easy to walk in an afternoon.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Šibenik — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/%C5%A0ibenik',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.735,
        'longitude': 15.8952,
    },
    {
        'name': 'Krka National Park',
        'slug': 'krka-national-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Krka_Nationalpark_BW_2024-09-30_13-53-15.jpg/1280px-Krka_Nationalpark_BW_2024-09-30_13-53-15.jpg',
            'author': 'Berthold Werner',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Krka_Nationalpark_BW_2024-09-30_13-53-15.jpg',
        },
        'region': 'sibenik',
        'place_type': 'national_parks',
        'featured': True,
        'summary': (
            'A national park along the Krka river, with seven waterfalls, an island monastery and'
            ' Roman remains.'
        ),
        'description': (
            'Krka National Park follows part of the Krka river, which runs through a limestone '
            'canyon and over a series of travertine waterfalls. Skradinski buk, the lowest and '
            'best-known, is reached by a wooden walkway. The park also holds the island monastery'
            ' of Visovac, the Roški slap waterfall and the Roman camp of Burnum.'
        ),
        'highlights': [
            'Skradinski buk waterfall',
            'Roški slap',
            'Visovac island and its monastery',
            'Roman camp of Burnum',
            'Boat trip from Skradin',
        ],
        'overview': (
            'The Krka rises in the Dinaric mountains and flows about 72 km to the sea near '
            'Šibenik. The national park, declared in 1985, protects a stretch of the lower river,'
            ' where the water drops over seven waterfalls, the lowest of them Skradinski buk, a '
            'wide curtain of cascades set among pools and islets. A wooden walkway leads through '
            'the area, with a loop of paths, an old mill exhibition and small shops. Upstream, '
            'the river widens into Lake Visovac, where the island of Visovac holds a Franciscan '
            'monastery founded in the fifteenth century. Further up are the Roški slap waterfalls'
            ' and, near the upper entrance, the remains of the Roman military camp of Burnum. The'
            ' Krka monastery stands in the canyon, too. Entrance is through Lozovac, Skradin, '
            'Roški slap or Burnum, and in season a boat runs from Skradin to Skradinski buk.'
        ),
        'faqs': [
            {
                'q': 'Is Krka National Park worth visiting?',
                'a': (
                    'Yes, for the waterfalls, the walkways and the combination of nature and '
                    'history. Skradinski buk is the most visited area.'
                ),
            },
            {
                'q': 'How do I get to Krka National Park?',
                'a': (
                    'The park’s entrances are within about 20 km of Šibenik by road, and you can '
                    'enter at Lozovac, Skradin, Roški slap or Burnum. Split Airport (SPU) and '
                    'Zadar Airport (ZAD) are the nearest airports.'
                ),
            },
            {
                'q': 'What is there to do in Krka National Park?',
                'a': (
                    'Walk the boardwalks at Skradinski buk, take a boat trip to Visovac or Roški '
                    'slap, and visit the Roman remains of Burnum.'
                ),
            },
            {
                'q': 'How long should I spend in Krka National Park?',
                'a': (
                    'Allow half a day for Skradinski buk, or a full day to add a boat trip or a '
                    'second entrance.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'April–June and September–October; summer is hot and busy',
            },
            {
                'label': 'Ideal for',
                'value': 'Nature walks, photography, families',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': (
                    'Within about 20 km of Šibenik; entrances at Lozovac, Skradin, Roški slap and'
                    ' Burnum'
                ),
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'families',
            'walkers',
            'photographers',
            'nature lovers',
            'history lovers',
        ],
        'sections': [
            {
                'heading': 'Skradinski buk',
                'body': (
                    'This is the lowest and widest of the park’s seven waterfalls. The river '
                    'spreads out over a series of travertine barriers and pools, and wooden '
                    'walkways let visitors walk among the cascades. Take the boat from Skradin or'
                    ' the bus from the Lozovac entrance. Opening and access rules for swimming '
                    'and paths are set by the park, so check them first.'
                ),
            },
            {
                'heading': 'Visovac and Roški slap',
                'body': (
                    'The Franciscan monastery on Visovac island sits in the middle of Lake '
                    'Visovac, and a church and a small museum are part of it. Boat trips run on '
                    'the lake, and visitors can see the island from the water. Further upstream, '
                    'Roški slap is a long series of cascades and small islands, with a watermill '
                    'display nearby.'
                ),
            },
            {
                'heading': 'Burnum and the upper river',
                'body': (
                    'At the upper part of the park, near Kistanje, Burnum is the site of a Roman '
                    'military camp and later a town. Arches from the legionary headquarters '
                    'survive, and the setting above the canyon is quiet. The park’s upper '
                    'entrance is the best choice if you plan to combine Burnum with Roški slap.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Krka National Park — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Krka_National_Park',
            },
            {
                'label': 'Krka National Park',
                'url': 'https://www.npkrka.hr/',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.803,
        'longitude': 15.9714,
    },
    {
        'name': 'Skradin',
        'slug': 'skradin',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Skradin_BW_2024-09-30_13-52-23.jpg/1280px-Skradin_BW_2024-09-30_13-52-23.jpg',
            'author': 'Berthold Werner',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Skradin_BW_2024-09-30_13-52-23.jpg',
        },
        'region': 'sibenik',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A small riverside town at the mouth of the Krka, and the main gateway by boat to '
            'Skradinski buk.'
        ),
        'description': (
            'Skradin lies on the Krka river, near where it widens into Lake Prokljan, and is the '
            'main gateway to Krka National Park. The town has a small harbour, a few old streets '
            'and a marina. The Romans knew the settlement as Scardona, and a fortress stands on '
            'the hill above it.'
        ),
        'highlights': [
            'Boat to Skradinski buk',
            'Harbour and waterfront',
            'Old town streets',
            'Turina fortress ruins',
            'Skradin risotto',
        ],
        'overview': (
            'Skradin is a small town on the west bank of the Krka, less than 20 km from Šibenik. '
            'In Roman times it was Scardona, an administrative centre of the region, and later it'
            ' was a medieval town with its own bishop. Today the old streets run down to a '
            'harbour where small boats and yachts tie up, and cafés line the waterfront. Above '
            'the town stand the ruins of Turina, a fortress on a hill. The town’s main role for '
            'visitors is as the starting point for boats to Skradinski buk, the park’s main '
            'waterfall, a trip of about half an hour. Skradin risotto is a local dish often '
            'served in the restaurants. The town is quiet outside the main season, and the park’s'
            ' boat service runs on a timetable that varies by month, so check it before you plan.'
        ),
        'faqs': [
            {
                'q': 'Is Skradin worth visiting?',
                'a': (
                    'Yes, as a short stop or an overnight base before or after Krka National '
                    'Park. It is small and easy to walk.'
                ),
            },
            {
                'q': 'How do I get to Skradin?',
                'a': (
                    'Skradin is less than 20 km from Šibenik by road. Split Airport (SPU) and '
                    'Zadar Airport (ZAD) are the nearest airports.'
                ),
            },
            {
                'q': 'What is there to do in Skradin?',
                'a': (
                    'Walk the old streets, eat at the waterfront and take the boat to Skradinski '
                    'buk in Krka National Park.'
                ),
            },
            {
                'q': 'How long should I spend in Skradin?',
                'a': 'A few hours for the town, or a night if you plan to spend a full day at Krka.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'April–October',
            },
            {
                'label': 'Ideal for',
                'value': 'Short stops, a base for Krka, boat trips',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a night',
            },
            {
                'label': 'Getting there',
                'value': 'Less than 20 km from Šibenik by road; boat to Skradinski buk',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'base for Krka',
            'boat trips',
            'short stops',
            'couples',
            'food lovers',
        ],
        'sections': [
            {
                'heading': 'From Scardona to Skradin',
                'body': (
                    'Under Rome the settlement was called Scardona, and it held a role as a '
                    'regional centre. Medieval Skradin had its own bishop, and parts of its old '
                    'defences survive on the hill above the present town. The town sits on a '
                    'short bend of the river, which gives it a sheltered harbour.'
                ),
            },
            {
                'heading': 'The gateway to Krka',
                'body': (
                    'Boats leave from the harbour for Skradinski buk, travelling along the river '
                    'through reed beds and low hills. The ticket for the park is bought at the '
                    'quay. The journey is a pleasant start to the day and leaves time to walk the'
                    ' boardwalks before you return.'
                ),
            },
            {
                'heading': 'Eating and staying',
                'body': (
                    'Small restaurants along the waterfront serve fish, risotto and local wine. '
                    'Skradin also has a marina, used by yachts on the lower Krka. Most visitors '
                    'arrive for the day, so the town is quietest in the evening and early '
                    'morning.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Skradin — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Skradin',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.8186,
        'longitude': 15.9239,
    },
    {
        'name': 'Primošten',
        'slug': 'primosten',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/Primo%C5%A1ten_Croatia.jpg/1280px-Primo%C5%A1ten_Croatia.jpg',
            'author': 'Martin Vorel',
            'licence': 'CC0',
            'licence_url': 'https://creativecommons.org/publicdomain/zero/1.0/deed.en',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Primo%C5%A1ten_Croatia.jpg',
        },
        'region': 'sibenik',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small old town on a rounded peninsula, with pebble beaches and terraced vineyards '
            'around it.'
        ),
        'description': (
            'Primošten’s old town sits on a small, rounded peninsula that was once an island and '
            'is now linked to the mainland by a short causeway. Around it, pebble beaches and '
            'pine-shaded coves face the sea. Inland, stone-walled vineyards grow the Babić grape.'
        ),
        'highlights': [
            'Old town on the peninsula',
            'Church of St George above the town',
            'Stone-walled Babić vineyards',
            'Pebble beaches and coves',
            'Waterfront walk',
        ],
        'overview': (
            'Primošten lies on the Adriatic coast about 30 km south-east of Šibenik. Its old town'
            ' stands on a small hill-shaped peninsula, which was an island until it was linked to'
            ' the mainland. A tight cluster of stone houses runs up to the parish church of St '
            'George, at the top, from where there is a view over the harbour and the sea. Outside'
            ' the town, the shoreline is a series of pebble beaches and small bays shaded by '
            'pines. Behind the town, the slopes are covered in vineyards divided by dry-stone '
            'walls, where the red Babić grape is grown. The walls and terraces form a distinctive'
            ' local landscape. Primošten is a good base for swimming and for exploring the coast '
            'between Šibenik and Split.'
        ),
        'faqs': [
            {
                'q': 'Is Primošten worth visiting?',
                'a': 'Yes, for a relaxed coastal stay with an old town, beaches and local wine.',
            },
            {
                'q': 'How do I get to Primošten?',
                'a': (
                    'It is on the Adriatic coastal road, near the A1 motorway, about 30 km south-'
                    'east of Šibenik. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Primošten?',
                'a': (
                    'Walk the old town, climb to the church of St George, swim in the coves and '
                    'taste Babić wine in the vineyards.'
                ),
            },
            {
                'q': 'How long should I spend in Primošten?',
                'a': 'A day covers the town and a beach; stay longer for a beach holiday.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Beach stays, local wine, a short walk through an old town',
            },
            {
                'label': 'Time needed',
                'value': 'A day or more',
            },
            {
                'label': 'Getting there',
                'value': 'Coastal road; about 30 km south-east of Šibenik',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU)',
            },
        ],
        'good_for': [
            'beach holidays',
            'wine lovers',
            'couples',
            'families',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'The old town',
                'body': (
                    'The town sits on a former island, and a short causeway now links it to the '
                    'mainland. Narrow streets climb up to the church of St George at the highest '
                    'point, with a graveyard beside it that overlooks the sea.'
                ),
            },
            {
                'heading': 'Beaches and the coast',
                'body': (
                    'Beaches near Primošten are mostly pebble, and the water is shallow and clear'
                    ' in the coves. Pines give shade behind the shore, and a path follows parts '
                    'of the coast.'
                ),
            },
            {
                'heading': 'Vineyards',
                'body': (
                    'The red Babić grape is the local variety, and the vines grow on stony '
                    'hillsides divided by dry-stone walls. Some small wineries welcome visitors '
                    'for tastings, usually by appointment. The vineyard landscape is a '
                    'distinctive feature of the area and can be seen from the road above the '
                    'town.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Primošten — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Primo%C5%A1ten',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.5856,
        'longitude': 15.9231,
    },
    {
        'name': 'Vodice',
        'slug': 'vodice',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Vodice_CRO.jpg/1280px-Vodice_CRO.jpg',
            'author': 'Tadam',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Vodice_CRO.jpg',
        },
        'region': 'sibenik',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small seaside resort north of Šibenik, with a promenade, a marina and boats to the'
            ' nearby islands.'
        ),
        'description': (
            'Vodice is a seaside town about 11 km north of Šibenik, on a sheltered bay with a '
            'long promenade, a marina and pebble beaches. Boats leave from its harbour for the '
            'island of Prvić, for Krka National Park and for the Kornati islands.'
        ),
        'highlights': [
            'Seafront promenade',
            'Vodice marina',
            'Boat trips to Prvić',
            'Excursions to the Kornati and Krka',
            'Pebble beaches',
        ],
        'overview': (
            'Vodice lies on the coast about 11 km from Šibenik, facing a scatter of small '
            'islands. The old centre is compact, with stone houses around the harbour and a '
            'parish church, and a long promenade runs along the waterfront with cafés, shops and '
            'a marina. Pebble beaches lie on either side of the town. Vodice is a popular base '
            'for families and for sailors in summer, and from its harbour, boats and ferries run '
            'to Prvić, a small island with quiet villages, and day excursions go to the Kornati '
            'and Krka. The nearby town of Tribunj can be reached by foot or bike along the coast.'
            ' In winter the town is quiet, and many restaurants and boat services reduce their '
            'schedules or close.'
        ),
        'faqs': [
            {
                'q': 'Is Vodice worth visiting?',
                'a': (
                    'Yes, as a beach and boating base near Šibenik, with easy access to Krka and '
                    'the islands.'
                ),
            },
            {
                'q': 'How do I get to Vodice?',
                'a': (
                    'Vodice is about 11 km from Šibenik by road. Split Airport (SPU) and Zadar '
                    'Airport (ZAD) are each about an hour away.'
                ),
            },
            {
                'q': 'What is there to do in Vodice?',
                'a': (
                    'Walk the promenade, swim from the beaches, take a boat to Prvić or the '
                    'Kornati and visit Krka National Park.'
                ),
            },
            {
                'q': 'How long should I spend in Vodice?',
                'a': 'A beach day, or a few nights as a base for boat trips.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Beach holidays, sailing, families',
            },
            {
                'label': 'Time needed',
                'value': 'A day or more',
            },
            {
                'label': 'Getting there',
                'value': 'About 11 km north of Šibenik by road',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'beach holidays',
            'families',
            'sailing',
            'boat trips',
            'groups of friends',
        ],
        'sections': [
            {
                'heading': 'Town and waterfront',
                'body': (
                    'The old part of Vodice is small, with a church, a main square and lanes that'
                    ' lead to the harbour. The promenade is the town’s social centre, lined with '
                    'restaurants. The marina fills with boats in summer.'
                ),
            },
            {
                'heading': 'Islands and excursions',
                'body': (
                    'From the harbour, boats run to Prvić, an island with two villages. '
                    'Excursions go to the Kornati and Krka, and boat taxis serve small bays along'
                    ' the coast. Book popular trips ahead in July and August.'
                ),
            },
            {
                'heading': 'Beyond the town',
                'body': (
                    'Tribunj, to the north, can be reached along the coast on foot or by bike. '
                    'Šibenik is the nearest city, and its cathedral and fortresses make an easy '
                    'half-day trip. Murter, with its access to the Kornati, lies further north-'
                    'west.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Vodice — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Vodice,_Croatia',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.7611,
        'longitude': 15.7792,
    },
    {
        'name': 'Tribunj',
        'slug': 'tribunj',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Tribunj.jpg/1280px-Tribunj.jpg',
            'author': 'Sztudva Gyöngyi',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Tribunj.jpg',
        },
        'region': 'sibenik',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small old town on a former islet near Vodice, joined to the mainland by a short '
            'causeway.'
        ),
        'description': (
            'Tribunj is a small town a few kilometres from Vodice, built on a rounded islet that '
            'is now joined to the mainland by a short causeway. Its stone houses and narrow lanes'
            ' surround a harbour with a marina, and the surrounding coast has pebble beaches and '
            'coves.'
        ),
        'highlights': [
            'Old town on the islet',
            'Harbour and marina',
            'Narrow stone lanes',
            'Pebble beaches and coves',
            'Walk or ride to Vodice',
        ],
        'overview': (
            'Tribunj stands on a small, round islet on the coast north of Šibenik, now reached '
            'over a short causeway from the mainland. The old town fills the islet, with stone '
            'houses packed around narrow lanes. Around the islet, a harbour and marina shelter '
            'small boats and yachts, and a few restaurants serve fish on the waterfront. Beaches '
            'nearby are pebble, with pines behind them. Tribunj is quieter than neighbouring '
            'Vodice, which is a few kilometres away and can be reached on foot or by bike along '
            'the coast. The town has a long fishing tradition, and on summer evenings the '
            'waterfront is the centre of activity. Excursion boats serve the Kornati and other '
            'islands from the area, and Krka National Park is within reach by road.'
        ),
        'faqs': [
            {
                'q': 'Is Tribunj worth visiting?',
                'a': (
                    'Yes, for a quiet stay or a short walk through a small island town, '
                    'especially combined with Vodice and Šibenik.'
                ),
            },
            {
                'q': 'How do I get to Tribunj?',
                'a': (
                    'Tribunj is on the coastal road a few kilometres from Vodice and about 15 km '
                    'from Šibenik. Split Airport (SPU) and Zadar Airport (ZAD) are each about an '
                    'hour away.'
                ),
            },
            {
                'q': 'What is there to do in Tribunj?',
                'a': (
                    'Walk through the old town, eat at the waterfront, swim from the nearby '
                    'beaches and take a boat trip to the islands.'
                ),
            },
            {
                'q': 'How long should I spend in Tribunj?',
                'a': 'A few hours for the old town, or a few nights as a quiet base.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet stays, short walks, sailing',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a few nights',
            },
            {
                'label': 'Getting there',
                'value': 'On the coastal road, a few kilometres from Vodice',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'quiet breaks',
            'sailing',
            'couples',
            'short stops',
            'food lovers',
        ],
        'sections': [
            {
                'heading': 'The islet town',
                'body': (
                    'The old town sits on its islet within a few minutes’ walk from end to end. '
                    'Houses of stone line the lanes, which lead to small squares and the harbour.'
                    ' The causeway that links the islet to the land is short, and the harbour on '
                    'either side is the centre of local life.'
                ),
            },
            {
                'heading': 'Sea and coast',
                'body': (
                    'The surrounding coast has pebble beaches and sheltered coves. The marina is '
                    'used by visiting yachts in summer. A path and the coastal road connect the '
                    'town to Vodice.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Tribunj is small, so most visitors come for part of a day or stay in nearby '
                    'accommodation. In summer the harbour is busy in the evening, and in winter '
                    'many restaurants close. Combine it with Vodice, Šibenik and Krka for a '
                    'broader trip.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Tribunj — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Tribunj',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.7533,
        'longitude': 15.7506,
    },
    {
        'name': 'Murter',
        'slug': 'murter',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Betina-Murter.jpg/1280px-Betina-Murter.jpg',
            'author': 'This Photo was taken by Miha Peče . Feel free to use my photos, but please mention me as the author. I would much appreciate if you send me an email pc.osx.linux@gmail.com or write on my talk page , f',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Betina-Murter.jpg',
        },
        'region': 'sibenik',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'An island joined to the mainland by a bridge at Tisno, and the main starting point '
            'for the Kornati islands.'
        ),
        'description': (
            'Murter is an island joined to the mainland by a short swing bridge at Tisno. Its '
            'villages, including Murter, Betina and Jezera, lie on quiet bays, and the island is '
            'the main starting point for boat trips to Kornati National Park, whose office is in '
            'Murter.'
        ),
        'highlights': [
            'Boats to Kornati National Park',
            'Betina and its wooden boats',
            'The bridge at Tisno',
            'Pebble beaches and coves',
            'Jezera and Murter harbours',
        ],
        'overview': (
            'Murter is an island on the Dalmatian coast, linked to the mainland by a short swing '
            'bridge at Tisno. The island has four villages: Murter, Betina, Jezera and Tisno. '
            'Murter’s harbour is a main point of departure for boats to the Kornati islands, and '
            'the Kornati National Park has its office here. Many of the Kornati islands have long'
            ' been owned by families from Murter, who grazed sheep and tended olives there. '
            'Betina is a small harbour village known for its tradition of building wooden boats, '
            'and has a museum of wooden shipbuilding. The island has pebble beaches, pine-covered'
            ' coves and olive groves. In summer, Murter is busy with sailors, divers and day-trip'
            ' boats; outside the season, it is quiet.'
        ),
        'faqs': [
            {
                'q': 'Is Murter worth visiting?',
                'a': (
                    'Yes, particularly as a base for the Kornati islands, with quiet beaches and '
                    'small harbours.'
                ),
            },
            {
                'q': 'How do I get to Murter?',
                'a': (
                    'By road over the bridge at Tisno from the coastal road. Split Airport (SPU) '
                    'and Zadar Airport (ZAD) are the nearest airports.'
                ),
            },
            {
                'q': 'What is there to do on Murter?',
                'a': (
                    'Take a boat trip to the Kornati, visit Betina and its boats, swim in the '
                    'coves and walk or cycle through the olive groves.'
                ),
            },
            {
                'q': 'How long should I spend on Murter?',
                'a': 'A day with a Kornati excursion, or a few nights for a beach holiday.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Sailing, a base for the Kornati, quiet beaches',
            },
            {
                'label': 'Time needed',
                'value': 'A day or more',
            },
            {
                'label': 'Getting there',
                'value': 'By road over the Tisno bridge',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'sailing',
            'boat trips',
            'divers',
            'quiet breaks',
            'families',
        ],
        'sections': [
            {
                'heading': 'The gateway to the Kornati',
                'body': (
                    'Boats to the Kornati leave from Murter and other harbours on the island. '
                    'Tickets for the national park are required, and park rules apply once you '
                    'reach the islands. Plan an early start if you want a full day on the water.'
                ),
            },
            {
                'heading': 'Betina and the villages',
                'body': (
                    'Betina is known for building wooden boats, and a small museum explains the '
                    'craft. Jezera and Tisno have small harbours with a few restaurants. The '
                    'villages are close together, and the island can be explored by bike.'
                ),
            },
            {
                'heading': 'Beaches and sea',
                'body': (
                    'The coast has pebble beaches, coves with pines and calm water. Outside July '
                    'and August the island is much quieter, and some services run on reduced '
                    'schedules.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Murter — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Murter',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.8186,
        'longitude': 15.6,
    },
    {
        'name': 'Zlarin',
        'slug': 'zlarin',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/5/5f/Zlarinsss.JPG',
            'author': 'Shanticm ( talk )',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Zlarinsss.JPG',
        },
        'region': 'sibenik',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small island in the Šibenik archipelago with a coral-diving past, a quiet village '
            'and few cars.'
        ),
        'description': (
            'Zlarin is a small island in the Šibenik archipelago, a short boat ride from Šibenik.'
            ' It has a single village with a harbour, stone houses and a tradition of coral '
            'diving, and it has little car traffic. The rest of the island is olive groves, pines'
            ' and quiet coves.'
        ),
        'highlights': [
            'Zlarin village and harbour',
            'Coral-diving heritage',
            'Quiet coves and swimming',
            'Olive groves and paths',
            'Boat from Šibenik',
        ],
        'overview': (
            'Zlarin lies a short way off Šibenik, in the archipelago in front of the city. Its '
            'one village stands around a small harbour, with stone houses and a main square, and '
            'for centuries its people were known for diving for coral, which gave the island a '
            'place in the region’s history. Today, the island is quiet, largely free of cars, and'
            ' the paths between the village, the coves and the olive groves can be walked or '
            'cycled. There are small beaches and rocky coves where visitors swim, and a few '
            'restaurants and rooms are available in the village. Zlarin is reached by passenger '
            'boat from Šibenik, and timetables vary by season. The island makes a quiet day trip '
            'or a short stay.'
        ),
        'faqs': [
            {
                'q': 'Is Zlarin worth visiting?',
                'a': 'Yes, if you want a quiet island day with swimming and a walk, close to Šibenik.',
            },
            {
                'q': 'How do I get to Zlarin?',
                'a': (
                    'By passenger boat from Šibenik. Split Airport (SPU) and Zadar Airport (ZAD) '
                    'are the nearest airports.'
                ),
            },
            {
                'q': 'What is there to do on Zlarin?',
                'a': (
                    'Walk through the village, swim in the coves, follow the paths through olive '
                    'groves and eat at the harbour.'
                ),
            },
            {
                'q': 'How long should I spend on Zlarin?',
                'a': (
                    'A day trip is enough for most visitors; stay overnight for a quieter '
                    'experience.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June–September for swimming; May and late September for quieter visits',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet days, swimming, short walks',
            },
            {
                'label': 'Time needed',
                'value': 'A day',
            },
            {
                'label': 'Getting there',
                'value': 'Passenger boat from Šibenik',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'quiet breaks',
            'swimming',
            'walkers',
            'day trips',
            'couples',
        ],
        'sections': [
            {
                'heading': 'Coral and the village',
                'body': (
                    'Zlarin’s history is closely tied to coral, which local divers collected from'
                    ' the seabed for centuries. The village is built around the harbour, with '
                    'stone houses running up the slope behind it.'
                ),
            },
            {
                'heading': 'Coves and paths',
                'body': (
                    'Paths link the village to coves with pebble and rock where visitors swim. '
                    'The island is small, and a loop on foot takes a couple of hours. Bring water'
                    ' and sun protection, because there is limited shade.'
                ),
            },
            {
                'heading': 'Getting there',
                'body': (
                    'Boats run from Šibenik’s waterfront. Timetables change between summer and '
                    'winter, so check them and the last return before you go. In summer, boats '
                    'can be busy at weekends.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Zlarin — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Zlarin',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.6967,
        'longitude': 15.8483,
    },
    {
        'name': 'Drniš',
        'slug': 'drnis',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/b/be/Drni%C5%A1_-_panoramio_%282%29.jpg',
            'author': 'gorchfin',
            'licence': 'CC BY 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Drni%C5%A1_-_panoramio_(2).jpg',
        },
        'region': 'sibenik',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'An inland town in the Dalmatian hinterland, known for its smoked ham and for the '
            'sculptor Ivan Meštrović.'
        ),
        'description': (
            'Drniš lies inland from Šibenik in the Dalmatian hinterland, in the valley below the '
            'Promina and Moseć hills. It is known for Drniš ham (Drniški pršut), and the nearby '
            'village of Otavice holds the Meštrović Mausoleum, built by the sculptor Ivan '
            'Meštrović, who grew up in the area.'
        ),
        'highlights': [
            'Drniš ham (Drniški pršut)',
            'Meštrović Mausoleum at Otavice',
            'Stone houses of the old centre',
            'Road to Krka National Park',
            'Hills of the Dalmatian hinterland',
        ],
        'overview': (
            'Drniš is a small town inland from the coast, on the road between Šibenik and the '
            'Dalmatian hinterland, in a valley below hills. It is known for its dry-cured ham, '
            'Drniški pršut, which has a protected name. Nearby, in the village of Otavice, stands'
            ' the Meštrović Mausoleum, built in the 1920s and 1930s to a design by the sculptor '
            'Ivan Meštrović, who spent part of his childhood in Otavice and is buried there. The '
            'town itself is a quiet place with a main square and a few old houses. Drniš makes a '
            'useful stop for visitors who want to see the interior of Dalmatia, and the Roški '
            'slap area of Krka National Park is nearby. Many travellers pass through on the way '
            'between the coast and the mountains.'
        ),
        'faqs': [
            {
                'q': 'Is Drniš worth visiting?',
                'a': (
                    'It is a short stop for visitors interested in the interior of Dalmatia, '
                    'local food and the work of Ivan Meštrović.'
                ),
            },
            {
                'q': 'How do I get to Drniš?',
                'a': (
                    'By road from Šibenik or Split, and the A1 motorway has an exit at Drniš. '
                    'Split Airport (SPU) and Zadar Airport (ZAD) are the nearest airports.'
                ),
            },
            {
                'q': 'What is there to do in Drniš?',
                'a': (
                    'Taste local ham, visit the Meštrović Mausoleum at Otavice and combine the '
                    'trip with Krka National Park.'
                ),
            },
            {
                'q': 'How long should I spend in Drniš?',
                'a': 'A few hours to half a day.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'April–June and September–October',
            },
            {
                'label': 'Ideal for',
                'value': 'Food, culture, a break from the coast',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to half a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Šibenik or Split; A1 motorway exit at Drniš',
            },
            {
                'label': 'Region',
                'value': 'Sibenik',
            },
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU) or Zadar Airport (ZAD), each about an hour by road',
            },
        ],
        'good_for': [
            'food lovers',
            'culture',
            'road trips',
            'short stops',
            'Krka visitors',
        ],
        'sections': [
            {
                'heading': 'Drniš ham',
                'body': (
                    'Drniški pršut is made from pork legs that are salted and then air-dried in '
                    'the cold, dry wind of the hinterland. The result is a ham with a distinctive'
                    ' taste, sold locally by producers and in shops. Ask at the market or a local'
                    ' producer about tasting, because availability depends on the season.'
                ),
            },
            {
                'heading': 'Ivan Meštrović at Otavice',
                'body': (
                    'Ivan Meštrović, one of Croatia’s best-known sculptors, was raised in the '
                    'area. The mausoleum at Otavice, the family’s burial place, is a stone '
                    'building with sculptures, set above the village. Visiting hours vary, so '
                    'check them before travelling.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'The interior is hotter in summer and colder in winter than the coast. Roški '
                    'slap and Burnum, both parts of Krka National Park, are a drive away, which '
                    'makes it easy to build a day around the area.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Drniš — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Drni%C5%A1',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 43.8644,
        'longitude': 16.1608,
    },
]
