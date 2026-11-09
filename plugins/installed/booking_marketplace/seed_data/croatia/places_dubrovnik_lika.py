"""Croatia destinations: the Dubrovnik region and Lika (Places seed data).

Editorial town and area guides for croatia-experience.me. English, factual, no prices or
opening hours. Each dict follows the schema in docs/plans/croatia-catalogue-2026-11.md.
"""

from __future__ import annotations

_HR = 'https://croatia.hr/en-gb'

PLACES: list[dict] = [
    # ------------------------------------------------------------------ Dubrovnik region
    {
        'name': 'Dubrovnik',
        'slug': 'dubrovnik',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Casco_viejo_de_Dubrovnik%2C_Croacia%2C_2014-04-14%2C_DD_07.JPG/1280px-Casco_viejo_de_Dubrovnik%2C_Croacia%2C_2014-04-14%2C_DD_07.JPG',
            'author': 'Diego Delso',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Casco_viejo_de_Dubrovnik,_Croacia,_2014-04-14,_DD_07.JPG',
        },
        'region': 'dubrovnik',
        'place_type': 'cities',
        'featured': True,
        'summary': 'A walled Adriatic city of stone streets, fortresses and sea views at the '
        'southern tip of Croatia.',
        'description': (
            'Dubrovnik is a walled city on the southern Adriatic coast. Its old town, with the '
            'limestone-paved Stradun, the Rector’s Palace and the city walls, has been on the '
            'UNESCO World Heritage List since 1979.'
        ),
        'highlights': [
            'Walking the city walls',
            'The Stradun and Onofrio’s Fountain',
            'Rector’s Palace',
            'Lovrijenac Fortress',
            'Cable car up Mount Srđ',
        ],
        'overview': (
            'Dubrovnik grew as the maritime Republic of Ragusa, which kept its independence '
            'for centuries as a trading state on the Adriatic. The old town is still enclosed '
            'by its medieval and Renaissance walls, with Lovrijenac Fortress standing on a '
            'rock outside the western gate. Inside, the Stradun runs between the Pile and '
            'Ploče gates, lined with stone houses, while lanes climb in steps on both sides. '
            'Landmarks include Onofrio’s Fountain, the Rector’s Palace, the Sponza Palace and '
            'the Cathedral of the Assumption. The old harbour is small and sits at the '
            'eastern end of the town. Mount Srđ rises directly behind the city and can be '
            'reached by cable car or on foot, giving a view over the walls and the nearby '
            'islands. Damage from the 1991–92 siege was repaired afterwards, and the city '
            'remains a working town as well as a destination.'
        ),
        'faqs': [
            {
                'q': 'Is Dubrovnik worth visiting?',
                'a': 'Yes, if you want a historic walled town on the sea. The old town, the '
                'city walls and the view from Mount Srđ are the main reasons to come, and the '
                'islands and coast nearby add day trips.',
            },
            {
                'q': 'How do I get to Dubrovnik?',
                'a': 'Dubrovnik Airport (DBV) is at Čilipi, south-east of the city. Buses run '
                'along the coast from Split and Zagreb, and boats and ferries connect the '
                'city with nearby islands.',
            },
            {
                'q': 'What is there to do in Dubrovnik?',
                'a': 'Walk the city walls, follow the Stradun, visit the Rector’s Palace and '
                'Lovrijenac Fortress, ride the cable car to Mount Srđ and take a boat to '
                'Lokrum or the Elaphiti Islands.',
            },
            {
                'q': 'How long should I spend in Dubrovnik?',
                'a': 'One full day covers the old town and the walls. Two or three days leave '
                'time for the islands, Cavtat and a day along the Pelješac peninsula.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September–October'},
            {'label': 'Ideal for', 'value': 'History, sea views, island day trips'},
            {'label': 'Time needed', 'value': '1–3 days'},
            {'label': 'Getting there', 'value': 'Dubrovnik Airport (DBV) at Čilipi; coastal buses'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV), Čilipi'},
        ],
        'good_for': [
            'history lovers',
            'couples',
            'photographers',
            'island hopping',
            'city breaks',
        ],
        'sections': [
            {
                'heading': 'The Republic of Ragusa',
                'body': (
                    'For centuries Dubrovnik was the Republic of Ragusa, a trading state that '
                    'ran its own affairs and kept its independence into the early 19th '
                    'century. That past shows in the planning of the town: a regular grid of '
                    'streets, public fountains, a harbour and a council hall at its centre. '
                    'The town was inscribed on the UNESCO World Heritage List in 1979, and '
                    'much of what visitors see, from the walls to the palaces, comes from '
                    'that long period of independence.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The walls enclose the old town and can be walked in a circuit, with the '
                    'sea on one side and rooftops on the other. Along the Stradun are '
                    'Onofrio’s Fountain, the Franciscan monastery and the Sponza Palace. The '
                    'Rector’s Palace now holds a museum. Outside the western gate, Lovrijenac '
                    'Fortress stands on its own rock above the water. For a wider view, the '
                    'cable car climbs Mount Srđ behind the city.'
                ),
            },
            {
                'heading': 'Beyond the walls',
                'body': (
                    'Boats leave the old harbour for Lokrum, a short crossing away, and for '
                    'the Elaphiti Islands to the north-west. By road, Cavtat and the Konavle '
                    'valley lie to the south-east, while the Trsteno Arboretum and the town '
                    'of Ston are reached along the coast to the north-west. Ferries and '
                    'boats also run to Mljet and other islands, so Dubrovnik works as a base '
                    'for several days.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Dubrovnik — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Dubrovnik'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.6507,
        'longitude': 18.0944,
    },
    {
        'name': 'Cavtat',
        'slug': 'cavtat',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/View_of_Cavtat_20180820-2.jpg/1280px-View_of_Cavtat_20180820-2.jpg',
            'author': 'Suicasmo',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:View_of_Cavtat_20180820-2.jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A small harbour town on a peninsula south-east of Dubrovnik, with a '
        'waterfront promenade and a hilltop mausoleum.',
        'description': (
            'Cavtat is a small town on the coast south-east of Dubrovnik, close to the '
            'airport. It stands on the site of the ancient settlement of Epidaurum and has a '
            'palm-lined harbour front and a wooded peninsula.'
        ),
        'highlights': [
            'Harbour promenade',
            'Račić Mausoleum by Ivan Meštrović',
            'Vlaho Bukovac House',
            'Walk around the Rat peninsula',
            'Boat trips along the coast',
        ],
        'overview': (
            'Cavtat sits on a bay in the Konavle area, south-east of Dubrovnik. The town '
            'stands on the site of Epidaurum, a Greek and later Roman settlement, and takes '
            'its present name from the Latin civitas. A waterfront promenade runs around the '
            'harbour, with cafés and restaurants facing the boats. On the Rat peninsula, a '
            'walking path leads through pines to the Račić family mausoleum, a domed building '
            'designed by the sculptor Ivan Meštrović. The painter Vlaho Bukovac was born in '
            'Cavtat, and his family house is now a museum of his work. The town is close to '
            'Dubrovnik Airport and is often used as a quieter base for the Dubrovnik region. '
            'Boats run from the harbour along the coast, and Dubrovnik is reachable by road '
            'or by sea.'
        ),
        'faqs': [
            {
                'q': 'Is Cavtat worth visiting?',
                'a': 'Yes, for a smaller and calmer harbour town. The promenade, the Račić '
                'Mausoleum and the walk around the peninsula make a good half day.',
            },
            {
                'q': 'How do I get to Cavtat?',
                'a': 'Cavtat is close to Dubrovnik Airport (DBV). It is also reachable from '
                'Dubrovnik by road and by boat, and the town centre is easy to walk around.',
            },
            {
                'q': 'What is there to do in Cavtat?',
                'a': 'Walk the harbour promenade and the Rat peninsula path, visit the Račić '
                'Mausoleum and the Vlaho Bukovac House, and take a boat along the coast.',
            },
            {
                'q': 'How long should I spend in Cavtat?',
                'a': 'A half day is enough to see the main sights. Many visitors stay '
                'longer and use Cavtat as a base for the Dubrovnik area and Konavle.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September–October'},
            {'label': 'Ideal for', 'value': 'Seaside walks, art, a quiet base'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'Close to Dubrovnik Airport (DBV); road and boat'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'couples',
            'art lovers',
            'short walks',
            'quiet seaside stays',
            'families',
        ],
        'sections': [
            {
                'heading': 'From Epidaurum to Cavtat',
                'body': (
                    'People have lived on this headland since antiquity. Greeks settled here, '
                    'and the Romans later knew the town as Epidaurum. The settlement was '
                    'destroyed in the early Middle Ages, and its survivors are traditionally '
                    'said to have founded Ragusa, today’s Dubrovnik. The modern name comes '
                    'from the Latin civitas. Later, Cavtat belonged to the Republic of Ragusa, '
                    'whose rector’s palace still stands on the waterfront.'
                ),
            },
            {
                'heading': 'Art on the peninsula',
                'body': (
                    'Cavtat has two sights tied to well-known Croatian artists. The Račić '
                    'Mausoleum, on the cemetery hill of the Rat peninsula, was designed by '
                    'Ivan Meštrović for a local shipowning family. In the town, the Vlaho '
                    'Bukovac House preserves the home of the painter who was born here. Both '
                    'are small, and each can be seen in under an hour alongside a walk '
                    'through the pine woods on the peninsula.'
                ),
            },
            {
                'heading': 'Getting around the coast',
                'body': (
                    'Cavtat lies at the edge of Konavle, the southernmost part of Croatia, '
                    'and the Montenegrin border is not far to the south-east. Boats from the '
                    'harbour run along the coast, and Dubrovnik can be reached by road '
                    'or by sea. The airport is nearby, which makes the town a convenient '
                    'first or last stop on a trip to the region.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Cavtat — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Cavtat'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.5792,
        'longitude': 18.2178,
    },
    {
        'name': 'Lokrum',
        'slug': 'lokrum',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Lokrum2.JPG/1280px-Lokrum2.JPG',
            'author': 'Timur Voronkov',
            'licence': 'Public domain',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Lokrum2.JPG',
        },
        'region': 'dubrovnik',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A wooded island just off Dubrovnik with a former monastery, a botanical '
        'garden and rocky swimming spots.',
        'description': (
            'Lokrum is a small, car-free island a short boat ride from the old harbour of '
            'Dubrovnik. It is a nature reserve with pine and holm-oak woods, a former '
            'Benedictine monastery, a botanical garden and a small salt lake.'
        ),
        'highlights': [
            'Former Benedictine monastery',
            'Botanical garden',
            'Fort Royal',
            'The Dead Sea salt lake',
            'Swimming from the rocks',
        ],
        'overview': (
            'Lokrum lies about 600 metres off the coast at Dubrovnik and is protected as a '
            'nature reserve. Boats from the old harbour make the short crossing, and visitors '
            'explore on foot along shaded paths through woods of pine and holm oak. A '
            'Benedictine monastery stood on the island from the Middle Ages, and its '
            'buildings and cloister survive beside a garden of plants collected from around '
            'the world. On the highest point, Fort Royal was built by the French in the '
            'early 19th century and gives a view back to the city. The island has a small '
            'salt lake known as the Dead Sea (Mrtvo more), and the coast is rock and '
            'pebble, with places to swim. Peacocks roam freely. Lokrum is a place for a '
            'half-day escape from the old town.'
        ),
        'faqs': [
            {
                'q': 'Is Lokrum worth visiting?',
                'a': 'Yes, for a quiet half day on the water. It offers shaded walks, a '
                'monastery and garden, and swimming places a few minutes from the old town.',
            },
            {
                'q': 'How do I get to Lokrum?',
                'a': 'Boats cross from the old harbour in Dubrovnik. The crossing is short, '
                'and the schedule depends on the season, so check before you go.',
            },
            {
                'q': 'What is there to do on Lokrum?',
                'a': 'Walk the island paths, see the monastery and botanical garden, climb to '
                'Fort Royal, look at the Dead Sea lake and swim from the rocks.',
            },
            {
                'q': 'How long should I spend on Lokrum?',
                'a': 'Plan on three to five hours, including the boat crossing. Bring water '
                'and shoes suitable for rock and pebble.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–October for swimming; spring for walking'},
            {'label': 'Ideal for', 'value': 'Nature walks, swimming, a break from the old town'},
            {'label': 'Time needed', 'value': 'Half a day'},
            {'label': 'Getting there', 'value': 'Boat from the old harbour in Dubrovnik'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'nature lovers',
            'swimmers',
            'families',
            'walkers',
            'day trips',
        ],
        'sections': [
            {
                'heading': 'A nature reserve',
                'body': (
                    'The whole island is a protected nature reserve. Paths cross woods of '
                    'Aleppo pine and holm oak and lead to small bays, and the island is '
                    'The setting is calm because of how close it '
                    'is to the city: the old town walls are visible across the strait. '
                    'Peacocks, which were introduced to the island, are a common sight along '
                    'the paths.'
                ),
            },
            {
                'heading': 'Monastery and garden',
                'body': (
                    'Benedictines settled on Lokrum in the Middle Ages and built a '
                    'monastery that was later converted into a residence. Part of the '
                    'complex and its cloister remain. Around it lies a botanical garden '
                    'with plants from several continents, planted in the 19th century. '
                    'Fort Royal, built by French troops in the early 1800s, crowns the '
                    'island’s high point and is reached by a path through the woods.'
                ),
            },
            {
                'heading': 'Swimming and walks',
                'body': (
                    'The coast is rock and pebble. The small salt lake called the Dead Sea '
                    'is joined to the open water by a narrow channel and is popular with '
                    'families because the water is calm. There are marked walking trails of '
                    'different length. Because the island has no shops outside the main '
                    'landing area, bring what you need for the day and plan your return boat '
                    'in advance.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Lokrum — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Lokrum'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.6256,
        'longitude': 18.1239,
    },
    {
        'name': 'Elaphiti Islands',
        'slug': 'elaphiti-islands',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/Insel_Lopud_in_Kroatien_%2848612708518%29.jpg/1280px-Insel_Lopud_in_Kroatien_%2848612708518%29.jpg',
            'author': 'dronepicr',
            'licence': 'CC BY 2.0',
            'licence_url': 'https://creativecommons.org/licenses/by/2.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Insel_Lopud_in_Kroatien_(48612708518).jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A chain of small islands north-west of Dubrovnik, with Koločep, Lopud and '
        'Šipan the inhabited ones.',
        'description': (
            'The Elaphiti Islands, or Elafiti, lie just north-west of Dubrovnik. Koločep, '
            'Lopud and Šipan are the inhabited islands, with villages, pine woods, '
            'old churches and small beaches, reached by regular boat.'
        ),
        'highlights': [
            'Koločep village and bays',
            'Lopud’s sandy beach at Šunj',
            'Šipan, the largest of the three',
            'Walks through pine and olive groves',
            'Boat excursions from Dubrovnik',
        ],
        'overview': (
            'The Elaphiti Islands form a short chain off the coast north-west of Dubrovnik. '
            'Three are inhabited: Koločep, nearest to the city, Lopud in the middle and '
            'Šipan, the largest of the group. They have small villages, churches from the '
            'Republic of Ragusa period and the remains of summer houses once built by '
            'Dubrovnik’s merchant families. Paths cross pine woods and olive and citrus '
            'groves, and the coasts have coves for swimming. Lopud is known for the sandy '
            'beach at Šunj, unusual on a coast of rock and pebble. Šipan has fields and '
            'vineyards in its central valley. Boats from Dubrovnik call at the islands on '
            'regular lines, and day excursions combine two or three of them with a '
            'swim and a lunch ashore.'
        ),
        'faqs': [
            {
                'q': 'Are the Elaphiti Islands worth visiting?',
                'a': 'Yes, if you want a quiet day close to Dubrovnik. The islands have '
                'walking paths, small villages and places to swim without long travel.',
            },
            {
                'q': 'How do I get to the Elaphiti Islands?',
                'a': 'Boats and ferries leave Dubrovnik for Koločep, Lopud and Šipan. '
                'Timetables change with the season, so check ahead.',
            },
            {
                'q': 'What is there to do on the Elaphiti Islands?',
                'a': 'Walk the island paths, swim from the beaches and coves, visit the old '
                'churches and village centres, and eat in the waterfront restaurants.',
            },
            {
                'q': 'How long should I spend on the Elaphiti Islands?',
                'a': 'One island fills a day. Excursion boats visit two or three in a day, '
                'with a few hours on each.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–October'},
            {'label': 'Ideal for', 'value': 'Island day trips, swimming, easy walks'},
            {'label': 'Time needed', 'value': 'A day'},
            {'label': 'Getting there', 'value': 'Boat or ferry from Dubrovnik'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'island hopping',
            'swimmers',
            'families',
            'easy walks',
            'quiet escapes',
        ],
        'sections': [
            {
                'heading': 'Three inhabited islands',
                'body': (
                    'Koločep is the closest to Dubrovnik and has two small settlements, '
                    'Donje Čelo and Gornje Čelo. Lopud lies in the middle and has a village '
                    'with a small harbour and several old churches. Šipan is the largest and '
                    'has two main villages, Šipanska Luka and Sudurađ. The other islets of '
                    'the group are uninhabited. Together they were part of the territory of '
                    'the Republic of Ragusa.'
                ),
            },
            {
                'heading': 'Villages, churches and summer houses',
                'body': (
                    'Dubrovnik’s wealthy families built summer houses and chapels on the '
                    'islands, especially on Lopud and Šipan, and ruins of some of these '
                    'still stand among the trees. The village churches are usually small and '
                    'whitewashed. The pace is slow, and the islands are best seen on foot, '
                    'following the paths from the harbour to a viewpoint or a cove on the '
                    'other side.'
                ),
            },
            {
                'heading': 'Swimming and planning',
                'body': (
                    'The coast is mostly rock and pebble, with the sandy Šunj beach on Lopud '
                    'as an exception. Facilities are modest outside the villages, so bring '
                    'water and sun protection. Because the boats run on a timetable that '
                    'depends on the season, note the time of the last return crossing before '
                    'you set out on a longer walk.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Elaphiti Islands — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Elaphiti_Islands',
            },
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.6900,
        'longitude': 17.9400,
    },
    {
        'name': 'Ston',
        'slug': 'ston',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/St._Blaise_Church%2C_Ston_01.jpg/1280px-St._Blaise_Church%2C_Ston_01.jpg',
            'author': 'Bernard Gagnon',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:St._Blaise_Church,_Ston_01.jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A small walled town at the neck of the Pelješac peninsula, known for its '
        'long defensive walls, salt pans and oysters.',
        'description': (
            'Ston is a small town at the base of the Pelješac peninsula. It is known for the '
            'defensive walls that link it with Mali Ston, for its historic salt pans and '
            'for the shellfish farmed in the nearby bay.'
        ),
        'highlights': [
            'The Walls of Ston',
            'Mali Ston and its shellfish',
            'Historic salt pans',
            'Walks along the town’s ramparts',
            'The Pelješac wine road',
        ],
        'overview': (
            'Ston lies where the Pelješac peninsula meets the mainland, north-west of '
            'Dubrovnik. The Republic of Ragusa built a fortified town here to protect the '
            'peninsula and its salt, and a line of walls about five kilometres long still '
            'climbs the hill above the town and runs down to Mali Ston, a smaller settlement '
            'on the bay. The salt pans beside Ston have produced salt for centuries and '
            'are still worked. Mali Ston Bay is known for oysters and mussels, and the '
            'restaurants of Mali Ston serve them. The streets of Ston are small and '
            'regular, laid out on a planned grid, with a few churches and a '
            'former rector’s palace. Many visitors stop here on the road between Dubrovnik '
            'and the rest of the Pelješac peninsula, whose vineyards lie further on.'
        ),
        'faqs': [
            {
                'q': 'Is Ston worth visiting?',
                'a': 'Yes, for the walls, the salt pans and the seafood. It is a small town '
                'and fits easily into a day along the coast from Dubrovnik.',
            },
            {
                'q': 'How do I get to Ston?',
                'a': 'Ston is on the main coastal road north-west of Dubrovnik, at the start '
                'of the Pelješac peninsula. The drive from Dubrovnik takes about an hour. '
                'Buses also serve the town.',
            },
            {
                'q': 'What is there to do in Ston?',
                'a': 'Walk the Walls of Ston, visit the salt pans, eat oysters and mussels '
                'in Mali Ston, and continue to the vineyards on the Pelješac peninsula.',
            },
            {
                'q': 'How long should I spend in Ston?',
                'a': 'Two to four hours cover the walls and a meal. A full day lets you add '
                'the peninsula’s wineries.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn for walking the walls'},
            {'label': 'Ideal for', 'value': 'History, seafood, wine road stops'},
            {'label': 'Time needed', 'value': '2–4 hours'},
            {'label': 'Getting there', 'value': 'By road from Dubrovnik, about an hour'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'history lovers',
            'food lovers',
            'wine routes',
            'day trips',
            'road trips',
        ],
        'sections': [
            {
                'heading': 'A fortress for salt',
                'body': (
                    'The Republic of Ragusa bought the Pelješac peninsula in the 14th '
                    'century and fortified its narrowest point. Salt was a main reason: the '
                    'pans at Ston were a source of revenue for the republic. The walls were '
                    'built to protect both the town and the pans and connect Ston with Mali '
                    'Ston across the hill. Parts of the walls were damaged by earthquakes '
                    'and have been restored in recent decades.'
                ),
            },
            {
                'heading': 'Walls, pans and oysters',
                'body': (
                    'Visitors can climb onto parts of the walls for a view over the town, '
                    'the pans and the bay. The salt pans are next to the road and can be '
                    'seen from the edge. In Mali Ston Bay, oysters and mussels are farmed, '
                    'and local restaurants build their menus around them. The shellfish '
                    'grounds are the reason many travellers stop here on a day trip.'
                ),
            },
            {
                'heading': 'Onwards on Pelješac',
                'body': (
                    'Beyond Ston the road runs along the Pelješac peninsula, which is known '
                    'for its vineyards, especially around Potomje and Trstenik, and for '
                    'villages such as Orebić at its western end. The Pelješac Bridge, which '
                    'opened in 2022, links the peninsula with the mainland to the north '
                    'without crossing Bosnia and Herzegovina’s short coastline at Neum.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Ston — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Ston'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.8400,
        'longitude': 17.6950,
    },
    {
        'name': 'Orebić',
        'slug': 'orebic',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Izme%C4%91u_dvi_stine1140337.JPG/1280px-Izme%C4%91u_dvi_stine1140337.JPG',
            'author': 'Quahadi Añtó 15:42, 15 January 2011 (UTC)',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Izme%C4%91u_dvi_stine1140337.JPG',
        },
        'region': 'dubrovnik',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A seaside town on the Pelješac peninsula facing Korčula, with a mountain '
        'behind it and a maritime history.',
        'description': (
            'Orebić is a coastal town at the western end of the Pelješac peninsula, across '
            'a narrow channel from the island of Korčula. Mount Sveti Ilija rises behind '
            'it, and the town has a long seafaring tradition.'
        ),
        'highlights': [
            'Walk up Mount Sveti Ilija',
            'Maritime Museum Orebić',
            'Trstenica beach',
            'Ferry crossing to Korčula',
            'Pelješac wine tasting nearby',
        ],
        'overview': (
            'Orebić lies on the southern shore of the Pelješac peninsula, facing the island '
            'of Korčula across a channel less than two kilometres wide. For centuries it was '
            'a home of ship captains, and its Maritime Museum keeps the records of that '
            'tradition. Behind the town rises Mount Sveti Ilija, which can be climbed on '
            'marked paths and gives a view across the channel to Korčula and over the '
            'islands. A Franciscan monastery stands on the shore just outside the town. The '
            'beach at Trstenica is a long pebble beach, and the channel’s steady wind makes '
            'the area a known place for windsurfing and kitesurfing. A car ferry runs '
            'between Orebić and Dominče, near Korčula town, and the wine villages '
            'of the peninsula are within a short drive.'
        ),
        'faqs': [
            {
                'q': 'Is Orebić worth visiting?',
                'a': 'Yes, for a quieter coastal stay with views of Korčula, a mountain walk '
                'and access to the Pelješac wine villages.',
            },
            {
                'q': 'How do I get to Orebić?',
                'a': 'By road along the Pelješac peninsula, which is reached from Dubrovnik '
                'via Ston. A ferry connects Orebić with Korčula.',
            },
            {
                'q': 'What is there to do in Orebić?',
                'a': 'Climb Mount Sveti Ilija, visit the Maritime Museum, swim at Trstenica, '
                'try windsurfing in the channel and taste wine on the peninsula.',
            },
            {
                'q': 'How long should I spend in Orebić?',
                'a': 'A day covers the town and the beach. Add half a day for the climb up '
                'Sveti Ilija.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–October; spring for hiking'},
            {'label': 'Ideal for', 'value': 'Hiking, windsurfing, wine routes'},
            {'label': 'Time needed', 'value': 'A day or more'},
            {'label': 'Getting there', 'value': 'By road via Ston; ferry to Korčula'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'hikers',
            'windsurfers',
            'wine routes',
            'seaside stays',
            'island access',
        ],
        'sections': [
            {
                'heading': 'A town of sea captains',
                'body': (
                    'Orebić grew in the 17th to 19th centuries as a base of the Pelješac '
                    'merchant fleet. Many local men served as ship captains, and the town '
                    'still has large houses built for them along the shore. The Maritime '
                    'Museum holds ship models, paintings and documents from that period. '
                    'The channel in front of the town has always been a busy sea lane '
                    'between the peninsula and Korčula.'
                ),
            },
            {
                'heading': 'Mountain and channel',
                'body': (
                    'Mount Sveti Ilija rises steeply above the town. Marked paths lead up '
                    'from Orebić, and a Franciscan monastery stands on the shore at its foot. '
                    'The channel below is exposed to wind, which suits windsurfing '
                    'and kitesurfing. On calm days the water is good for swimming, and '
                    'the pebble beach at Trstenica lies a few minutes from the centre.'
                ),
            },
            {
                'heading': 'Wine and the ferry',
                'body': (
                    'The Pelješac peninsula is a wine-growing area, and the steep slopes '
                    'around Orebić and nearby Potomje are planted with red grapes. Cellars '
                    'in the villages receive visitors by appointment. The ferry to Dominče '
                    'on Korčula takes a short time and carries cars, so a day on the island '
                    'is easy to add. Check the timetable, which changes with the season.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Orebić — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Orebi%C4%87'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.9747,
        'longitude': 17.1772,
    },
    {
        'name': 'Korčula',
        'slug': 'korcula',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Kor%C4%8Dula_23h.jpg/1280px-Kor%C4%8Dula_23h.jpg',
            'author': 'Miroslav.vajdic',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Kor%C4%8Dula_23h.jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'cultural',
        'featured': True,
        'summary': 'A walled old town on a small peninsula on the island of Korčula, with a '
        'cathedral, narrow lanes and sea views.',
        'description': (
            'Korčula town is a fortified old town on the east side of the island of Korčula. '
            'Its streets are laid out in a herringbone pattern, and it is home to St Mark’s '
            'Cathedral, the Moreška sword dance and local white wine.'
        ),
        'highlights': [
            'St Mark’s Cathedral',
            'The old town walls and towers',
            'Herringbone street plan',
            'The Moreška sword dance',
            'Pošip wine from the island',
        ],
        'overview': (
            'Korčula town sits on a small peninsula that juts into the channel between the '
            'island of Korčula and the Pelješac peninsula. A ring of walls and towers '
            'surrounds the old town, which grew under Venetian and then Ragusan influence. '
            'Its streets branch off the main street in a herringbone pattern, a layout often '
            'explained by the wish to break the wind and let in the breeze. St Mark’s '
            'Cathedral, built in stone from local quarries, stands at the highest point. '
            'According to local tradition, the house of the explorer Marco Polo is in the '
            'town, although historians disagree about his birthplace. The island is also '
            'known for the Moreška, a sword dance performed in the town, and for Pošip, a '
            'white wine made on Korčula. Ferries link the island with the mainland and '
            'Orebić across the channel.'
        ),
        'faqs': [
            {
                'q': 'Is Korčula town worth visiting?',
                'a': 'Yes, for its compact walled old town, its cathedral and the views '
                'across the channel. It is easy to see on foot.',
            },
            {
                'q': 'How do I get to Korčula?',
                'a': 'The island has ferry links with the mainland, including a short '
                'crossing from Orebić on the Pelješac peninsula. Catamarans and ferries '
                'also run along the coast.',
            },
            {
                'q': 'What is there to do in Korčula?',
                'a': 'Walk the old town and the walls, visit St Mark’s Cathedral, see a '
                'Moreška performance when it is held, and taste Pošip wine.',
            },
            {
                'q': 'How long should I spend in Korčula?',
                'a': 'The old town can be seen in a few hours. Stay a night or more to add '
                'the island’s beaches and villages.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September–October'},
            {'label': 'Ideal for', 'value': 'History, architecture, wine, easy walking'},
            {'label': 'Time needed', 'value': 'A day or an overnight stay'},
            {'label': 'Getting there', 'value': 'Ferry or boat; short crossing from Orebić'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'history lovers',
            'couples',
            'wine lovers',
            'photographers',
            'island stays',
        ],
        'sections': [
            {
                'heading': 'A planned medieval town',
                'body': (
                    'The old town stands on an oval peninsula. The main street runs along '
                    'its spine, and smaller streets branch off at an angle, giving the '
                    'plan its herringbone shape. Towers and walls protect the landward '
                    'side. The town was under Venetian rule for much of the late Middle '
                    'Ages and later, and the Venetian influence is visible in the stonework '
                    'of its houses and loggias.'
                ),
            },
            {
                'heading': 'Cathedral and traditions',
                'body': (
                    'St Mark’s Cathedral dominates the old town square and was built over '
                    'several centuries. The Moreška, a dance with swords that tells of a '
                    'contest between two armies, has been performed on Korčula for a long '
                    'time and is staged for visitors in the summer. Marco Polo’s name is '
                    'attached to a house in the town by local tradition, and a small '
                    'museum or tower is shown to visitors under that name.'
                ),
            },
            {
                'heading': 'The island around the town',
                'body': (
                    'Beyond the town, Korčula has pine forests, vineyards and small '
                    'villages. The wine villages of Lumbarda and Smokvica produce white '
                    'wines, including Pošip and Grk. Bays with pebble beaches lie along '
                    'the coast, and the island can be explored by car or bicycle. A car '
                    'ferry also links Dominče, near the town, to Orebić on the mainland.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Korčula — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Kor%C4%8Dula',
            },
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.9597,
        'longitude': 17.1352,
    },
    {
        'name': 'Mljet National Park',
        'slug': 'mljet-national-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Zalazak.jpg/1280px-Zalazak.jpg',
            'author': 'Jaganjac',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Zalazak.jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'national_parks',
        'featured': False,
        'summary': 'The wooded western end of Mljet island, with two saltwater lakes and a '
        'former monastery on an islet.',
        'description': (
            'Mljet National Park covers the western part of the island of Mljet. It centres '
            'on two connected saltwater lakes, Veliko jezero and Malo jezero, surrounded by '
            'Aleppo pine forest, with a Benedictine monastery on the islet of St Mary.'
        ),
        'highlights': [
            'Veliko jezero and Malo jezero',
            'St Mary’s islet and monastery',
            'Walking and cycling around the lakes',
            'Pomena and Polače villages',
            'Roman palace remains at Polače',
        ],
        'overview': (
            'Mljet is one of the more forested islands of the Adriatic, and its western '
            'end has been a national park since 1960. The park’s centre is two lakes of '
            'seawater, Veliko jezero (the Big Lake) and Malo jezero (the Small Lake), joined '
            'to each other and to the open sea by narrow channels. On a small island in '
            'the Big Lake stands the monastery of St Mary, founded by Benedictines in the '
            'Middle Ages. Paths and a cycle route run along the shores, and visitors can '
            'swim in the lakes. Boats take visitors to the islet. The villages of Pomena '
            'and Polače, at the park’s edges, have small harbours and restaurants, and at '
            'Polače the ruins of a late Roman palace can be seen near the shore. Ferries '
            'and boats link the island with Dubrovnik and the Pelješac peninsula.'
        ),
        'faqs': [
            {
                'q': 'Is Mljet National Park worth visiting?',
                'a': 'Yes, for a quiet, forested island setting with lakes where you can '
                'swim, walk and cycle. It suits a day trip or an overnight stay.',
            },
            {
                'q': 'How do I get to Mljet National Park?',
                'a': 'Ferries sail to Sobra from Prapratno on the Pelješac peninsula, and '
                'boats run from Dubrovnik to Sobra and Polače. Schedules change with the '
                'season, so check ahead.',
            },
            {
                'q': 'What is there to do in Mljet National Park?',
                'a': 'Walk or cycle around the lakes, take the boat to St Mary’s islet, '
                'swim, and visit Pomena and Polače.',
            },
            {
                'q': 'How long should I spend in Mljet National Park?',
                'a': 'One full day covers the lakes and the islet. Stay overnight for '
                'a slower visit.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–October'},
            {'label': 'Ideal for', 'value': 'Walking, cycling, swimming, quiet nature'},
            {'label': 'Time needed', 'value': 'A day or more'},
            {'label': 'Getting there', 'value': 'Ferry from Prapratno or boat from Dubrovnik'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'nature lovers',
            'cyclists',
            'swimmers',
            'families',
            'quiet stays',
        ],
        'sections': [
            {
                'heading': 'Two lakes of seawater',
                'body': (
                    'The lakes are depressions in the limestone that were flooded by the '
                    'sea and are connected to it by narrow channels. The tide moves water '
                    'in and out of the channel between the Big Lake and the sea, and the '
                    'water in the lakes is calmer and warmer than the open sea. The shores '
                    'are covered by Aleppo pine, and the island is known for its '
                    'green interior.'
                ),
            },
            {
                'heading': 'St Mary and Polače',
                'body': (
                    'On the islet of St Mary in the Big Lake, Benedictines built a church '
                    'and monastery in the 12th century. The buildings have been restored '
                    'and are among the park’s best-known sights, reached by a short boat '
                    'ride. In Polače, on the north coast of the park, the remains of a '
                    'late Roman palace stand beside the harbour, a reminder that the '
                    'island was settled long before the monks arrived.'
                ),
            },
            {
                'heading': 'Walking and cycling',
                'body': (
                    'A path circles the lakes, and bicycles can be rented in Pomena and '
                    'Polače. The terrain around the lakes is mostly flat, with gentle '
                    'climbs to viewpoints. Entry to the park is ticketed, so check the '
                    'park’s website for current information before you go, and bring water '
                    'and sun protection for the day.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Mljet National Park — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Mljet_National_Park',
            },
            {'label': 'Mljet National Park — official site', 'url': 'https://np-mljet.hr/en/'},
        ],
        'latitude': 42.7600,
        'longitude': 17.3600,
    },
    {
        'name': 'Lastovo',
        'slug': 'lastovo',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Skrivena_luka%2C_Lastovo.jpg/1280px-Skrivena_luka%2C_Lastovo.jpg',
            'author': 'Dijana Župan',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Skrivena_luka,_Lastovo.jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A remote, wooded island and nature park in the outer Adriatic, with a '
        'hillside town of distinctive chimneys.',
        'description': (
            'Lastovo is a remote island south of Korčula, surrounded by smaller islets that '
            'together form the Lastovo Archipelago Nature Park. Its main town climbs a '
            'hillside above a bowl-shaped valley and is known for its decorated chimneys.'
        ),
        'highlights': [
            'Lastovo town and its chimneys',
            'The Lastovo Archipelago Nature Park',
            'Clear night skies',
            'Diving and boating among the islets',
            'The Poklad carnival',
        ],
        'overview': (
            'Lastovo is one of the outermost inhabited islands of the Croatian Adriatic, '
            'south of Korčula. It is surrounded by dozens of small islands, and the whole '
            'group is protected as the Lastovo Archipelago Nature Park. The island is '
            'densely wooded and has few people. Its main settlement, Lastovo town, is built '
            'on the inside slope of a hillside, facing away from the sea, and is known for '
            'its stone chimneys of varied shapes. Because there is little artificial '
            'light, the night sky is dark and clear. The island is known for the '
            'Poklad, a carnival held before Lent, with a traditional procession. Visitors '
            'come for walking, diving and sailing among the islets. Reaching the island '
            'takes time, as it depends on ferries and boats.'
        ),
        'faqs': [
            {
                'q': 'Is Lastovo worth visiting?',
                'a': 'Yes, if you want a quiet island with little tourism, clear skies and '
                'sea and woodland to explore. It suits visitors who plan ahead.',
            },
            {
                'q': 'How do I get to Lastovo?',
                'a': 'By ferry, usually from Split or via Vela Luka on Korčula, and by '
                'private boat. Timetables depend on the season, so check them before '
                'you plan the trip.',
            },
            {
                'q': 'What is there to do on Lastovo?',
                'a': 'Walk through the town and the woods, swim and dive around the nearby '
                'islets, sail or kayak in the nature park, and watch the night sky.',
            },
            {
                'q': 'How long should I spend on Lastovo?',
                'a': 'At least two nights are sensible given how long the journey takes. '
                'A day trip is rarely practical.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–October'},
            {'label': 'Ideal for', 'value': 'Quiet stays, diving, sailing, stargazing'},
            {'label': 'Time needed', 'value': 'Two nights or more'},
            {'label': 'Getting there', 'value': 'Ferry or private boat'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'quiet escapes',
            'divers',
            'sailors',
            'stargazers',
            'nature lovers',
        ],
        'sections': [
            {
                'heading': 'An island apart',
                'body': (
                    'Lastovo is far from the mainland, and for much of the 20th century it '
                    'was closed to visitors because of its military use. That left its '
                    'coast and woods largely untouched. The Lastovo Archipelago was '
                    'declared a nature park in 2006, and the island is now a place for '
                    'quiet holidays rather than mass tourism.'
                ),
            },
            {
                'heading': 'The town and its chimneys',
                'body': (
                    'Lastovo town is built on a slope that faces inland, which hid it from '
                    'pirates and from the wind. Its houses are stone, and many have '
                    'chimneys with distinctive, decorative tops. The Poklad, the '
                    'carnival before Lent, ends with the burning of a figure and a '
                    'procession. Details of the event vary from '
                    'year to year.'
                ),
            },
            {
                'heading': 'The nature park',
                'body': (
                    'The park covers the island and the surrounding islets and sea. The '
                    'waters are used for diving and sailing, and a few places on the coast '
                    'are set up for visitors. Guided trips and boat rentals are available '
                    'in season. Bring supplies, because services on the island are limited '
                    'and shops have short hours outside summer.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Lastovo — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Lastovo'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.7625,
        'longitude': 16.8975,
    },
    {
        'name': 'Trsteno Arboretum',
        'slug': 'trsteno-arboretum',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Arboretum_Trsteno_%28by_Pudelek%29.JPG/1280px-Arboretum_Trsteno_%28by_Pudelek%29.JPG',
            'author': 'Pudelek (Marcin Szala)',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Arboretum_Trsteno_(by_Pudelek).JPG',
        },
        'region': 'dubrovnik',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A historic garden and arboretum on the coast north-west of Dubrovnik, '
        'laid out by a Ragusan noble family.',
        'description': (
            'The Trsteno Arboretum is a garden by the sea in the village of Trsteno, '
            'north-west of Dubrovnik. It was started by the Gučetić family in the late '
            '15th century and combines a Renaissance layout with a park of later plantings.'
        ),
        'highlights': [
            'Two very old plane trees at the entrance',
            'Renaissance garden and pergola',
            'The Neptune fountain and pond',
            'The aqueduct',
            'Sea views from the terraces',
        ],
        'overview': (
            'Trsteno is a village on the coast about twenty kilometres north-west of '
            'Dubrovnik, and the arboretum is its main attraction. The garden was begun by '
            'the Gučetić (Gozze) family, nobles of the Republic of Ragusa, who built a summer '
            'residence here at the end of the 15th century. The oldest part is laid out in '
            'the Renaissance style, with a pergola, a pond and a fountain of Neptune, and '
            'an aqueduct that once carried water to the gardens. Two plane trees near the '
            'entrance are said to be around five hundred years old. Later owners added '
            'trees and shrubs from many countries, and the arboretum is now run by the '
            'Croatian Academy of Sciences and Arts. A path leads down to a small harbour '
            'on the sea.'
        ),
        'faqs': [
            {
                'q': 'Is the Trsteno Arboretum worth visiting?',
                'a': 'Yes, if you like gardens and history. It is a quiet, shaded place '
                'with a Renaissance layout and sea views, close to Dubrovnik.',
            },
            {
                'q': 'How do I get to the Trsteno Arboretum?',
                'a': 'Trsteno is on the coastal road north-west of Dubrovnik, around twenty '
                'kilometres from the city. Buses and cars both serve the village.',
            },
            {
                'q': 'What is there to see at the Trsteno Arboretum?',
                'a': 'The old plane trees, the Neptune fountain and pond, the pergola, the '
                'aqueduct and the plants collected over the centuries.',
            },
            {
                'q': 'How long should I spend at the Trsteno Arboretum?',
                'a': 'Plan one to two hours for the garden, or a half day if you combine it '
                'with the nearby coast.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn'},
            {'label': 'Ideal for', 'value': 'Gardens, history, a quiet stop near Dubrovnik'},
            {'label': 'Time needed', 'value': '1–2 hours'},
            {'label': 'Getting there', 'value': 'By road or bus north-west of Dubrovnik'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'garden lovers',
            'history lovers',
            'photographers',
            'quiet stops',
            'couples',
        ],
        'sections': [
            {
                'heading': 'A noble family’s garden',
                'body': (
                    'The Gučetić family built a summer residence at Trsteno in the late '
                    '15th century and laid out a garden beside it. The house and garden '
                    'stayed in the family for generations, and the garden grew with plants '
                    'brought by merchants and sailors from the Republic of Ragusa’s '
                    'trading routes. Today it is a protected monument.'
                ),
            },
            {
                'heading': 'What is in the garden',
                'body': (
                    'The Renaissance part of the garden includes a stone pergola above the '
                    'sea, a pond with the Neptune fountain and an aqueduct that brought '
                    'water down from the hills. Around it grow cypresses, palms, '
                    'citrus and a wide range of trees from other continents. A path leads '
                    'to the lower terrace and the small harbour, with the Elaphiti Islands '
                    'visible offshore.'
                ),
            },
            {
                'heading': 'Care and visiting',
                'body': (
                    'The Croatian Academy of Sciences and Arts has cared for the arboretum '
                    'since the 20th century. Fire damaged part of the grounds in 2000, and '
                    'the garden has since been replanted and restored. Visiting is '
                    'straightforward from Dubrovnik by bus or car, and the arboretum '
                    'pairs well with a stop in Ston or a swim on the coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Trsteno Arboretum — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Trsteno_Arboretum',
            },
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.7119,
        'longitude': 18.0000,
    },
    {
        'name': 'Konavle',
        'slug': 'konavle',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/Konavle_%2811%29.jpg/1280px-Konavle_%2811%29.jpg',
            'author': 'Ivan Petrović Poljak',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Konavle_(11).jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'The fertile southernmost valley of Croatia, with villages, vineyards, '
        'folk traditions and the airport at Čilipi.',
        'description': (
            'Konavle is the farthest south-eastern part of Croatia, a green valley between '
            'the sea and the mountains that run along the border with Montenegro. It is '
            'known for its villages, vineyards, embroidery and folk traditions.'
        ),
        'highlights': [
            'Čilipi and its Sunday folklore tradition',
            'Konavle embroidery',
            'Sokol Grad fortress',
            'Vineyards and local wines',
            'Villages with old stone houses',
        ],
        'overview': (
            'Konavle lies south-east of Dubrovnik, a long, fertile valley enclosed by hills '
            'on the landward side and open to the sea at Cavtat. It was once part of the '
            'Republic of Ragusa, which bought it in the 15th century, and the valley kept a '
            'strong rural culture. Čilipi, the village beside Dubrovnik Airport, is known '
            'for its folk costumes and dance, which have been shown in the village at '
            'Sunday performances. The area is known for embroidery, with traditional '
            'patterns on women’s costume. Sokol Grad, a fortress on a rock above the valley '
            'near Gruda, dates from the Middle Ages and was a Ragusan stronghold. The '
            'valley has vineyards, olive groves and small farms, and local restaurants '
            'serve food made from what is grown there.'
        ),
        'faqs': [
            {
                'q': 'Is Konavle worth visiting?',
                'a': 'Yes, for a rural side of the Dubrovnik region: villages, vineyards, '
                'folk traditions and quiet roads, close to the coast.',
            },
            {
                'q': 'How do I get to Konavle?',
                'a': 'By road from Dubrovnik, south-east along the coast. Dubrovnik Airport '
                'is in Čilipi, in the middle of Konavle.',
            },
            {
                'q': 'What is there to do in Konavle?',
                'a': 'Visit Čilipi and Cavtat, see Sokol Grad, taste local wine and food, '
                'and look for embroidery and folk costume.',
            },
            {
                'q': 'How long should I spend in Konavle?',
                'a': 'A half day covers the main villages. A full day with Cavtat and a '
                'winery visit gives a fuller picture.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn'},
            {'label': 'Ideal for', 'value': 'Rural culture, wine, quiet drives'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'By road from Dubrovnik; airport at Čilipi'},
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV), Čilipi'},
        ],
        'good_for': [
            'culture lovers',
            'wine lovers',
            'road trips',
            'families',
            'quiet stays',
        ],
        'sections': [
            {
                'heading': 'A valley under Ragusa',
                'body': (
                    'The Republic of Ragusa acquired Konavle in the early 15th century and '
                    'held it until the republic ended in 1808. The valley supplied the city '
                    'with food and wine, and its villages kept their own customs. '
                    'Fortresses such as Sokol Grad and the walled towns along the coast '
                    'were built to defend it.'
                ),
            },
            {
                'heading': 'Folk culture',
                'body': (
                    'Konavle is known in Croatia for its embroidery, silk-making and '
                    'folk costume. Čilipi preserves the tradition of dances and songs, '
                    'performed in the village in front of the church on certain Sundays '
                    'during the season. Check the local programme for dates, which change '
                    'from year to year.'
                ),
            },
            {
                'heading': 'Land and table',
                'body': (
                    'The valley floor is farmland, with vineyards, olive groves and '
                    'orchards, and small family estates sell wine and olive oil. Local '
                    'restaurants serve regional dishes, and the valley is a calm contrast to '
                    'the crowded old town of Dubrovnik. Cavtat, at the seaward end, offers '
                    'swimming and a harbour promenade.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Konavle — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Konavle'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 42.5300,
        'longitude': 18.3200,
    },
    {
        'name': 'Neretva Delta',
        'slug': 'neretva-delta',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/U%C5%A1%C4%87e_Neretve_002.jpg/1280px-U%C5%A1%C4%87e_Neretve_002.jpg',
            'author': 'Ivan25',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:U%C5%A1%C4%87e_Neretve_002.jpg',
        },
        'region': 'dubrovnik',
        'place_type': 'lakes',
        'featured': False,
        'summary': 'The wetland delta of the Neretva river, a flat landscape of channels, '
        'reed beds, orchards and wildlife.',
        'description': (
            'The Neretva Delta is a wide wetland where the Neretva river reaches the '
            'Adriatic. Channels, reed beds and lagoons are mixed with farmland growing '
            'citrus fruit, and the area is important for birds.'
        ),
        'highlights': [
            'Boat trips on the river channels',
            'Mandarin orchards',
            'Birdwatching in the reed beds',
            'Local eel and frog dishes',
            'Opuzen and Metković',
        ],
        'overview': (
            'The Neretva is the largest river that flows into the Adriatic from the east, '
            'and near its mouth it spreads into a delta of channels, lagoons and reed beds. '
            'The delta lies between the towns of Metković and Ploče and is crossed by '
            'canals dug to drain the land for farming. Orchards of mandarins are a '
            'local speciality, as are fruit and vegetables. The reed beds and '
            'wetlands are home to many birds, and parts of the delta are protected as nature '
            'reserves. Traditional wooden boats, called trupica, were once the main transport '
            'on the channels, and visitors can take boat trips in the lower '
            'delta. The local cooking is known for eel and frog, which are prepared as a '
            'stew. Opuzen, a small town on the river, is a convenient '
            'centre.'
        ),
        'faqs': [
            {
                'q': 'Is the Neretva Delta worth visiting?',
                'a': 'Yes, if you like wetlands, birdwatching and a slower, rural side of '
                'the region. It is flat and quiet, a change from the rocky coast.',
            },
            {
                'q': 'How do I get to the Neretva Delta?',
                'a': 'By road from Dubrovnik or Split along the coast. Opuzen and Metković '
                'are the main towns, and the delta lies between them and the sea.',
            },
            {
                'q': 'What is there to do in the Neretva Delta?',
                'a': 'Take a boat trip, watch birds, taste local food and fruit, and '
                'visit Opuzen and the nature reserves.',
            },
            {
                'q': 'How long should I spend in the Neretva Delta?',
                'a': 'A half day covers a boat trip and a meal. A full day lets you add '
                'bird reserves and a walk.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn for birds'},
            {'label': 'Ideal for', 'value': 'Wildlife, boat trips, local food'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {
                'label': 'Getting there',
                'value': 'By road along the coast; towns of Opuzen, Metković',
            },
            {'label': 'Region', 'value': 'Dubrovnik'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (DBV)'},
        ],
        'good_for': [
            'birdwatchers',
            'nature lovers',
            'food lovers',
            'boat trips',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'A river meets the sea',
                'body': (
                    'The Neretva rises in the mountains of Bosnia and Herzegovina and '
                    'crosses into Croatia for its last stretch, where it opens into a '
                    'delta. Over the last two centuries much of the marsh was drained for '
                    'agriculture, but a core of wetland remains. The result is a mix of '
                    'fields, canals and wild reed beds that changes with the season.'
                ),
            },
            {
                'heading': 'Wildlife and boats',
                'body': (
                    'Several parts of the delta are protected as nature reserves, and the '
                    'reed beds and lagoons attract water birds, especially in spring and '
                    'autumn migration. Boat trips run on the river channels, often in '
                    'traditional wooden boats. The trips are a quiet way to see herons and '
                    'other birds from the water.'
                ),
            },
            {
                'heading': 'Fruit and food',
                'body': (
                    'The delta’s farmland is known for mandarins, which are picked in the '
                    'autumn, and for vegetables and fruit sold at roadside stalls. '
                    'Restaurants serve local dishes based on eel and frog, which are '
                    'traditional on the river. Opuzen, on the river, is a pleasant place to stop and eat.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Neretva — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Neretva'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 43.0300,
        'longitude': 17.4500,
    },
    # ------------------------------------------------------------------------------ Lika
    {
        'name': 'Plitvice Lakes National Park',
        'slug': 'plitvice-lakes-national-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Plitvice_Lakes1.jpg/1280px-Plitvice_Lakes1.jpg',
            'author': 'Tesla Delacroix',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Plitvice_Lakes1.jpg',
        },
        'region': 'lika',
        'place_type': 'national_parks',
        'featured': True,
        'summary': 'A chain of sixteen terraced lakes joined by waterfalls in forested '
        'hills, on the UNESCO World Heritage List.',
        'description': (
            'Plitvice Lakes National Park, in the Lika region, is a series of sixteen named '
            'lakes joined by waterfalls and cascades over natural travertine barriers. It '
            'has been a national park since 1949 and a UNESCO World Heritage Site since 1979.'
        ),
        'highlights': [
            'The Upper and Lower Lakes',
            'Veliki Slap, the large waterfall',
            'Wooden boardwalks over the water',
            'Electric boat across Kozjak lake',
            'Beech and fir forests',
        ],
        'overview': (
            'Plitvice Lakes National Park lies in the hills of Lika, between Zagreb and the '
            'Dalmatian coast. Its sixteen named lakes are arranged in steps, with water '
            'passing from one to the next over barriers of travertine, a rock that the '
            'water itself builds up slowly from dissolved limestone. The Upper Lakes lie in '
            'a dolomite valley and the Lower Lakes in limestone with deeper canyons. Wooden '
            'boardwalks and paths run over and beside the water, and a boat crosses the '
            'largest lake, Kozjak. The park also protects forests of beech and fir that are '
            'home to bears, wolves and many birds. The area was declared a national park '
            'in 1949 and inscribed on the UNESCO World Heritage List in 1979. Swimming '
            'is not allowed within the park, and visitors keep to the marked paths.'
        ),
        'faqs': [
            {
                'q': 'Is Plitvice Lakes National Park worth visiting?',
                'a': 'Yes, if you like waterfalls and walking. The lakes, boardwalks and '
                'forests are the reason it is one of Croatia’s best-known parks.',
            },
            {
                'q': 'How do I get to Plitvice Lakes National Park?',
                'a': 'By road from Zagreb or Zadar, in roughly two hours from each. Buses '
                'also stop at the park’s entrances. The nearest airports are Zagreb '
                '(ZAG) and Zadar (ZAD).',
            },
            {
                'q': 'What is there to do at Plitvice Lakes National Park?',
                'a': 'Walk the boardwalks and trails, take the electric boat across '
                'Kozjak lake, see the waterfalls and watch for birds in the forest.',
            },
            {
                'q': 'How long should I spend at Plitvice Lakes National Park?',
                'a': 'Plan on four to six hours to see the main parts of the park. Stay '
                'overnight nearby to visit early or late in the day.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring for high water; autumn for colour'},
            {'label': 'Ideal for', 'value': 'Walking, waterfalls, photography'},
            {'label': 'Time needed', 'value': '4–6 hours'},
            {'label': 'Getting there', 'value': 'By road from Zagreb or Zadar, about 2 hours'},
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zadar (ZAD) or Zagreb (ZAG)'},
        ],
        'good_for': [
            'hikers',
            'photographers',
            'families',
            'nature lovers',
            'day trips from Zagreb',
        ],
        'sections': [
            {
                'heading': 'How the lakes formed',
                'body': (
                    'The lakes exist because of travertine. As water rich in dissolved '
                    'limestone flows over moss and algae, it deposits rock that grows into '
                    'natural dams. Over thousands of years these dams have raised the '
                    'water level and created the stepped chain of lakes seen today. The '
                    'process continues, which is why the park asks visitors to stay on the '
                    'paths and keep out of the water.'
                ),
            },
            {
                'heading': 'Upper and Lower Lakes',
                'body': (
                    'The Upper Lakes are a series of larger lakes with gentle shores and '
                    'wide cascades. The Lower Lakes are smaller and sit in a steeper '
                    'canyon, and the tallest waterfall, Veliki Slap, drops into the river '
                    'Korana at their lower end. Boardwalks cross the water at many points. '
                    'Several marked routes of different lengths combine the two sections '
                    'with boat and shuttle rides.'
                ),
            },
            {
                'heading': 'Forests and visiting',
                'body': (
                    'Beech and fir forest covers the slopes around the lakes, and the park '
                    'is home to brown bears, wolves and many species of birds and '
                    'butterflies. The park has two main entrances, and tickets and routes '
                    'are managed by the park authority, so check the official site '
                    'for current rules before you go. Paths can be crowded at midday in '
                    'summer, and early or late visits are quieter.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Plitvice Lakes National Park — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Plitvice_Lakes_National_Park',
            },
            {
                'label': 'Plitvice Lakes National Park — official site',
                'url': 'https://np-plitvicka-jezera.hr/en/',
            },
        ],
        'latitude': 44.8654,
        'longitude': 15.5820,
    },
    {
        'name': 'Rastoke',
        'slug': 'rastoke',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Rastoke_1510.JPG/1280px-Rastoke_1510.JPG',
            'author': 'Karl Gruber',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Rastoke_1510.JPG',
        },
        'region': 'lika',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A village quarter of Slunj where the Slunjčica river tumbles over small '
        'waterfalls past old watermills.',
        'description': (
            'Rastoke is the old quarter of Slunj, a small town in the hills north of '
            'Plitvice Lakes. The Slunjčica river falls over travertine steps into the '
            'Korana, and old wooden houses and watermills stand on and between the cascades.'
        ),
        'highlights': [
            'Cascades of the Slunjčica river',
            'Old watermills and wooden houses',
            'Confluence with the Korana',
            'Walking paths and viewpoints',
            'Local trout dishes',
        ],
        'overview': (
            'Rastoke is part of Slunj, a town in the hills of Kordun, north of Plitvice '
            'Lakes. Here the small river Slunjčica reaches the larger Korana, and just '
            'before the meeting it breaks into many small waterfalls and cascades over '
            'travertine, the same rock that forms the lakes at Plitvice. Houses and '
            'watermills were built on and between the falls, many of them of wood and stone, and '
            'the water once turned mill wheels used for grinding grain and fulling cloth. '
            'Footpaths and small bridges run through the quarter, and viewpoints look over '
            'the cascades. Several mills have been restored, and some now house '
            'restaurants. Rastoke is a short stop on the road between Zagreb and Plitvice '
            'and a place for a walk and a meal rather than a full-day visit.'
        ),
        'faqs': [
            {
                'q': 'Is Rastoke worth visiting?',
                'a': 'Yes, as a short stop. It is a small village quarter with waterfalls '
                'and old mills, and it fits well on the road to or from Plitvice.',
            },
            {
                'q': 'How do I get to Rastoke?',
                'a': 'Rastoke is in Slunj, on the road between Karlovac and Plitvice Lakes. '
                'It is about an hour and a half from Zagreb by car, and buses stop in '
                'Slunj.',
            },
            {
                'q': 'What is there to do in Rastoke?',
                'a': 'Walk the paths along the cascades, look at the mills and houses, '
                'and eat in one of the restaurants by the water.',
            },
            {
                'q': 'How long should I spend in Rastoke?',
                'a': 'One to two hours is enough for the walk and a meal.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn'},
            {'label': 'Ideal for', 'value': 'Short walks, photography, a stop on the way'},
            {'label': 'Time needed', 'value': '1–2 hours'},
            {'label': 'Getting there', 'value': 'By road to Slunj, on the way to Plitvice'},
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG) or Zadar (ZAD)'},
        ],
        'good_for': [
            'photographers',
            'short walks',
            'road trips',
            'families',
            'food stops',
        ],
        'sections': [
            {
                'heading': 'Where two rivers meet',
                'body': (
                    'The Slunjčica is a short river that drops through travertine '
                    'terraces before joining the Korana. The meeting point lies in a '
                    'small canyon, and the old quarter of Rastoke spreads over the '
                    'terraces above it. The sound of falling water is constant, and the '
                    'air is cooler than in the town above.'
                ),
            },
            {
                'heading': 'Mills and houses',
                'body': (
                    'Mills have stood here for centuries, using the river’s '
                    'drop to drive wheels. Many of the houses stand directly over the '
                    'water on stone and timber foundations. After the mills went out of use, '
                    'some of the buildings were restored, and the quarter is now '
                    'protected as a cultural landmark. Paths and small footbridges lead '
                    'through it.'
                ),
            },
            {
                'heading': 'On the way to Plitvice',
                'body': (
                    'Rastoke is a convenient break on the route between Zagreb and '
                    'Plitvice Lakes. Visitors often walk the main path, take photographs '
                    'from the viewpoints and eat a meal, with trout a common dish in the '
                    'restaurants. For a longer visit, Slunj also offers walks along the '
                    'Korana.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Slunj — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Slunj'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 45.1186,
        'longitude': 15.5850,
    },
    {
        'name': 'Northern Velebit National Park',
        'slug': 'northern-velebit-national-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Karstformationen_Nationalpark-Nord-Velebit.JPG/1280px-Karstformationen_Nationalpark-Nord-Velebit.JPG',
            'author': 'Rootmaker',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0/',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Karstformationen_Nationalpark-Nord-Velebit.JPG',
        },
        'region': 'lika',
        'place_type': 'national_parks',
        'featured': False,
        'summary': 'A high karst mountain park on the Velebit range, with limestone peaks, '
        'beech forests and a famous hiking trail.',
        'description': (
            'Northern Velebit National Park covers a rugged part of the Velebit range above '
            'the Adriatic coast. It protects limestone peaks, deep caves, beech and fir '
            'forests and a botanical garden, and is crossed by the Premužić Trail.'
        ),
        'highlights': [
            'Hajdučki and Rožanski kukovi limestone towers',
            'The Premužić Trail',
            'Zavižan mountain hut and botanical garden',
            'Beech and fir forests',
            'Karst caves such as Lukina jama',
        ],
        'overview': (
            'Northern Velebit National Park lies on the Velebit, the long mountain range '
            'that runs parallel to the Adriatic coast. The park, declared in 1999, '
            'protects a high karst landscape of limestone ridges, sinkholes and caves, and '
            'forests of beech and fir. In the centre of the park are the Hajdučki and '
            'Rožanski kukovi, groups of limestone towers and pillars that are a strictly '
            'protected reserve. The Premužić Trail, built in the 1930s along the ridge '
            'by the engineer Ante Premužić, is a well-known long-distance route '
            'through the park, with views to the sea and islands. At Zavižan, a mountain '
            'hut and weather station stand beside a botanical garden of Velebit plants. '
            'The park’s visitor centre is in Krasno. Hiking is the main activity, and '
            'access to some parts is restricted.'
        ),
        'faqs': [
            {
                'q': 'Is Northern Velebit National Park worth visiting?',
                'a': 'Yes, for hikers who want a high mountain landscape with views to '
                'the sea. It is wilder and quieter than the coast.',
            },
            {
                'q': 'How do I get to Northern Velebit National Park?',
                'a': 'By road from Gospić or from the coast near Senj, with the visitor '
                'centre in Krasno. The nearest airports are Zadar (ZAD) and Zagreb (ZAG).',
            },
            {
                'q': 'What is there to do in Northern Velebit National Park?',
                'a': 'Hike the Premužić Trail and other marked routes, visit the botanical '
                'garden at Zavižan and see the limestone towers of the strict reserve.',
            },
            {
                'q': 'How long should I spend in Northern Velebit National Park?',
                'a': 'A day covers a short route. Longer hikes need one or more days and '
                'good preparation.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'Hiking, mountain views, botany'},
            {'label': 'Time needed', 'value': 'A day or several days'},
            {
                'label': 'Getting there',
                'value': 'By road via Gospić or Senj; visitor centre in Krasno',
            },
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zadar (ZAD) or Zagreb (ZAG)'},
        ],
        'good_for': [
            'hikers',
            'mountain lovers',
            'botanists',
            'photographers',
            'multi-day treks',
        ],
        'sections': [
            {
                'heading': 'A karst mountain park',
                'body': (
                    'The park sits on limestone, and rain and snowmelt disappear into the '
                    'rock, shaping sinkholes, shafts and caves. The caves include Lukina '
                    'jama, a deep shaft that is known to cavers. The surface is a mix of '
                    'meadows, rocky ridges and forest, and weather can change quickly '
                    'at altitude. The mountains also form a climate barrier between the '
                    'coast and the interior.'
                ),
            },
            {
                'heading': 'The Premužić Trail',
                'body': (
                    'Ante Premužić designed the trail in the 1930s, and it follows the '
                    'contours of the mountain with an even gradient and stone-built '
                    'edges. It crosses open ground and forest and has long views toward '
                    'the sea and the islands of Pag and Rab. It forms part of a longer '
                    'mountain route along the Velebit. Water is scarce on the ridge, so '
                    'carry what you need.'
                ),
            },
            {
                'heading': 'Forests and protection',
                'body': (
                    'The park’s forests of beech and fir shelter bears, wolves and lynx, '
                    'and some of the beech stands belong to a UNESCO World Heritage '
                    'listing for ancient beech forests. The Hajdučki and Rožanski kukovi '
                    'are a strict reserve, with access limited to protect them. Check the '
                    'park’s information before a visit, since rules and trail conditions '
                    'vary with the season.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Northern Velebit National Park — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Northern_Velebit_National_Park',
            },
            {
                'label': 'Northern Velebit National Park — official site',
                'url': 'https://np-sjeverni-velebit.hr/en/',
            },
        ],
        'latitude': 44.7900,
        'longitude': 14.9800,
    },
    {
        'name': 'Gospić',
        'slug': 'gospic',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/e/e8/Gospic_panorama_s_novog_mosta.JPG',
            'author': 'INekic',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Gospic_panorama_s_novog_mosta.JPG',
        },
        'region': 'lika',
        'place_type': 'cities',
        'featured': False,
        'summary': 'The main town of Lika, set on a plain between Velebit and Plitvice, and a '
        'base for Smiljan and Velebit.',
        'description': (
            'Gospić is the administrative centre of Lika-Senj County, in a high plain '
            'between the Velebit mountains and the Plitvice area. It is a small working '
            'town and a practical base for the Lika region.'
        ),
        'highlights': [
            'Cathedral of the Annunciation',
            'Lika Museum',
            'Nikola Tesla Memorial Centre in nearby Smiljan',
            'Gateway to Northern Velebit',
            'Lika countryside',
        ],
        'overview': (
            'Gospić lies on the Lika plateau, around five hundred metres above sea level, '
            'with the Velebit mountains to the south-west. It is the seat of Lika-Senj '
            'County and the largest town in the area, and its history includes a long '
            'period on the Habsburg Military Frontier. The town has a modest centre with '
            'a cathedral, a regional museum and a number of 19th-century buildings. The '
            'main reason many travellers come is nearby Smiljan, a village a few '
            'kilometres away, where the inventor Nikola Tesla was born in 1856 and where a '
            'memorial centre now stands. Gospić also works as a practical base for '
            'Northern Velebit National Park and Plitvice Lakes, both within a drive of '
            'about an hour. The surrounding Lika countryside is sparsely populated, with '
            'meadows, forests and small farms.'
        ),
        'faqs': [
            {
                'q': 'Is Gospić worth visiting?',
                'a': 'It is worth a stop for Smiljan, the town’s museum and as a base for '
                'the mountains and lakes of Lika, rather than as a sightseeing city.',
            },
            {
                'q': 'How do I get to Gospić?',
                'a': 'By road along the A1 motorway from Zagreb or Zadar, and by bus. The '
                'nearest airports are Zadar (ZAD) and Zagreb (ZAG).',
            },
            {
                'q': 'What is there to do in Gospić?',
                'a': 'Visit the Lika Museum and the cathedral, go to the Tesla Memorial '
                'Centre in Smiljan, and use the town as a base for Velebit and Plitvice.',
            },
            {
                'q': 'How long should I spend in Gospić?',
                'a': 'A few hours cover the town. Add half a day for Smiljan.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'A base for Lika, Tesla heritage'},
            {'label': 'Time needed', 'value': 'A few hours; longer as a base'},
            {'label': 'Getting there', 'value': 'By road or bus; near the A1 motorway'},
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zadar (ZAD) or Zagreb (ZAG)'},
        ],
        'good_for': [
            'road trips',
            'Tesla fans',
            'hikers',
            'a regional base',
            'history lovers',
        ],
        'sections': [
            {
                'heading': 'A frontier town',
                'body': (
                    'Gospić became an important town in the 17th and 18th centuries, when '
                    'Lika was part of the Habsburg Military Frontier, a defensive zone '
                    'against the Ottoman empire. The town was damaged in the wars of the '
                    '20th century and rebuilt afterwards. Today it is a small, '
                    'regional centre with services for the area.'
                ),
            },
            {
                'heading': 'Tesla’s Smiljan',
                'body': (
                    'Nikola Tesla was born in 1856 in Smiljan, a village a short drive '
                    'from Gospić. The Memorial Centre Nikola Tesla there includes his '
                    'birthplace and the church where his father served as a priest, and '
                    'presents his work with exhibits and demonstrations. It is the area’s '
                    'best-known visitor sight.'
                ),
            },
            {
                'heading': 'A base for Lika',
                'body': (
                    'From Gospić, Northern Velebit National Park and its visitor centre '
                    'in Krasno are about an hour away, and the Gacka valley and Plitvice '
                    'Lakes are both within reach by car. The town has hotels, shops and '
                    'restaurants, and it lies close to the motorway that links Zagreb '
                    'with the Dalmatian coast.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Gospić — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Gospi%C4%87'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 44.5461,
        'longitude': 15.3747,
    },
    {
        'name': 'Cerovac Caves',
        'slug': 'cerovac-caves',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/Posjetitelji_kod_jezerca%2C_Gornja_%C5%A1pilja.jpg/1280px-Posjetitelji_kod_jezerca%2C_Gornja_%C5%A1pilja.jpg',
            'author': 'Nikola Turkalj',
            'licence': 'CC BY 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Posjetitelji_kod_jezerca,_Gornja_%C5%A1pilja.jpg',
        },
        'region': 'lika',
        'place_type': 'mountains',
        'featured': False,
        'summary': 'A karst cave system on the southern slopes of Velebit, near Gračac, with '
        'chambers, formations and traces of prehistoric life.',
        'description': (
            'The Cerovac Caves are a group of caves on the southern slope of the Velebit '
            'mountains, close to the town of Gračac. Parts of the system are open to guided '
            'visits and show stalactites, stalagmites and finds from the Stone Age.'
        ),
        'highlights': [
            'Guided cave tour',
            'Stalactites and stalagmites',
            'Prehistoric finds in the caves',
            'Velebit foothills scenery',
            'Hiking nearby',
        ],
        'overview': (
            'The Cerovac Caves lie on the southern slopes of Velebit, near Gračac, in a '
            'karst landscape of limestone ridges and sinkholes. The system is made up of '
            'several caves, and a section has been opened for guided tours, with lighting '
            'and paths that follow the passages. Inside are the usual karst formations, '
            'stalactites hanging from the ceiling and stalagmites rising from the floor, '
            'together with larger chambers. Archaeologists have found traces of prehistoric '
            'people and the bones of cave animals in the caves, which makes them of '
            'interest beyond the formations themselves. The temperature inside stays cool '
            'throughout the year, so bring a warm layer. The caves can only be visited '
            'with a guide, and tour times are set by the operator, so check ahead.'
        ),
        'faqs': [
            {
                'q': 'Are the Cerovac Caves worth visiting?',
                'a': 'Yes, for a guided look at a karst cave system and its formations, '
                'especially if you are already travelling in Lika or on the road to the '
                'coast.',
            },
            {
                'q': 'How do I get to the Cerovac Caves?',
                'a': 'By road to Gračac, then a short drive to the caves. The nearest '
                'airport is Zadar (ZAD), and Zagreb (ZAG) is the other main option.',
            },
            {
                'q': 'What is there to do at the Cerovac Caves?',
                'a': 'Join a guided tour of the cave passages and chambers, and see the '
                'formations and the displays about the finds.',
            },
            {
                'q': 'How long should I spend at the Cerovac Caves?',
                'a': 'Allow about two hours including the tour and the drive from Gračac.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn; the cave is cool all year'},
            {'label': 'Ideal for', 'value': 'Caves, geology, a stop on the road'},
            {'label': 'Time needed', 'value': 'About 2 hours'},
            {'label': 'Getting there', 'value': 'By road via Gračac'},
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zadar (ZAD)'},
        ],
        'good_for': [
            'cave lovers',
            'families',
            'geology fans',
            'road trips',
            'rainy days',
        ],
        'sections': [
            {
                'heading': 'Karst underground',
                'body': (
                    'Velebit is made of limestone, and rain has dissolved passages and '
                    'chambers into the rock over a very long time. The Cerovac Caves are '
                    'one result, with a network of galleries that extends beneath the '
                    'foothills. Water still drips from the ceilings and slowly builds the '
                    'formations that visitors see on the tour.'
                ),
            },
            {
                'heading': 'Finds from the past',
                'body': (
                    'Excavations in the caves have recovered traces of prehistoric people '
                    'and the remains of animals such as the cave bear. The caves '
                    'sheltered people in the Stone Age, and a guide can explain the finds.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'The caves are visited with a guide only, and the path is lit but '
                    'includes steps and damp surfaces, so wear shoes with a good grip. The '
                    'temperature underground is much lower than outside in summer. Gračac '
                    'is the nearest town for food and fuel, and the caves can be combined '
                    'with walks in the Velebit foothills.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Cerovačke špilje — Wikipedia (Croatian)',
                'url': 'https://hr.wikipedia.org/wiki/Cerova%C4%8Dke_%C5%A1pilje',
            },
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 44.2719,
        'longitude': 15.8922,
    },
    {
        'name': 'Krasno',
        'slug': 'krasno',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Krasnarsko_polje.JPG/1280px-Krasnarsko_polje.JPG',
            'author': 'Damir Jelic',
            'licence': 'CC BY 2.5',
            'licence_url': 'https://creativecommons.org/licenses/by/2.5',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Krasnarsko_polje.JPG',
        },
        'region': 'lika',
        'place_type': 'mountains',
        'featured': False,
        'summary': 'A mountain village in the Krasno karst field below Velebit, and the '
        'entrance point to Northern Velebit National Park.',
        'description': (
            'Krasno is a small village in a karst field on the landward side of Northern '
            'Velebit. It is the site of the national park’s visitor centre and a starting '
            'point for walks and drives into the mountains.'
        ),
        'highlights': [
            'Northern Velebit National Park visitor centre',
            'Walks in the Krasno field',
            'Access to Zavižan and the Premužić Trail',
            'Mountain meadows and beech forest',
            'Quiet village stays',
        ],
        'overview': (
            'Krasno is a village in the hills of Lika, set in a flat karst basin called '
            'Krasno polje, ringed by forested slopes below the northern part of the Velebit. '
            'It has few residents and lies on the road that links the Lika plain with the '
            'coast near Senj. The village is the seat of the visitor centre of Northern '
            'Velebit National Park, where visitors can learn about the park and its '
            'trails before heading into the mountains. From the area, paths and forest roads '
            'lead toward the high ridge, and the park’s mountain hut at Zavižan can be '
            'reached by a longer route. The landscape around Krasno is one of meadows, '
            'beech woods and farmland, with a quiet, rural feel. Accommodation is limited '
            'and mostly in small guesthouses, so plan ahead.'
        ),
        'faqs': [
            {
                'q': 'Is Krasno worth visiting?',
                'a': 'Yes, if you are heading into Northern Velebit. It is a small, quiet '
                'village that serves as an entrance to the park.',
            },
            {
                'q': 'How do I get to Krasno?',
                'a': 'By road from Gospić or from Senj on the coast. There is little public '
                'transport, so most visitors drive. The nearest airports are Zadar (ZAD) '
                'and Zagreb (ZAG).',
            },
            {
                'q': 'What is there to do in Krasno?',
                'a': 'Visit the national park’s visitor centre, walk in the surrounding '
                'meadows and forest, and set out for the Velebit trails.',
            },
            {
                'q': 'How long should I spend in Krasno?',
                'a': 'A few hours are enough for the visitor centre and a short walk. '
                'Stay a night or more if you plan a longer hike.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'Hiking base, quiet mountain stays'},
            {'label': 'Time needed', 'value': 'A few hours to a night'},
            {'label': 'Getting there', 'value': 'By road from Gospić or Senj'},
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zadar (ZAD) or Zagreb (ZAG)'},
        ],
        'good_for': [
            'hikers',
            'quiet stays',
            'nature lovers',
            'park visitors',
            'road trips',
        ],
        'sections': [
            {
                'heading': 'A village in a karst field',
                'body': (
                    'Krasno polje is a basin typical of limestone country: a flat floor '
                    'with no surface outlet, where water drains underground. The village '
                    'sits on its edge, with fields and pasture on the flat ground and '
                    'forest on the slopes. Winters are cold and snowy, and in summer the '
                    'climate is cooler than on the coast.'
                ),
            },
            {
                'heading': 'The park’s visitor centre',
                'body': (
                    'The visitor centre of Northern Velebit National Park is in Krasno. '
                    'It gives information on trails, rules and conditions in the park, and '
                    'explains its geology, plants and animals. It is a sensible first stop '
                    'before a hike, since conditions in the high mountains can differ a '
                    'lot from those in the valley.'
                ),
            },
            {
                'heading': 'Into the mountains',
                'body': (
                    'From the Krasno area, roads and paths lead up toward the ridge of '
                    'Northern Velebit and the Premužić Trail, with Zavižan as a main '
                    'destination. Some forest roads are narrow and unpaved, so check the '
                    'route and the weather first, and carry water and food. The village '
                    'itself is quiet and has only basic services.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Northern Velebit National Park — official site',
                'url': 'https://np-sjeverni-velebit.hr/en/',
            },
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 44.823,
        'longitude': 15.051,
    },
    {
        'name': 'Gacka River',
        'slug': 'gacka-river',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Izvor_Gacke_Majerovo_vrilo.jpg/1280px-Izvor_Gacke_Majerovo_vrilo.jpg',
            'author': '1Moment.hr',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Izvor_Gacke_Majerovo_vrilo.jpg',
        },
        'region': 'lika',
        'place_type': 'lakes',
        'featured': False,
        'summary': 'A clear, spring-fed river in the Gacka valley near Otočac, known for '
        'trout and old watermills.',
        'description': (
            'The Gacka is a short river in the Lika valley near Otočac. It rises from karst '
            'springs, flows through meadows and past old mills, and is known among anglers '
            'for its trout.'
        ),
        'highlights': [
            'Clear spring-fed water',
            'Trout fishing',
            'Old watermills',
            'Otočac and its old town',
            'Riverside walks',
        ],
        'overview': (
            'The Gacka flows through a broad karst valley in Lika, around the town of '
            'Otočac, between the Velebit range and the hills to the north. It is fed by '
            'springs, so the water is clear and cool through the year, and the river runs '
            'for only a few tens of kilometres before it sinks into the limestone near '
            'Brlog. It is known for trout, and fly fishing on the Gacka attracts anglers, '
            'who need a permit. Along its banks stand old stone watermills, some '
            'now used as cafés or kept as monuments. Meadows and reed beds line the '
            'water, and the valley is a good place for a quiet walk or cycle. Otočac, on '
            'the river, has an old centre. The area lies on the road '
            'between Gospić and Senj.'
        ),
        'faqs': [
            {
                'q': 'Is the Gacka River worth visiting?',
                'a': 'Yes, for a quiet, rural stretch of clear water. It suits anglers, '
                'walkers and anyone looking for a slow stop in Lika.',
            },
            {
                'q': 'How do I get to the Gacka River?',
                'a': 'By road to Otočac, which is on the route between Gospić and Senj. '
                'The nearest airports are Zadar (ZAD) and Zagreb (ZAG).',
            },
            {
                'q': 'What is there to do at the Gacka River?',
                'a': 'Fish for trout with a permit, walk or cycle along the banks, see the '
                'old watermills and visit Otočac.',
            },
            {
                'q': 'How long should I spend at the Gacka River?',
                'a': 'A couple of hours suit a walk and a look at the mills. Anglers will '
                'want a full day.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn'},
            {'label': 'Ideal for', 'value': 'Fishing, quiet walks, rural scenery'},
            {'label': 'Time needed', 'value': 'A few hours to a day'},
            {'label': 'Getting there', 'value': 'By road to Otočac'},
            {'label': 'Region', 'value': 'Lika'},
            {'label': 'Nearest airport', 'value': 'Zadar (ZAD) or Zagreb (ZAG)'},
        ],
        'good_for': [
            'anglers',
            'walkers',
            'cyclists',
            'quiet stays',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'A river from springs',
                'body': (
                    'The Gacka begins in karst springs in the valley, so it carries clean '
                    'water with a steady temperature. Because the valley floor is low, '
                    'the river spreads into several channels and small lakes. After a '
                    'short course it disappears into the limestone, a pattern that is '
                    'common in this part of Croatia.'
                ),
            },
            {
                'heading': 'Trout and mills',
                'body': (
                    'Anglers value the river for its trout and for the setting. Fishing '
                    'is controlled, and visitors need a permit and must follow the local '
                    'rules. Along the banks stand watermills that once ground grain, and '
                    'their stone buildings add to the scenery. A few have been restored '
                    'and are open as small cafés or exhibition spaces.'
                ),
            },
            {
                'heading': 'Otočac and the valley',
                'body': (
                    'Otočac is the main town of the Gacka valley and has a small old '
                    'centre on the river. From here, the road '
                    'continues to Senj on the coast and to Gospić. The valley is flat '
                    'enough for easy cycling, and the Velebit slopes to the south add a '
                    'mountain backdrop.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Otočac — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Oto%C4%8Dac'},
            {'label': 'Croatian National Tourist Board', 'url': _HR},
        ],
        'latitude': 44.8689,
        'longitude': 15.2358,
    },
]
