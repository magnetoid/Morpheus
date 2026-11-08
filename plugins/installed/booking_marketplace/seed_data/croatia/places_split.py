"""Croatia seed data: places in the Split-Dalmatia region.

Real destinations around Split, Trogir and the Makarska Riviera, and on the islands of Brač,
Hvar, Vis, Biševo and Šolta. Plain, factual editorial text with no prices or opening hours;
seeded by ``manage.py seed_croatia`` (idempotent, keyed by slug).
"""

from __future__ import annotations

PLACES: list[dict] = [
    {
        'name': 'Split',
        'slug': 'split',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Promenade%2C_Split_%28P1080864%29.jpg/1280px-Promenade%2C_Split_%28P1080864%29.jpg',
            'author': 'Matti Blume',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Promenade,_Split_(P1080864).jpg',
        },
        'region': 'split',
        'place_type': 'cities',
        'featured': True,
        'summary': (
            'Croatia’s second-largest city, built in and around the Roman palace of Emperor '
            'Diocletian.'
        ),
        'description': (
            'Split grew inside and around Diocletian’s Palace, a Roman imperial residence from '
            'about AD 300 that is now a living part of the old town and a UNESCO World Heritage '
            'Site. The Riva promenade, the wooded Marjan hill and the ferry port make it the main'
            ' gateway to the central Dalmatian islands.'
        ),
        'highlights': [
            'Diocletian’s Palace and the Peristyle',
            'Cathedral of St Domnius and its bell tower',
            'The Riva waterfront promenade',
            'Marjan hill park',
            'Ferries to Brač, Hvar, Vis and Šolta',
        ],
        'overview': (
            'Split is the largest city on the Dalmatian coast and the second largest in Croatia. '
            'Its heart is Diocletian’s Palace, built around AD 300 as the retirement residence of'
            ' the Roman emperor Diocletian and inscribed on the UNESCO World Heritage List in '
            '1979. It is not a ruin: inside the walls are homes, shops, cafés and squares, so the'
            ' old town is lived in rather than roped off. The Peristyle courtyard, the cathedral '
            'dedicated to St Domnius and the vaulted cellars below the palace are the best-known '
            'parts. South of the walls the Riva promenade runs along the harbour, and to the west'
            ' the wooded Marjan hill rises above the city with paths and viewpoints. Split is '
            'also the region’s main ferry port, with boats to Brač, Hvar, Vis and Šolta.'
        ),
        'faqs': [
            {
                'q': 'Is Split worth visiting?',
                'a': (
                    'Yes. The Roman palace at the centre of the old town is a UNESCO World '
                    'Heritage Site, and the city also has a seafront promenade, a hill park and '
                    'ferries to the islands, so it works both as a destination and as a base.'
                ),
            },
            {
                'q': 'How do I get to Split?',
                'a': (
                    'Split Airport (SPU) lies northwest of the city, near Kaštela and Trogir. The'
                    ' city also has a ferry port, a bus station and a railway station, and boats '
                    'run from Split to Brač, Hvar, Vis and Šolta.'
                ),
            },
            {
                'q': 'What is there to do in Split?',
                'a': (
                    'Walk through Diocletian’s Palace and the Peristyle, climb the cathedral bell'
                    ' tower, stroll the Riva, walk up Marjan hill, and take a day trip to Trogir,'
                    ' Salona, Klis or an island.'
                ),
            },
            {
                'q': 'How long should I spend in Split?',
                'a': (
                    'One day covers the old town and the Riva. Two or three days leave time for '
                    'Marjan, the Roman site at Salona and a trip to an island.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': (
                    'May–June and September (warm sea, fewer crowds); July and August are hot and'
                    ' busy'
                ),
            },
            {'label': 'Ideal for', 'value': 'City breaks, history, island hopping'},
            {'label': 'Time needed', 'value': 'One to three days'},
            {
                'label': 'Getting there',
                'value': 'Split Airport (SPU); ferry port, bus and railway stations',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': ['city breaks', 'history lovers', 'island hopping', 'food and wine', 'walkers'],
        'latitude': 43.5081,
        'longitude': 16.4402,
        'sections': [
            {
                'heading': 'A palace that became a city',
                'body': (
                    'Diocletian had the palace built on the Dalmatian coast as a retirement home,'
                    ' and it combined a fortress, an imperial residence and temples behind walls '
                    'and towers. After the Western Roman Empire fell, people sheltered behind '
                    'those walls, and a town grew inside and around them over the following '
                    'centuries. The Roman streets, gates and towers still shape the old town '
                    'today, with later Romanesque, Gothic and Renaissance buildings set into the '
                    'older stone. The result is a city centre that is both a monument and an '
                    'ordinary neighbourhood where people live and work.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The Peristyle is the palace’s central courtyard, and off it stands the '
                    'Cathedral of St Domnius, originally built as Diocletian’s mausoleum, with a '
                    'bell tower that can be climbed for views over the roofs. Close by, the '
                    'former Temple of Jupiter survives as a baptistery. Below the palace, the '
                    'vaulted basement halls remain from the Roman building. Outside the Golden '
                    'Gate, on the north side, stands the large bronze statue of Gregory of Nin by'
                    ' the sculptor Ivan Meštrović.'
                ),
            },
            {
                'heading': 'Getting around and onward',
                'body': (
                    'The old town is compact and best seen on foot, with the Riva and the harbour'
                    ' just outside the walls. Marjan hill is a short walk west of the centre and '
                    'has paths and viewpoints over the city and the sea. From the port, ferries '
                    'and catamarans serve Brač, Hvar, Vis and Šolta. The coast and hinterland '
                    'around Split put Trogir, Salona, Klis Fortress, Omiš and the Cetina River '
                    'within a short drive, so the city works as a base for several days of day '
                    'trips.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Split — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Split,_Croatia',
            },
            {
                'label': 'Diocletian’s Palace — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Diocletian%27s_Palace',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Trogir',
        'slug': 'trogir',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Magasin_et_restaurant_%C3%A0_Trogir.jpg/1280px-Magasin_et_restaurant_%C3%A0_Trogir.jpg',
            'author': 'Sebring12Hrs',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Magasin_et_restaurant_%C3%A0_Trogir.jpg',
        },
        'region': 'split',
        'place_type': 'cultural',
        'featured': True,
        'summary': (
            'A compact UNESCO-listed old town on a small island, packed with Romanesque and '
            'Renaissance buildings.'
        ),
        'description': (
            'Trogir’s old town sits on a small island between the mainland and the island of '
            'Čiovo, joined to both by bridges. Its stone lanes, town loggia and the Cathedral of '
            'St Lawrence, with the carved portal by Master Radovan, earned it a place on the '
            'UNESCO World Heritage List in 1997.'
        ),
        'highlights': [
            'Cathedral of St Lawrence and Radovan’s Portal',
            'Kamerlengo Fortress',
            'Town Loggia and the main square',
            'Čipiko Palace',
            'The seafront promenade',
        ],
        'overview': (
            'Trogir is a small walled town on an islet in the channel between the Dalmatian '
            'mainland and Čiovo. Greek settlers founded a colony here in the 3rd century BC, and '
            'the town later passed through Roman, Croatian-Hungarian and Venetian rule, leaving a'
            ' dense core of Romanesque, Gothic and Renaissance buildings. UNESCO inscribed the '
            'historic city in 1997. The Cathedral of St Lawrence, begun in the 13th century, is '
            'the main monument, and its west portal was carved by Master Radovan. Near the sea '
            'stands the Kamerlengo Fortress, built by the Venetians in the 15th century. The old '
            'town is small enough to cross in minutes, and its lanes, squares and waterfront are '
            'best explored on foot. Split Airport is only a few kilometres away, so Trogir is '
            'often a visitor’s first or last stop in Dalmatia.'
        ),
        'faqs': [
            {
                'q': 'Is Trogir worth visiting?',
                'a': (
                    'Yes. The whole old town is a UNESCO World Heritage Site, and its cathedral, '
                    'fortress and palaces are concentrated in a small, walkable area.'
                ),
            },
            {
                'q': 'How do I get to Trogir?',
                'a': (
                    'Trogir lies about 25 km west of Split along the coast road, and Split '
                    'Airport (SPU) is only a few kilometres away. Buses connect the town with '
                    'Split, and a bridge links the old town to the mainland.'
                ),
            },
            {
                'q': 'What is there to do in Trogir?',
                'a': (
                    'Visit the Cathedral of St Lawrence and see Radovan’s Portal, walk around the'
                    ' Kamerlengo Fortress, wander the old lanes and the loggia square, and stroll'
                    ' the waterfront promenade.'
                ),
            },
            {
                'q': 'How long should I spend in Trogir?',
                'a': (
                    'Half a day is enough for the old town. An overnight stay lets you see it '
                    'when the day trippers have gone.'
                ),
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September–October'},
            {'label': 'Ideal for', 'value': 'History, architecture, short breaks'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {
                'label': 'Getting there',
                'value': 'About 25 km west of Split by road; Split Airport (SPU) nearby',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {
                'label': 'Nearest airport',
                'value': 'Split Airport (SPU), a few kilometres away',
            },
        ],
        'good_for': [
            'history lovers',
            'architecture',
            'short breaks',
            'photographers',
            'day trips',
        ],
        'latitude': 43.5167,
        'longitude': 16.2517,
        'sections': [
            {
                'heading': 'A town on an island',
                'body': (
                    'The old town fills a small island in the channel between the mainland and '
                    'Čiovo, which gave it a natural defence and a sheltered harbour. According to'
                    ' ancient sources, Greek settlers from the island of Vis founded the colony '
                    'of Tragurion here in the 3rd century BC. Over later centuries the town was '
                    'rebuilt and enlarged, and the street grid seen today dates mostly from the '
                    'medieval and Venetian periods. Walking its lanes, you pass Gothic windows '
                    'and Renaissance doorways within a few minutes of each other.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The Cathedral of St Lawrence, whose construction ran from the 13th century '
                    'onwards, has a Romanesque portal carved by Master Radovan, and a bell tower '
                    'that can be climbed for a view over the roofs and the channel. Nearby are '
                    'the town loggia, the town hall and the Čipiko Palace. At the western end of '
                    'the waterfront the Kamerlengo Fortress, built by the Venetians in the 15th '
                    'century, guards the harbour. All of these stand within a few minutes’ walk '
                    'of each other.'
                ),
            },
            {
                'heading': 'Around Trogir',
                'body': (
                    'Čiovo island, reached by a short bridge, has quiet coves and villages, and '
                    'the Bay of Kaštela with its seven small towns starts just east of Trogir. '
                    'Split, Salona and Klis Fortress are all within about half an hour’s drive, '
                    'so Trogir can be a base as well as a day trip. The waterfront promenade '
                    'along the channel is the usual place to walk in the evening, when the old '
                    'town is quieter.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Trogir — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Trogir'},
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Kaštela',
        'slug': 'kastela',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Split_mountains_%2820785899568%29.jpg/1280px-Split_mountains_%2820785899568%29.jpg',
            'author': 'Nick Savchenko from Kiev, Ukraine',
            'licence': 'CC BY-SA 2.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/2.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Split_mountains_(20785899568).jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'Seven small seaside towns on a bay between Split and Trogir, each grown around an '
            'old fortified manor.'
        ),
        'description': (
            'Kaštela is a coastal municipality of seven settlements, Kaštel Sućurac, Gomilica, '
            'Kambelovac, Lukšić, Stari, Novi and Štafilić, strung along a bay between Split and '
            'Trogir. Each grew around a kaštel, a fortified house built by local nobles in the '
            '15th and 16th centuries, and Split Airport lies within the municipality.'
        ),
        'highlights': [
            'Kaštel Gomilica’s castle on its islet',
            'The Vitturi castle in Kaštel Lukšić',
            'Old fortified houses in each of the seven settlements',
            'Seafront promenades along the bay',
            'Pebble beaches and short trips to Split and Trogir',
        ],
        'overview': (
            'The Bay of Kaštela runs between Split and Trogir, and its shore holds seven small '
            'settlements: Kaštel Sućurac, Gomilica, Kambelovac, Lukšić, Stari, Novi and Štafilić.'
            ' The name comes from the kaštels, fortified houses that local nobles and landowners '
            'built from the 15th century, partly as refuges against Ottoman raids. Most stand '
            'right on the water, and the best known include the castle of Kaštel Gomilica, on a '
            'small islet joined to the shore, and the Vitturi castle in Kaštel Lukšić. Behind the'
            ' towns the slopes of Kozjak rise above olive groves and vineyards. Today the '
            'settlements are mainly residential, with promenades, small harbours and pebble '
            'beaches, and Split Airport (SPU) is within the municipality, which makes Kaštela a '
            'practical base for reaching both Split and Trogir.'
        ),
        'faqs': [
            {
                'q': 'Is Kaštela worth visiting?',
                'a': (
                    'It suits travellers who want a quieter stretch of coast close to Split and '
                    'Trogir. The old kaštels, seafront promenades and pebble beaches are the main'
                    ' draws.'
                ),
            },
            {
                'q': 'How do I get to Kaštela?',
                'a': (
                    'Split Airport (SPU) is in the municipality, and the coast road and local '
                    'buses link the seven settlements with Split and Trogir. The distances to '
                    'either city are short.'
                ),
            },
            {
                'q': 'What is there to do in Kaštela?',
                'a': (
                    'See the castles of Kaštel Gomilica and Kaštel Lukšić, walk the seafront, '
                    'swim from the pebble beaches, and use the towns as a base for day trips to '
                    'Split, Trogir and Klis.'
                ),
            },
            {
                'q': 'How long should I spend in Kaštela?',
                'a': (
                    'A half-day walk covers the main castles. Many visitors stay several nights '
                    'and travel out from here.'
                ),
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September'},
            {'label': 'Ideal for', 'value': 'Quiet coast, base near Split and Trogir'},
            {'label': 'Time needed', 'value': 'Half a day, or a longer stay'},
            {
                'label': 'Getting there',
                'value': 'Between Split and Trogir; Split Airport (SPU) is in the municipality',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), within Kaštela'},
        ],
        'good_for': ['quiet coast', 'families', 'castles', 'base near the airport', 'walkers'],
        'latitude': 43.55,
        'longitude': 16.34,
        'sections': [
            {
                'heading': 'Seven towns, one bay',
                'body': (
                    'The seven settlements stand along the northern shore of the bay, and in '
                    'older times each was a separate village under the protection of its own '
                    'fortified house. Together they now form the municipality of Kaštela. Between'
                    ' the shore and the Kozjak hills lie olive groves, vineyards and small farms,'
                    ' and the coast road links the settlements with Split and Trogir. Each town '
                    'has its own harbour or beach, so you can move from one to the next by car, '
                    'bus or bicycle in a short time.'
                ),
            },
            {
                'heading': 'The kaštels',
                'body': (
                    'The kaštels were built by noble families and landowners from the 15th '
                    'century as fortified residences and refuges, usually on or next to the '
                    'water. Kaštel Gomilica’s castle stands on a small islet joined to the shore,'
                    ' and the Vitturi castle in Kaštel Lukšić is one of the best known in the '
                    'bay. Many have been altered over the centuries, and some are private homes, '
                    'so check locally which can be entered before you set out.'
                ),
            },
            {
                'heading': 'Using Kaštela as a base',
                'body': (
                    'With the airport in the municipality, Kaštela is convenient for a first or '
                    'last night. Trogir is a short drive west and Split a short drive east. Klis '
                    'Fortress and the Roman site of Salona are also close by. The towns are '
                    'mainly residential, so they are quieter than the cities at either end of the'
                    ' bay, and walking along the shore is the simplest way to see the castles one'
                    ' after another.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Kaštela — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Ka%C5%A1tela',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Klis Fortress',
        'slug': 'klis-fortress',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Fortress_of_Klis_05.jpg/1280px-Fortress_of_Klis_05.jpg',
            'author': 'Bernard Gagnon',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Fortress_of_Klis_05.jpg',
        },
        'region': 'split',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A hilltop fortress on a mountain pass above Split, guarding the road between the '
            'coast and the interior.'
        ),
        'description': (
            'Klis Fortress stands on a rocky ridge above the village of Klis, about 10 km from '
            'Split, where a pass runs between the Mosor and Kozjak mountains. It has been '
            'fortified since antiquity, held by Croatian rulers, and fell to the Ottomans in '
            '1537.'
        ),
        'highlights': [
            'Views over Split, Solin and the islands',
            'The upper and lower fortress walls',
            'The history of the defence against the Ottomans',
            'The Klis pass and the village below',
            'Filming location for the TV series Game of Thrones',
        ],
        'overview': (
            'Klis Fortress sits on a long rocky ridge above the village of Klis, about 10 km from'
            ' Split. The ridge overlooks a narrow pass between Mosor and Kozjak, a natural route '
            'between the Dalmatian coast and the interior, which is why the site has been '
            'fortified for so long, from ancient times through the medieval Croatian kingdom. In '
            'the 16th century it was a key stronghold against the Ottomans, under the captain '
            'Petar Kružić, until it fell in 1537. Venice took it in 1648. Today visitors walk '
            'through successive gates and courtyards to the top, where the view stretches over '
            'Split, the Bay of Kaštela and the nearby islands. Parts of the series Game of '
            'Thrones were filmed here, and the fortress stood in for the city of Meereen.'
        ),
        'faqs': [
            {
                'q': 'Is Klis Fortress worth visiting?',
                'a': (
                    'Yes, for the history and the view. The fortress is close to Split and gives '
                    'a clear picture of why the pass was fought over for centuries.'
                ),
            },
            {
                'q': 'How do I get to Klis Fortress?',
                'a': (
                    'It is about 10 km northeast of Split and can be reached by road in around 20'
                    ' minutes, or by local bus from Split to the village of Klis. Split Airport '
                    '(SPU) is also close.'
                ),
            },
            {
                'q': 'What is there to do at Klis Fortress?',
                'a': (
                    'Walk through the gates and courtyards up to the highest point, take in the '
                    'view over the coast, and read about the siege of 1537 and the later history '
                    'of the site.'
                ),
            },
            {
                'q': 'How long should I spend at Klis Fortress?',
                'a': (
                    'Plan about one to two hours on site, or half a day if you combine it with '
                    'Salona and the village of Klis.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and autumn for walking; summer can be hot on the open ridge',
            },
            {'label': 'Ideal for', 'value': 'History, views, film fans'},
            {'label': 'Time needed', 'value': 'One to two hours'},
            {'label': 'Getting there', 'value': 'About 10 km northeast of Split by road'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'history lovers',
            'views',
            'film fans',
            'short trips from Split',
            'photographers',
        ],
        'latitude': 43.5608,
        'longitude': 16.5236,
        'sections': [
            {
                'heading': 'A pass worth defending',
                'body': (
                    'The pass between Mosor and Kozjak is one of the main routes from the coast '
                    'into the interior, and whoever held the ridge above it controlled movement '
                    'between the two. The site was fortified in antiquity and later used by '
                    'medieval Croatian rulers, and the walls seen today grew over many centuries,'
                    ' with later work by the Venetians. The fortress is made up of several levels'
                    ' of walls and courtyards that follow the shape of the rock, which is why it '
                    'looks so much a part of the ridge.'
                ),
            },
            {
                'heading': 'The siege of 1537',
                'body': (
                    'In the 16th century the fortress was a key defence against the Ottoman '
                    'advance. Its captain, Petar Kružić, led the defenders until he was killed in'
                    ' 1537, and the fortress then fell to the Ottomans. It remained in Ottoman '
                    'hands until the Venetians captured it in 1648. The story is told in the '
                    'displays on site, and the ridge itself explains much of it: the walls look '
                    'down on every approach from the coast.'
                ),
            },
            {
                'heading': 'Visiting',
                'body': (
                    'The walk climbs through several gates and courtyards to the highest part of '
                    'the ridge, where the view takes in Split, Solin and the sea. Wear sturdy '
                    'shoes, as the paths are stone and can be uneven, and bring water in warm '
                    'months because shade is limited. The ruins of Salona are nearby and fit well'
                    ' into the same trip, and the village of Klis below the fortress is close to '
                    'Split by road.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Klis Fortress — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Klis_Fortress',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Salona',
        'slug': 'salona',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Salona_-_Porta_Cesarea.jpg/1280px-Salona_-_Porta_Cesarea.jpg',
            'author': 'Pudelek (Marcin Szala)',
            'licence': 'CC BY-SA 3.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Salona_-_Porta_Cesarea.jpg',
        },
        'region': 'split',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'The remains of a major Roman city at Solin, just outside Split, with an amphitheatre'
            ' and early Christian sites.'
        ),
        'description': (
            'Salona was a major Roman city and the capital of the province of Dalmatia, and its '
            'ruins lie at Solin, a few kilometres from Split. The site includes an amphitheatre, '
            'city walls, baths and early Christian churches and cemeteries.'
        ),
        'highlights': [
            'The Roman amphitheatre',
            'Manastirine early Christian cemetery and basilica',
            'The city walls and gates',
            'The Tusculum museum',
            'Remains of the forum and the baths',
        ],
        'overview': (
            'Salona lies at Solin, a short distance northeast of Split, and was once the capital '
            'of the Roman province of Dalmatia. The emperor Diocletian is believed to have been '
            'born in the area, and he later built his palace at nearby Split. The city grew large'
            ' under Rome and became an important early Christian centre, with a bishop and '
            'several basilicas. It was abandoned in the early 7th century, when invaders attacked'
            ' it, and people moved to the safer coast and settled in the ruins of the palace, '
            'from which Split grew. Today the archaeological reserve contains the foundations of '
            'the forum and baths, stretches of the city walls with their gates, the amphitheatre,'
            ' and the early Christian burial ground at Manastirine. The Tusculum, a house beside '
            'the site, was linked to the archaeologist Frane Bulić. Salona is open-air, so it is '
            'best visited in good weather.'
        ),
        'faqs': [
            {
                'q': 'Is Salona worth visiting?',
                'a': (
                    'Yes, if you are interested in Roman and early Christian history. It is one '
                    'of the major Roman sites in Croatia and is very close to Split.'
                ),
            },
            {
                'q': 'How do I get to Salona?',
                'a': (
                    'Salona is at Solin, a few kilometres northeast of Split, and is reached by '
                    'city bus or a short drive. Split Airport (SPU) is also close.'
                ),
            },
            {
                'q': 'What is there to see at Salona?',
                'a': (
                    'The amphitheatre, the city walls and gates, the remains of the forum and '
                    'baths, and the early Christian cemetery and basilica at Manastirine.'
                ),
            },
            {
                'q': 'How long should I spend at Salona?',
                'a': (
                    'About one to two hours for a visit on foot. Combine it with Diocletian’s '
                    'Palace in Split to see how the two are linked.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and autumn; summer is hot and shade is limited',
            },
            {'label': 'Ideal for', 'value': 'Archaeology, history'},
            {'label': 'Time needed', 'value': 'One to two hours'},
            {
                'label': 'Getting there',
                'value': 'A few kilometres northeast of Split, at Solin',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'archaeology',
            'history lovers',
            'early Christian sites',
            'short trips from Split',
            'families with older children',
        ],
        'latitude': 43.5394,
        'longitude': 16.4833,
        'sections': [
            {
                'heading': 'The capital of a province',
                'body': (
                    'Under the Romans, Salona was the main city of the province of Dalmatia, with'
                    ' a forum, baths, a theatre and an amphitheatre. It also had a port on the '
                    'bay, and roads linked it to the interior. The city declined in the early 7th'
                    ' century, when it was attacked and abandoned, and many of its people moved '
                    'to safer places on the coast. Walking the site today, you cross the line of '
                    'the old city walls and pass the gates that once controlled the main roads.'
                ),
            },
            {
                'heading': 'Early Christian Salona',
                'body': (
                    'Salona was an important centre of early Christianity in the region, with a '
                    'bishop and several churches. The cemetery at Manastirine holds the remains '
                    'of a basilica and early Christian graves, and further churches and a '
                    'baptistery have been excavated within the city. The amphitheatre, built in '
                    'the Roman period, was partly dismantled by the Venetians in the 17th century'
                    ' to keep it from use by an attacker, and its lower walls can still be '
                    'walked.'
                ),
            },
            {
                'heading': 'From Salona to Split',
                'body': (
                    'After Salona was abandoned, many of its people settled in Diocletian’s '
                    'Palace nearby, and the town of Split grew around it. A visit to both sites '
                    'in one day makes the link clear. Wear comfortable shoes, as the site is open'
                    ' air and the ground is uneven, and bring water and sun protection in summer.'
                    ' The Tusculum, a house beside the site, is tied to the archaeologist Frane '
                    'Bulić, who worked here, and the Klis Fortress is a short drive away.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Salona — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Salona'},
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Omiš',
        'slug': 'omis',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/Omis_fortice_Starigrad.jpg/1280px-Omis_fortice_Starigrad.jpg',
            'author': 'Larisa Uhryn',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Omis_fortice_Starigrad.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small town at the mouth of the Cetina River, framed by steep cliffs and old '
            'fortresses.'
        ),
        'description': (
            'Omiš sits where the Cetina River breaks through a gorge to reach the Adriatic, about'
            ' 25 km southeast of Split. Cliffs rise right behind the old town, topped by the '
            'Mirabela and Starigrad fortresses, and the river canyon is a base for rafting and '
            'walks.'
        ),
        'highlights': [
            'Mirabela (Peovica) Fortress',
            'Starigrad (Fortica) Fortress above the town',
            'The mouth of the Cetina River',
            'Omiš town beach',
            'Rafting and canyoning on the Cetina',
        ],
        'overview': (
            'Omiš lies about 25 km southeast of Split, at the point where the Cetina River leaves'
            ' its canyon and flows into the sea. Steep limestone cliffs rise directly behind the '
            'old town, and two fortresses sit on them: Mirabela, known locally as Peovica, and '
            'Starigrad, also called Fortica, which stands on the hill above the town. In the '
            'Middle Ages Omiš was known for its corsairs, who used the narrow river mouth and the'
            ' cliffs as a base. The old town is a small group of stone houses, lanes and a main '
            'square. The town beach, called Punta, is at the river mouth, and there are other '
            'pebble beaches along the coast. The Cetina canyon upriver offers rafting, canyoning '
            'and walking, and Omiš is the usual starting point for those trips.'
        ),
        'faqs': [
            {
                'q': 'Is Omiš worth visiting?',
                'a': (
                    'Yes. The setting between cliffs and sea is unusual for the coast, and the '
                    'town combines fortresses, a river mouth and outdoor activities.'
                ),
            },
            {
                'q': 'How do I get to Omiš?',
                'a': (
                    'Omiš is about 25 km southeast of Split on the coast road, and buses run '
                    'between the two. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Omiš?',
                'a': (
                    'Climb to the Mirabela or Starigrad fortress, walk the old town, swim at the '
                    'town beach, and take a rafting or canyoning trip on the Cetina.'
                ),
            },
            {
                'q': 'How long should I spend in Omiš?',
                'a': (
                    'Half a day covers the town and a fortress. Add a day if you want to raft or '
                    'hike the canyon.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–June and September for outdoor activities',
            },
            {'label': 'Ideal for', 'value': 'Outdoors, history, short coastal stays'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'About 25 km southeast of Split by road'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'outdoor activities',
            'rafting',
            'history lovers',
            'photographers',
            'day trips from Split',
        ],
        'latitude': 43.4444,
        'longitude': 16.6872,
        'sections': [
            {
                'heading': 'Town between river and cliff',
                'body': (
                    'Omiš is a compact town on a narrow strip between the sea and a wall of rock.'
                    ' The Cetina meets the Adriatic here after running through a deep gorge, and '
                    'the river mouth shapes the town’s beach and harbour. The setting also made '
                    'Omiš easy to defend, which explains the fortresses on the cliffs above. In '
                    'the Middle Ages the town was known for its corsairs, who used the river '
                    'mouth as a base, and that history is part of how locals tell the story of '
                    'the place today.'
                ),
            },
            {
                'heading': 'The fortresses',
                'body': (
                    'Mirabela, or Peovica, is a small fortress on a rocky spur right above the '
                    'old town and is reached by a short, steep climb. Starigrad, or Fortica, '
                    'stands higher on the hill behind the town and gives a wide view of the '
                    'coast, the islands and the river mouth. Both are medieval in origin. Wear '
                    'good shoes for the climbs, and take water, because the paths are exposed and'
                    ' the stone is hot in summer.'
                ),
            },
            {
                'heading': 'The Cetina canyon',
                'body': (
                    'Upstream from Omiš, the Cetina runs through a canyon with steep walls. Local'
                    ' operators run rafting, kayaking and canyoning trips here, and there are '
                    'walking routes along the sides of the gorge. Water levels vary with the '
                    'season and with releases from the dams upriver, so book with a licensed '
                    'operator and ask about conditions on the day. For more, see the Cetina River'
                    ' entry.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Omiš — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Omi%C5%A1',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Cetina River',
        'slug': 'cetina-river',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Cetina_%28HR%29%2C_Quelle_%22Blue_Eye%22_und_Dinara_--_2022_--_0042.jpg/1280px-Cetina_%28HR%29%2C_Quelle_%22Blue_Eye%22_und_Dinara_--_2022_--_0042.jpg',
            'author': 'Anil Öztas',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Cetina_(HR),_Quelle_%22Blue_Eye%22_und_Dinara_--_2022_--_0042.jpg',
        },
        'region': 'split',
        'place_type': 'lakes',
        'featured': False,
        'summary': (
            'A karst river of about 100 km that rises in the Dinara foothills and reaches the sea'
            ' through a canyon at Omiš.'
        ),
        'description': (
            'The Cetina rises at the foot of the Dinara mountains and flows southwest through the'
            ' Cetina valley, past Sinj, to the Adriatic at Omiš. Its lower course runs through a '
            'canyon used for rafting, canyoning and walks, and its waters are dammed in places '
            'for power.'
        ),
        'highlights': [
            'The Cetina canyon above Omiš',
            'Rafting and kayaking',
            'Radmanove Mlinice and its old mills',
            'Peruća reservoir',
            'The river mouth at Omiš',
        ],
        'overview': (
            'The Cetina is one of the main rivers of Dalmatia, about 100 km long. It rises at the'
            ' foot of the Dinara range, flows through the Cetina valley past the town of Sinj, '
            'and passes through the Peruća reservoir, one of several places where it is dammed '
            'for hydroelectric power. In its lower course the river cuts a canyon with steep '
            'walls before it reaches the Adriatic at Omiš. The canyon is the part most visitors '
            'come for: rafting, kayaking and canyoning trips start near Omiš, and walkers follow '
            'paths along the gorge. Upstream near Zadvarje, the old water mills of Radmanove '
            'Mlinice stand beside the river and a waterfall. Water levels and conditions change '
            'with the season and with the hydroelectric releases, so activities should be booked '
            'with a local operator and checked on the day.'
        ),
        'faqs': [
            {
                'q': 'Is the Cetina River worth visiting?',
                'a': (
                    'Yes, if you like outdoor activities or river scenery. The canyon near Omiš '
                    'is the main draw.'
                ),
            },
            {
                'q': 'How do I get to the Cetina River?',
                'a': (
                    'The lower canyon starts at Omiš, about 25 km southeast of Split by road. '
                    'Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do on the Cetina River?',
                'a': (
                    'Go rafting, kayaking or canyoning, hike along the gorge, and visit the old '
                    'mills at Radmanove Mlinice.'
                ),
            },
            {
                'q': 'How long should I spend on the Cetina River?',
                'a': (
                    'A rafting trip takes a few hours, and a full day lets you combine it with '
                    'Omiš.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn for water activities',
            },
            {'label': 'Ideal for', 'value': 'Rafting, outdoors, scenery'},
            {'label': 'Time needed', 'value': 'A few hours to a day'},
            {'label': 'Getting there', 'value': 'Omiš is about 25 km southeast of Split'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'rafting',
            'outdoor activities',
            'scenery',
            'adventure',
            'day trips from Split',
        ],
        'latitude': 43.447,
        'longitude': 16.7,
        'sections': [
            {
                'heading': 'From the Dinara to the sea',
                'body': (
                    'The river’s source lies at the foot of the Dinara mountains. It flows across'
                    ' the karst plateau of the Cetina valley, past Sinj, through the Peruća '
                    'reservoir and a series of dams, and finally into the canyon near the coast. '
                    'Along the way it supplies hydroelectric power and irrigates fields in the '
                    'valley. The river is about 100 km long and is one of the main rivers of '
                    'Dalmatia, even though it passes through dry limestone country for much of '
                    'its course.'
                ),
            },
            {
                'heading': 'The lower canyon',
                'body': (
                    'Below the last dam the Cetina falls toward the sea through a canyon with '
                    'limestone walls on either side. Operators in Omiš run rafting, kayaking and '
                    'canyoning here, and a path follows part of the gorge. The mouth of the river'
                    ' at Omiš is the town’s beach and harbour. Upstream near Zadvarje, the old '
                    'mills of Radmanove Mlinice stand beside the river and a small waterfall, and'
                    ' are a quiet place to stop.'
                ),
            },
            {
                'heading': 'Safety and planning',
                'body': (
                    'The river’s flow depends on rainfall and on releases from the dams, so '
                    'conditions can differ from day to day. Use licensed local operators for any '
                    'water activity, listen to their instructions, and bring swimwear, a towel '
                    'and shoes you can get wet. Start early in summer, when the canyon is hot by '
                    'midday, and check the weather first, since heavy rain upstream changes the '
                    'water quickly.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Makarska',
        'slug': 'makarska',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Urbanisti%C4%8Dka_cjelina_Makarske.jpg/1280px-Urbanisti%C4%8Dka_cjelina_Makarske.jpg',
            'author': 'SKas',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Urbanisti%C4%8Dka_cjelina_Makarske.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'The main town of the Makarska Riviera, with a pebble beach, a harbour and the '
            'Biokovo mountain wall behind.'
        ),
        'description': (
            'Makarska is the centre of the Makarska Riviera, a stretch of coast about 60 km '
            'southeast of Split. A bay with a long pebble beach and the wooded Sveti Petar '
            'peninsula lie in front, and the steep Biokovo mountain rises directly behind.'
        ),
        'highlights': [
            'Kačić Square and the old town',
            'The Franciscan monastery and its shell museum',
            'The Sveti Petar peninsula',
            'The seafront promenade',
            'Biokovo Nature Park above the town',
        ],
        'overview': (
            'Makarska is the largest town on the Makarska Riviera, a strip of coast between the '
            'sea and the limestone wall of Biokovo, about 60 km southeast of Split. The town is '
            'built around a sheltered bay: the harbour and the main square, Kačić Square, are at '
            'the centre, a pebble beach runs along the front, and the Sveti Petar peninsula with '
            'its pine woods closes the bay on the west. The Franciscan monastery on the seafront '
            'houses a museum devoted to sea shells. Behind the town, Biokovo Nature Park offers '
            'walks and viewpoints, and Makarska is also a port: a ferry crosses to Sumartin on '
            'the island of Brač. The town works as a base for the whole riviera, with Brela, '
            'Baška Voda and Tučepi all nearby. In summer the promenade and beaches are busy, and '
            'the evenings are lively.'
        ),
        'faqs': [
            {
                'q': 'Is Makarska worth visiting?',
                'a': (
                    'Yes, for its beaches and its setting between the sea and Biokovo. It is a '
                    'lively base for swimming, walking and day trips.'
                ),
            },
            {
                'q': 'How do I get to Makarska?',
                'a': (
                    'Makarska is about 60 km southeast of Split by road, and buses connect the '
                    'two. Split Airport (SPU) is the nearest airport. A ferry also links Makarska'
                    ' with Sumartin on Brač.'
                ),
            },
            {
                'q': 'What is there to do in Makarska?',
                'a': (
                    'Walk the seafront and the Sveti Petar peninsula, visit the Franciscan '
                    'monastery’s shell museum, swim from the beaches, and go hiking in Biokovo '
                    'Nature Park.'
                ),
            },
            {
                'q': 'How long should I spend in Makarska?',
                'a': (
                    'A day covers the town. Many visitors stay several days to use it as a base '
                    'for the riviera and Biokovo.'
                ),
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September'},
            {'label': 'Ideal for', 'value': 'Beaches, walking, a base for the riviera'},
            {'label': 'Time needed', 'value': 'A day to several days'},
            {
                'label': 'Getting there',
                'value': 'About 60 km southeast of Split; ferry from Sumartin (Brač)',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'beach holidays',
            'walkers',
            'families',
            'base for the riviera',
            'island hopping',
        ],
        'latitude': 43.2969,
        'longitude': 17.0178,
        'sections': [
            {
                'heading': 'A town in a bay',
                'body': (
                    'Makarska sits on a bay that is sheltered by the Sveti Petar peninsula, with '
                    'the Biokovo range directly behind. The old centre is small and gathers '
                    'around Kačić Square, which is named after Andrija Kačić Miošić, a Franciscan'
                    ' friar and writer from the area. The harbour and promenade run along the '
                    'front, with cafés and restaurants facing the water, and the town’s churches '
                    'and a museum stand within a few streets of the square.'
                ),
            },
            {
                'heading': 'Sights and the sea',
                'body': (
                    'The Franciscan monastery on the seafront holds a museum with a collection of'
                    ' shells. The beach at the centre is pebble, and the pine woods on Sveti '
                    'Petar offer shade and paths along the water. Other pebble coves stretch '
                    'along the riviera northwest and southeast of the town. The promenade is the '
                    'usual evening walk, and the harbour is the place to find boats and boat '
                    'trips in season.'
                ),
            },
            {
                'heading': 'Biokovo and the islands',
                'body': (
                    'The mountain above Makarska is a nature park with paths and a road to the '
                    'viewpoints. A ferry runs from Makarska to Sumartin on the island of Brač, '
                    'and boats from the area serve other islands in season. Brela, Baška Voda and'
                    ' Tučepi are on the same coast, and the coast road and buses link them all '
                    'with Split, about 60 km to the northwest, so day trips in either direction '
                    'are easy.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Makarska — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Makarska',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Brela',
        'slug': 'brela',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Brela_BW_2024-10-04_16-08-03.jpg/1280px-Brela_BW_2024-10-04_16-08-03.jpg',
            'author': 'Berthold Werner',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Brela_BW_2024-10-04_16-08-03.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small resort on the northwest end of the Makarska Riviera, known for its pine-'
            'backed pebble beaches.'
        ),
        'description': (
            'Brela lies at the northwest end of the Makarska Riviera, with a long series of '
            'pebble beaches backed by pine trees and the Biokovo slopes rising behind. Punta Rata'
            ' is its best-known beach.'
        ),
        'highlights': [
            'Punta Rata beach',
            'Pine-shaded coves and paths',
            'The seafront promenade',
            'The slopes of Biokovo behind',
            'Makarska and Baška Voda nearby',
        ],
        'overview': (
            'Brela is a small village on the Makarska Riviera, northwest of Makarska, with a long'
            ' run of pebble coves shaded by pines and a clear sea. Its best-known beach is Punta '
            'Rata, a cape with a pebble shore and pine trees. A seafront path links the coves, '
            'and above the village the slopes of Biokovo rise behind olive groves and scrub. '
            'Brela is quieter than Makarska and has little in the way of monuments; it is mostly '
            'a place to swim, walk along the shore, and rest. Baška Voda lies a short way '
            'southeast along the coast and Makarska a little further on. The nearest airport is '
            'Split Airport (SPU), and the coast road links Brela with Split. Pine trees shade '
            'much of the shore, the sea is clear, and the coves are easy to reach on foot from '
            'the village.'
        ),
        'faqs': [
            {
                'q': 'Is Brela worth visiting?',
                'a': (
                    'Yes, if you want a quiet pebble-beach stay on the Makarska Riviera. Its '
                    'beaches, pines and clear water are its main attraction.'
                ),
            },
            {
                'q': 'How do I get to Brela?',
                'a': (
                    'Brela lies on the coast road northwest of Makarska, and buses between Split '
                    'and Makarska stop there. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Brela?',
                'a': (
                    'Swim at Punta Rata and the other coves, walk the seafront path, and make '
                    'trips to Makarska, Baška Voda or up into Biokovo.'
                ),
            },
            {
                'q': 'How long should I spend in Brela?',
                'a': (
                    'A day is enough for the beaches. Many visitors stay for several days of '
                    'beach time.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June to September for swimming; May and September are quieter',
            },
            {'label': 'Ideal for', 'value': 'Beach holidays, rest'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {'label': 'Getting there', 'value': 'On the coast road northwest of Makarska'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': ['beach holidays', 'families', 'quiet stays', 'walkers', 'swimmers'],
        'latitude': 43.3642,
        'longitude': 16.9211,
        'sections': [
            {
                'heading': 'A coast of pebbles and pines',
                'body': (
                    'Brela’s shore is a series of coves with pebbles and pine trees that grow '
                    'close to the water. A path follows the shore from cove to cove, and the '
                    'village itself is small and scattered along the hillside, with stone houses '
                    'among the trees. The sea is clear, and the coves are separated by low rocky '
                    'points, so you can walk from one beach to the next in a few minutes and '
                    'choose the one with the most shade or the fewest people.'
                ),
            },
            {
                'heading': 'Punta Rata',
                'body': (
                    'Punta Rata is a pebble beach on a headland with pine trees behind it and is '
                    'the beach most associated with Brela. It is popular in summer, so arriving '
                    'early helps. Other coves along the shore are less busy. Water shoes are '
                    'useful on the pebbles and on the rocks at the edges of the coves, and the '
                    'pines give natural shade for much of the day, which suits families with '
                    'young children.'
                ),
            },
            {
                'heading': 'Around Brela',
                'body': (
                    'Baška Voda is a short way southeast, and Makarska is further along the '
                    'riviera. The slopes of Biokovo behind Brela hold walking routes, and the '
                    'park’s higher paths are reached from Makarska or other points on the coast. '
                    'The coast road and buses link Brela with Split, so a day in the city is '
                    'possible, although most visitors come here to stay by the sea for several '
                    'days.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Brela — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Brela'},
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Baška Voda',
        'slug': 'baska-voda',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Baska_Voda-mountain.jpg/1280px-Baska_Voda-mountain.jpg',
            'author': 'László Szalai ( Beyond silence )',
            'licence': 'Public domain',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Baska_Voda-mountain.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small seaside town on the Makarska Riviera with a long pebble promenade and '
            'Biokovo behind.'
        ),
        'description': (
            'Baška Voda lies between Brela and Makarska on the Makarska Riviera. A promenade runs'
            ' along its pebble shore, and the Biokovo mountain wall rises behind the village.'
        ),
        'highlights': [
            'The seafront promenade',
            'Pebble beaches along the shore',
            'Views of Biokovo',
            'Brela to the northwest',
            'Makarska to the southeast',
        ],
        'overview': (
            'Baška Voda is a small town on the Makarska Riviera, between Brela and Makarska. A '
            'promenade follows its pebble shore, with cafés and small restaurants along the '
            'front, and pine trees shade parts of the coast. Behind the town the mountain wall of'
            ' Biokovo rises steeply. The town is mostly a place for beach holidays and gentle '
            'walks: there are few major monuments, but the setting is close to the sea and the '
            'mountains at once. Brela is a short distance northwest and Makarska a little further'
            ' southeast, and local buses and the coast road link all three with Split. Split '
            'Airport (SPU) is the nearest airport. Boats and ferries from the riviera serve the '
            'nearby islands in season. Cafés and restaurants line the promenade, and a walk in '
            'either direction leads to quieter coves.'
        ),
        'faqs': [
            {
                'q': 'Is Baška Voda worth visiting?',
                'a': (
                    'It suits visitors who want a relaxed beach stay on the Makarska Riviera, '
                    'with Brela and Makarska nearby.'
                ),
            },
            {
                'q': 'How do I get to Baška Voda?',
                'a': (
                    'Baška Voda lies on the coast road between Brela and Makarska, and buses on '
                    'the Split–Makarska route stop there. Split Airport (SPU) is the nearest '
                    'airport.'
                ),
            },
            {
                'q': 'What is there to do in Baška Voda?',
                'a': (
                    'Swim from the pebble beaches, walk the seafront promenade, and visit Brela '
                    'and Makarska along the coast.'
                ),
            },
            {
                'q': 'How long should I spend in Baška Voda?',
                'a': 'A day for the beaches, or a longer stay as a base on the riviera.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June to September for swimming; May and September are quieter',
            },
            {'label': 'Ideal for', 'value': 'Beach holidays'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {
                'label': 'Getting there',
                'value': 'On the coast road between Brela and Makarska',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'beach holidays',
            'families',
            'walkers',
            'quiet stays',
            'base for the riviera',
        ],
        'latitude': 43.3578,
        'longitude': 16.9533,
        'sections': [
            {
                'heading': 'A town on the riviera',
                'body': (
                    'Baška Voda is one of the string of coastal villages that make up the '
                    'Makarska Riviera, with Biokovo rising directly behind. Its shore is pebble, '
                    'and a promenade links the beaches with the centre. The town is larger than '
                    'Brela and smaller than Makarska, and its mix of small shops, cafés and '
                    'beaches makes it a practical base for a holiday on this stretch of coast '
                    'without a car.'
                ),
            },
            {
                'heading': 'The shore and promenade',
                'body': (
                    'The seafront path is the main thoroughfare and carries cafés and '
                    'restaurants. The water is clear, and pine trees give shade in places along '
                    'the coast. Quieter coves lie outside the centre, and a walk along the shore '
                    'in either direction brings you to smaller beaches. Water shoes help on the '
                    'pebbles, and the promenade is the place to watch the sunset over the sea and'
                    ' the islands.'
                ),
            },
            {
                'heading': 'Around Baška Voda',
                'body': (
                    'Brela is a short drive or walk northwest, and Makarska lies further '
                    'southeast. The Biokovo slopes above the village can be reached on foot or by'
                    ' road, and the park’s main access points are near Makarska. Buses on the '
                    'coast road link Baška Voda with Split and Makarska, and boats from the '
                    'riviera reach the nearby islands in season, which makes day trips easy to '
                    'arrange.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Baška Voda — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Ba%C5%A1ka_Voda',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Tučepi',
        'slug': 'tucepi',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/8/88/Tu%C4%8Depi_II.jpg',
            'author': 'Nikolaj Potanin',
            'licence': 'CC BY-SA 2.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/2.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Tu%C4%8Depi_II.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A village on the Makarska Riviera with a long pebble beach, a short drive from '
            'Makarska.'
        ),
        'description': (
            'Tučepi lies just southeast of Makarska, on a long pebble beach below the slopes of '
            'Biokovo. It is a quiet base for swimming and walking, with Makarska a few kilometres'
            ' along the coast and Podgora next in the other direction.'
        ),
        'highlights': [
            'The long pebble beach',
            'The seafront promenade',
            'The slopes of Biokovo behind',
            'Makarska a few kilometres away',
            'Podgora to the southeast',
        ],
        'overview': (
            'Tučepi is a village on the Makarska Riviera, about 5 km southeast of Makarska. A '
            'long pebble beach and a seafront path run along the shore, and the steep slopes of '
            'Biokovo rise immediately behind the village. The settlement is quieter and smaller '
            'than Makarska and is mostly a place for beach holidays and walks, with local cafés '
            'and restaurants along the front. A small harbour serves local boats. Makarska, with '
            'its old centre, ferry port and wider choice of services, is a short drive or bus '
            'ride away, and Podgora lies further southeast along the coast. Biokovo Nature Park, '
            'above the village, offers hiking routes and viewpoints. The nearest airport is Split'
            ' Airport (SPU). The sea is clear, the beach is long enough to find space away from '
            'the centre, and the Biokovo slopes give the village a dramatic backdrop.'
        ),
        'faqs': [
            {
                'q': 'Is Tučepi worth visiting?',
                'a': (
                    'It suits visitors who want a quiet beach stay on the Makarska Riviera with '
                    'Makarska close by for sights and services.'
                ),
            },
            {
                'q': 'How do I get to Tučepi?',
                'a': (
                    'Tučepi lies on the coast road about 5 km southeast of Makarska, and buses on'
                    ' the Split–Makarska line serve the area. Split Airport (SPU) is the nearest '
                    'airport.'
                ),
            },
            {
                'q': 'What is there to do in Tučepi?',
                'a': (
                    'Swim from the pebble beach, walk the seafront, and take trips to Makarska, '
                    'Podgora or Biokovo Nature Park.'
                ),
            },
            {
                'q': 'How long should I spend in Tučepi?',
                'a': 'A day for the beach, or a longer stay as a quiet base on the riviera.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June to September for swimming; May and September are quieter',
            },
            {'label': 'Ideal for', 'value': 'Beach holidays, walking'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {
                'label': 'Getting there',
                'value': 'About 5 km southeast of Makarska by the coast road',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'beach holidays',
            'families',
            'quiet stays',
            'walkers',
            'base for the riviera',
        ],
        'latitude': 43.27,
        'longitude': 17.05,
        'sections': [
            {
                'heading': 'A village on the shore',
                'body': (
                    'Tučepi stretches along its beach with the mountain behind. The village is '
                    'mainly modern along the shore, with older houses on the slopes above, and '
                    'the beach is pebble with clear water. The pace is slower than in Makarska, '
                    'and most visitors come for a few days of swimming and walking along the '
                    'coast, with the mountain always in view above the rooftops and the sea in '
                    'front.'
                ),
            },
            {
                'heading': 'The beach and the path',
                'body': (
                    'The seafront path follows the beach and joins the cafés, small shops and the'
                    ' harbour. Beaches are easy to reach on foot, and the Makarska end of the '
                    'coast is a short walk or drive along the shore. The beach is long enough '
                    'that it rarely feels crowded away from the centre, and water shoes make the '
                    'pebbles easier on the feet. The evenings are the time for the promenade, '
                    'when the heat has gone.'
                ),
            },
            {
                'heading': 'Biokovo and the coast',
                'body': (
                    'The Biokovo slopes above Tučepi have walking routes and viewpoints, and the '
                    'park’s main entrances are reached from the coast road. Makarska is the '
                    'nearest town for the ferry to Brač, and Podgora lies in the other direction.'
                    ' Buses on the coast road link Tučepi with Makarska and Split, so you can '
                    'reach the larger town for shops, sights and onward travel without a car.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Tučepi — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Tu%C4%8Depi',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Biokovo Nature Park',
        'slug': 'biokovo-nature-park',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Biokovo_10_2019.jpg/1280px-Biokovo_10_2019.jpg',
            'author': 'SKas',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Biokovo_10_2019.jpg',
        },
        'region': 'split',
        'place_type': 'mountains',
        'featured': False,
        'summary': (
            'A limestone mountain range behind the Makarska Riviera, rising steeply from the sea '
            'to Sveti Jure at 1,762 m.'
        ),
        'description': (
            'Biokovo Nature Park protects the mountain range that rises directly behind the '
            'Makarska Riviera. Its highest peak, Sveti Jure, is 1,762 m, and the park holds '
            'walking routes, viewpoints over the islands and a botanical garden.'
        ),
        'highlights': [
            'Sveti Jure, the highest peak at 1,762 m',
            'The Biokovo Skywalk viewpoint',
            'The Kotišina botanical garden',
            'Walking routes with views of the islands',
            'Karst landscape and endemic plants',
        ],
        'overview': (
            'Biokovo is a long limestone range running parallel to the coast behind the Makarska '
            'Riviera, and since 2006 it has been protected as a nature park. The mountain rises '
            'steeply from the sea to Sveti Jure, which at 1,762 m is the second-highest peak in '
            'Croatia. The terrain is karst: bare limestone, sinkholes, caves and rock walls, with'
            ' Mediterranean vegetation low down and mountain plants higher up, including a number'
            ' of endemic species. A road climbs from the coast to the upper part of the mountain,'
            ' where the Biokovo Skywalk viewpoint looks over the sea toward the islands of Brač, '
            'Hvar and Korčula. Walking routes of different lengths start from the coast and from '
            'the road, and the botanical garden at Kotišina shows local flora. Weather changes '
            'quickly on the mountain, so check conditions before going and wear suitable shoes.'
        ),
        'faqs': [
            {
                'q': 'Is Biokovo Nature Park worth visiting?',
                'a': (
                    'Yes, for the views and the contrast between the sea and the high karst. It '
                    'is popular for walking and for viewpoints over the islands.'
                ),
            },
            {
                'q': 'How do I get to Biokovo Nature Park?',
                'a': (
                    'The park is directly behind the Makarska Riviera. Routes up the mountain '
                    'start near Makarska and nearby villages, and Split Airport (SPU) is the '
                    'nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Biokovo Nature Park?',
                'a': (
                    'Walk marked routes, drive or hike to the viewpoints at Sveti Jure, visit the'
                    ' Biokovo Skywalk, and see the botanical garden at Kotišina.'
                ),
            },
            {
                'q': 'How long should I spend in Biokovo Nature Park?',
                'a': (
                    'A half day for a drive to the viewpoints and a short walk, or a full day for'
                    ' a longer hike. Check the weather first.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; weather can change fast at altitude',
            },
            {'label': 'Ideal for', 'value': 'Hiking, views, nature'},
            {'label': 'Time needed', 'value': 'Half a day to a full day'},
            {
                'label': 'Getting there',
                'value': 'Routes start near Makarska and nearby villages',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': ['hikers', 'views', 'nature lovers', 'photographers', 'active travellers'],
        'latitude': 43.3436,
        'longitude': 17.0553,
        'sections': [
            {
                'heading': 'A mountain above the sea',
                'body': (
                    'Biokovo’s ridge follows the coast for many kilometres, and its height gives '
                    'the sea-level villages a mountain backdrop. The upper slopes are bare '
                    'limestone, while the lower slopes hold pine woods, scrub and olive groves. '
                    'The contrast between the sea and the high karst is what draws most visitors,'
                    ' and on a clear day the viewpoints look out over the water to the islands.'
                ),
            },
            {
                'heading': 'Peaks, viewpoints and plants',
                'body': (
                    'Sveti Jure is the second-highest peak in Croatia at 1,762 m. Near it, the '
                    'Biokovo Skywalk is a viewing platform over the coast and islands. The '
                    'Kotišina botanical garden shows plants of the mountain, and a number of '
                    'species found on Biokovo are endemic. The park also has caves, sinkholes and'
                    ' rock walls typical of karst, and the walking routes vary from short strolls'
                    ' near the road to long, demanding hikes.'
                ),
            },
            {
                'heading': 'Planning a visit',
                'body': (
                    'Access to the mountain road and the upper park can depend on the weather, '
                    'and a fee may apply for entry. Temperatures at the top are much lower than '
                    'at the coast, so bring layers, water, sun protection and sturdy shoes. '
                    'Weather can change quickly on the mountain, so check conditions before you '
                    'set out, tell someone your route if you hike, and turn back if cloud or wind'
                    ' rises.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Biokovo — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Biokovo',
            },
            {'label': 'Biokovo Nature Park', 'url': 'https://pp-biokovo.hr/'},
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Sinj',
        'slug': 'sinj',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/e/ec/Sinj_-_ca._2010-_kulturnadobra.hr_Z-5117.jpg',
            'author': 'Unknown author Unknown author',
            'licence': 'CC BY-SA 3.0 hr',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0/hr/deed.en',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Sinj_-_ca._2010-_kulturnadobra.hr_Z-5117.jpg',
        },
        'region': 'split',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'The main town of the Cetina valley, home of the Sinjska Alka knights’ tournament.',
        'description': (
            'Sinj is the largest town in the Cetina valley, inland from Split. It is known for '
            'the Sinjska Alka, a knights’ tournament held each August since 1715 and inscribed on'
            ' the UNESCO list of intangible cultural heritage in 2010.'
        ),
        'highlights': [
            'Sinjska Alka tournament',
            'The Sanctuary of Our Lady of Sinj',
            'Sinj Fortress on the hill',
            'The Alka museum',
            'The Cetina valley around the town',
        ],
        'overview': (
            'Sinj is the main town of the Cetina valley, in the Dalmatian hinterland inland from '
            'Split. It is best known for the Sinjska Alka, a competition in which horsemen gallop'
            ' down a street and try to pierce a metal ring with a lance. It commemorates the '
            'defeat of an Ottoman army in 1715, is held each August, and UNESCO inscribed it on '
            'the intangible cultural heritage list in 2010. Above the town stands a fortress on a'
            ' hill, and in the town centre the Franciscan church houses the image of Our Lady of '
            'Sinj, a place of pilgrimage. The surrounding Cetina valley is a plain of fields and '
            'low hills, with the river nearby. Sinj lies to the northeast of Split and can be '
            'reached by road, so it works as a half-day or day trip from the coast.'
        ),
        'faqs': [
            {
                'q': 'Is Sinj worth visiting?',
                'a': (
                    'Yes, particularly for the Sinjska Alka in August. At other times it offers a'
                    ' quiet inland town, a fortress and the Cetina valley.'
                ),
            },
            {
                'q': 'How do I get to Sinj?',
                'a': (
                    'Sinj lies northeast of Split and is reached by road, with buses running from'
                    ' Split. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Sinj?',
                'a': (
                    'See the Alka museum, visit the Franciscan church and the Sanctuary of Our '
                    'Lady of Sinj, climb to the fortress, and explore the Cetina valley.'
                ),
            },
            {
                'q': 'How long should I spend in Sinj?',
                'a': 'Half a day for the town, or a full day with a trip along the Cetina valley.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'August for the Alka; spring and autumn for quieter visits',
            },
            {'label': 'Ideal for', 'value': 'Culture, tradition, inland trips'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'Northeast of Split by road'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': ['tradition', 'culture', 'history lovers', 'inland trips', 'photographers'],
        'latitude': 43.7036,
        'longitude': 16.6392,
        'sections': [
            {
                'heading': 'The Alka',
                'body': (
                    'The Sinjska Alka is a tournament in which riders in traditional dress race '
                    'down the street and aim a lance at a small iron ring hung above it. It '
                    'recalls the victory over the Ottomans in 1715 and has been held since then, '
                    'each August, and it was inscribed by UNESCO as intangible heritage in 2010. '
                    'The Alka museum in the town explains the event, the costumes and the rules, '
                    'and is a good place to start if you visit outside the August tournament.'
                ),
            },
            {
                'heading': 'Our Lady of Sinj',
                'body': (
                    'The Franciscan church in Sinj holds an image of the Virgin known as Our Lady'
                    ' of Sinj, which is the centre of a pilgrimage. Many people link the 1715 '
                    'victory with her. The church is open to visitors outside services, and '
                    'visitors are expected to dress modestly and keep quiet while worship is '
                    'under way. The town’s centre is small enough to see in a couple of hours on '
                    'foot.'
                ),
            },
            {
                'heading': 'The town and valley',
                'body': (
                    'A fortress stands on the hill above the town and offers a view over the '
                    'valley. The Cetina flows nearby, and the valley connects Sinj with the lower'
                    ' river and Omiš on the coast. Sinj is inland, so it is hotter in summer and '
                    'colder in winter than the coast. It makes a good day trip from Split by '
                    'road, and it combines well with a drive along the Cetina toward Omiš.'
                ),
            },
        ],
        'external_links': [
            {'label': 'Sinj — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Sinj'},
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Imotski',
        'slug': 'imotski',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Imotski_-_Crkva_sv._Franje_2020-08-06a.jpg/1280px-Imotski_-_Crkva_sv._Franje_2020-08-06a.jpg',
            'author': 'Stjepko Krehula',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Imotski_-_Crkva_sv._Franje_2020-08-06a.jpg',
        },
        'region': 'split',
        'place_type': 'lakes',
        'featured': False,
        'summary': (
            'A hill town inland from the Makarska Riviera, known for the Red Lake and Blue Lake '
            'sinkholes.'
        ),
        'description': (
            'Imotski is an inland town near the border with Bosnia and Herzegovina, known for two'
            ' sinkhole lakes in the karst: the Red Lake, surrounded by tall rock walls, and the '
            'Blue Lake, whose level changes through the year.'
        ),
        'highlights': [
            'The Red Lake (Crveno jezero)',
            'The Blue Lake (Modro jezero)',
            'Topana Fortress',
            'The old town of Imotski',
            'Karst scenery of the Imotska krajina',
        ],
        'overview': (
            'Imotski is a town in the karst plateau inland from the Makarska Riviera, close to '
            'the border with Bosnia and Herzegovina. It is known for two natural lakes inside '
            'deep sinkholes. The Red Lake (Crveno jezero) lies in a vertical-walled depression '
            'whose rock has a reddish tone, and the Blue Lake (Modro jezero) sits in a wide '
            'sinkhole near the town. The Blue Lake’s level changes with rainfall, and in a dry '
            'summer it can fall very low or disappear, so the view differs from season to season.'
            ' The Topana fortress stands above the old town, and the area around is a plateau of '
            'fields and vineyards. Imotski can be reached by road from the coast and works as a '
            'day trip from the Makarska Riviera or Split.'
        ),
        'faqs': [
            {
                'q': 'Is Imotski worth visiting?',
                'a': (
                    'Yes, for the two sinkhole lakes and the inland scenery. The Blue Lake can be'
                    ' low in summer, so check before going.'
                ),
            },
            {
                'q': 'How do I get to Imotski?',
                'a': (
                    'Imotski is reached by road from the Makarska Riviera or from Split, and '
                    'buses run from Split. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Imotski?',
                'a': (
                    'Visit the Red Lake and the Blue Lake, walk up to the Topana fortress, and '
                    'see the old town and the surrounding karst plateau.'
                ),
            },
            {
                'q': 'How long should I spend in Imotski?',
                'a': (
                    'Half a day for the lakes and the town, or a full day as an excursion from '
                    'the coast.'
                ),
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring for fuller lakes; summer can be dry'},
            {'label': 'Ideal for', 'value': 'Natural sights, inland trips'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {
                'label': 'Getting there',
                'value': 'By road from Split or the Makarska Riviera',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU)'},
        ],
        'good_for': [
            'natural sights',
            'photographers',
            'inland trips',
            'hikers',
            'curious travellers',
        ],
        'latitude': 43.4467,
        'longitude': 17.2147,
        'sections': [
            {
                'heading': 'Two lakes in sinkholes',
                'body': (
                    'The Red Lake and the Blue Lake are in collapsed sinkholes in the limestone. '
                    'The Red Lake is in a deep pit with near-vertical rock walls, and the Blue '
                    'Lake lies in a wider depression near the town. Both are examples of karst, '
                    'the landscape of soluble rock in which water has dissolved caves and '
                    'cavities underground until the roofs fell in. Viewpoints and paths near the '
                    'rim let you look down at the water, so take care near the edges.'
                ),
            },
            {
                'heading': 'A changing lake',
                'body': (
                    'The Blue Lake is fed from the karst groundwater and the water level varies '
                    'with rain. In dry weather it can nearly disappear, and in wet seasons it '
                    'fills. Ask locally or check before you travel if the water is what you want '
                    'to see. Photographs online may therefore not match what you find on the day,'
                    ' and local people can say how the lake looks that week.'
                ),
            },
            {
                'heading': 'The town',
                'body': (
                    'The old town of Imotski stands on the edge of the lakes. The Topana fortress'
                    ' on the hill above dates from the Middle Ages, and the plateau around the '
                    'town is farmed with fields and vineyards. The town is inland and near the '
                    'border with Bosnia and Herzegovina, so carry identification when travelling '
                    'in the area, and allow time for the drive from the coast, which climbs '
                    'through the mountains.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Imotski — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Imotski',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Hvar',
        'slug': 'hvar',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/J32_715_Loggia%2C_Trg_Svjetog_Stjepana.jpg/1280px-J32_715_Loggia%2C_Trg_Svjetog_Stjepana.jpg',
            'author': 'Falk2',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:J32_715_Loggia,_Trg_Svjetog_Stjepana.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': True,
        'summary': (
            'A Venetian-era harbour town on the island of Hvar, with a fortress, a theatre and '
            'the Pakleni Islands offshore.'
        ),
        'description': (
            'Hvar town sits on the south-west coast of the island of Hvar, with a large main '
            'square, a hilltop fortress and a harbour full of boats. The Pakleni Islands lie just'
            ' offshore, and ferries and catamarans link the town with Split.'
        ),
        'highlights': [
            'St Stephen’s Square (Pjaca)',
            'The Spanish Fortress (Fortica)',
            'The Hvar Theatre in the Arsenal',
            'The Cathedral of St Stephen',
            'The Pakleni Islands',
        ],
        'overview': (
            'Hvar is the main town on the island of the same name, set on a harbour on the '
            'southwest coast and developed under Venetian rule. At its centre is St Stephen’s '
            'Square, known locally as Pjaca, a large square with the cathedral and the Arsenal '
            'beside it. The Arsenal, a former Venetian naval building, holds a theatre dating '
            'from the early 17th century. Above the town a fortress, called the Spanish Fortress '
            'or Fortica, looks over the harbour and the Pakleni Islands, a small group of wooded '
            'islets reached by boat taxi. The island is also known for lavender and olive groves.'
            ' Ferries and catamarans connect Hvar town with Split; the main car ferry from Split '
            'lands at Stari Grad, on the north coast. Late spring and September are quieter and '
            'cooler than the height of summer, and the island’s lanes and fields reward a slower '
            'pace.'
        ),
        'faqs': [
            {
                'q': 'Is Hvar worth visiting?',
                'a': (
                    'Yes. The town combines a historic centre, a fortress with views and nearby '
                    'islands, and it is a base for exploring the rest of the island.'
                ),
            },
            {
                'q': 'How do I get to Hvar?',
                'a': (
                    'Catamarans run from Split to Hvar town. The car ferry from Split goes to '
                    'Stari Grad, on the north coast. The nearest airport is Split Airport (SPU).'
                ),
            },
            {
                'q': 'What is there to do in Hvar?',
                'a': (
                    'Walk St Stephen’s Square, climb to the Spanish Fortress, see the theatre in '
                    'the Arsenal, and take a boat to the Pakleni Islands.'
                ),
            },
            {
                'q': 'How long should I spend in Hvar?',
                'a': 'A day or two covers the town, and a few days let you see more of the island.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May–June and September; July and August are busy',
            },
            {'label': 'Ideal for', 'value': 'Island stays, history, swimming'},
            {'label': 'Time needed', 'value': 'One to several days'},
            {
                'label': 'Getting there',
                'value': 'Ferry or catamaran from Split; car ferry to Stari Grad',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['island stays', 'history lovers', 'swimmers', 'couples', 'boat trips'],
        'latitude': 43.1729,
        'longitude': 16.4412,
        'sections': [
            {
                'heading': 'A Venetian harbour town',
                'body': (
                    'Hvar prospered as a Venetian naval base in the Middle Ages, and its square, '
                    'loggia, palaces and Arsenal come from that period and later. The town stands'
                    ' between the harbour and the hill, with narrow stone lanes running up from '
                    'the water. The centre is compact, and everything from the harbour to the '
                    'fortress can be covered on foot in a couple of hours, although the climb to '
                    'the fortress is steep.'
                ),
            },
            {
                'heading': 'Sights',
                'body': (
                    'The Cathedral of St Stephen and the Arsenal both face the square. The '
                    'Arsenal holds a theatre from the early 17th century above its ground floor. '
                    'The Spanish Fortress above the town is reached by a path and gives a wide '
                    'view of the harbour and islands. Wear sturdy shoes, as the path is stone, '
                    'and go in the cooler part of the day in summer, because there is little '
                    'shade on the hill.'
                ),
            },
            {
                'heading': 'The island and the Pakleni Islands',
                'body': (
                    'Beyond the town, the island has Stari Grad, Jelsa and fields of lavender and'
                    ' olives. The Pakleni Islands, a short boat ride from the harbour, have '
                    'pebble coves and pine woods and are reached by taxi boat in season. Buses '
                    'and the island’s roads link the town with Stari Grad and Jelsa, so you can '
                    'combine the town with the Greek plain and the quieter bays on the north '
                    'coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Stari Grad',
        'slug': 'stari-grad',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Aerial_image_of_the_Stari_Grad_Plain_%28view_from_the_southwest%29.jpg/1280px-Aerial_image_of_the_Stari_Grad_Plain_%28view_from_the_southwest%29.jpg',
            'author': 'Carsten Steger',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Aerial_image_of_the_Stari_Grad_Plain_(view_from_the_southwest).jpg',
        },
        'region': 'split',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A town on the north coast of Hvar founded by Greek settlers in 384 BC, with a '
            'UNESCO-listed plain.'
        ),
        'description': (
            'Stari Grad was founded as Pharos by Greek settlers from the island of Paros in 384 '
            'BC. The fertile plain behind the town still keeps its ancient Greek field divisions '
            'and was inscribed on the UNESCO World Heritage List in 2008.'
        ),
        'highlights': [
            'The Stari Grad Plain (UNESCO)',
            'Tvrdalj, the fortified house of Petar Hektorović',
            'The old town lanes',
            'The harbour and long bay',
            'The Split–Stari Grad ferry port',
        ],
        'overview': (
            'Stari Grad is one of the oldest towns in Europe. It was founded as Pharos by Greek '
            'settlers from the island of Paros in 384 BC, and it sits at the head of a long, '
            'narrow bay on the north coast of Hvar. Behind it lies the Stari Grad Plain, a '
            'fertile stretch of farmland whose field boundaries, laid out by the Greeks, have '
            'survived for more than two thousand years and were inscribed by UNESCO in 2008. '
            'Today the plain grows grapes and olives. In the old town stands Tvrdalj, the '
            'fortified house of the 16th-century poet Petar Hektorović, with a fishpond and '
            'gardens. Stari Grad is also the island’s ferry port: the Split–Stari Grad line is '
            'the main way to reach Hvar with a vehicle. The nearest airport is Split Airport '
            '(SPU), and the town of Hvar lies across the island.'
        ),
        'faqs': [
            {
                'q': 'Is Stari Grad worth visiting?',
                'a': (
                    'Yes, for the ancient history, the old town and the plain, which is easily '
                    'explored on foot or by bike.'
                ),
            },
            {
                'q': 'How do I get to Stari Grad?',
                'a': (
                    'The Split–Stari Grad ferry crosses to the town, and the nearest airport is '
                    'Split Airport (SPU). Buses connect the ferry port with Hvar town and Jelsa.'
                ),
            },
            {
                'q': 'What is there to do in Stari Grad?',
                'a': (
                    'Walk the old town, see Tvrdalj, cycle or walk through the plain, and swim at'
                    ' the beaches along the bay.'
                ),
            },
            {
                'q': 'How long should I spend in Stari Grad?',
                'a': 'A half day for the town, or a day if you include the plain.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn for walking and cycling'},
            {'label': 'Ideal for', 'value': 'History, walking, cycling'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'Ferry from Split to Stari Grad'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['history lovers', 'cyclists', 'walkers', 'ferry arrivals', 'slow travel'],
        'latitude': 43.185,
        'longitude': 16.595,
        'sections': [
            {
                'heading': 'The Greek town of Pharos',
                'body': (
                    'Settlers from Paros founded Pharos on this coast in 384 BC, and the town has'
                    ' been inhabited since. Its position at the end of a deep bay gave good '
                    'shelter, and the harbour is still the centre of the town today. Walking the '
                    'waterfront, you can see the long, narrow bay that the Greeks chose, and the '
                    'ferry from Split arrives at the same sheltered water.'
                ),
            },
            {
                'heading': 'The plain',
                'body': (
                    'The Stari Grad Plain was divided by the Greeks into regular plots separated '
                    'by dry-stone walls, and the pattern survives. UNESCO listed it in 2008 as a '
                    'cultural landscape. Farmers still grow grapes and olives on it, and paths '
                    'cross it on foot and by bike. The plain is flat and open, so it suits an '
                    'easy walk or ride, but there is little shade, and a hat and water are worth '
                    'bringing.'
                ),
            },
            {
                'heading': 'Tvrdalj and the old town',
                'body': (
                    'Tvrdalj was the home of Petar Hektorović, a poet of the 16th century, and '
                    'has a walled garden and fishpond. It stands in the old town, whose stone '
                    'lanes and small squares are close to the harbour. The old town is small '
                    'enough to cover in an hour, and the harbour cafés are the place to rest '
                    'after a walk on the plain or before an onward bus to Hvar town or Jelsa.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Stari Grad Plain — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Stari_Grad_Plain',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Jelsa',
        'slug': 'jelsa',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Aerial_image_of_Jelsa_%28view_from_the_south%29.jpg/1280px-Aerial_image_of_Jelsa_%28view_from_the_south%29.jpg',
            'author': 'Carsten Steger',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Aerial_image_of_Jelsa_(view_from_the_south).jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small harbour town on the north coast of Hvar, with pine-fringed bays and nearby '
            'Vrboska.'
        ),
        'description': (
            'Jelsa is a harbour town on the north coast of the island of Hvar, east of Stari '
            'Grad. It has a waterfront with cafés, pebble beaches and bays, and the small village'
            ' of Vrboska lies close by.'
        ),
        'highlights': [
            'The harbour and waterfront',
            'Pebble beaches and bays',
            'The village of Vrboska nearby',
            'The tunnel road to Zavala',
            'Walking in the island’s hills',
        ],
        'overview': (
            'Jelsa is a small harbour town on the north coast of Hvar, east of Stari Grad and the'
            ' ferry port. A waterfront with cafés and restaurants runs along the harbour, and '
            'pebble beaches and quiet bays lie on either side. The village of Vrboska is next '
            'door, a small harbour with a fortified church. From Jelsa a road runs through a '
            'tunnel above the village of Pitve to Zavala, on the south coast of the island. The '
            'hills behind the town are covered with pines and scrub and offer walks. Jelsa is '
            'reached from the Stari Grad ferry port by road, and the nearest airport is Split '
            'Airport (SPU). The town suits families and couples looking for a slower stay, with '
            'pine-shaded shores, clear water and cafés on the waterfront. Roads and buses link it'
            ' with Stari Grad, Vrboska and Hvar town, and boats serve the coast in summer.'
        ),
        'faqs': [
            {
                'q': 'Is Jelsa worth visiting?',
                'a': (
                    'It suits visitors who want a smaller, quieter base on Hvar island, with '
                    'beaches and bays nearby.'
                ),
            },
            {
                'q': 'How do I get to Jelsa?',
                'a': (
                    'Take the ferry from Split to Stari Grad and continue by road, or take a bus '
                    'from the ferry port. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Jelsa?',
                'a': (
                    'Swim from the beaches, walk the waterfront, visit Vrboska and take the road '
                    'to Zavala.'
                ),
            },
            {
                'q': 'How long should I spend in Jelsa?',
                'a': 'A day for the town, or longer for a quiet beach stay.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June to September for swimming'},
            {'label': 'Ideal for', 'value': 'Beach stays, quiet island life'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {'label': 'Getting there', 'value': 'By road from the Stari Grad ferry port'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['beach holidays', 'quiet stays', 'families', 'walkers', 'island life'],
        'latitude': 43.1615,
        'longitude': 16.695,
        'sections': [
            {
                'heading': 'A harbour town',
                'body': (
                    'Jelsa’s small harbour and waterfront are its centre, with stone houses '
                    'around the square and a church above. The town is smaller and quieter than '
                    'Hvar town, with a waterfront lined with cafés and restaurants. Pine trees '
                    'shade parts of the shore, and the town’s pace is slow in the evenings, when '
                    'people walk along the water after the heat of the day.'
                ),
            },
            {
                'heading': 'Beaches and bays',
                'body': (
                    'Pebble beaches lie on both sides of the town, with pine trees behind them in'
                    ' places. Other coves are reached by short walks or by road. The water is '
                    'clear and the beaches are easy for families, with shallow edges and shade '
                    'nearby. Water shoes help on the pebbles and on rocky edges, and the walks '
                    'along the shore bring you to quieter bays outside the town.'
                ),
            },
            {
                'heading': 'Around Jelsa',
                'body': (
                    'Vrboska is a short walk or drive away. The tunnel road leads to Zavala on '
                    'the south coast, and Stari Grad and its ferry port lie to the west. Hvar '
                    'town is across the island. Buses on the island’s main road link Jelsa with '
                    'Stari Grad and Hvar town, so you can see several places in a day, and the '
                    'roads through the hills pass olive groves, vineyards and small villages.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Jelsa — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Jelsa,_Croatia',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Bol',
        'slug': 'bol',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/J35_870_Bol%2C_Riva.jpg/1280px-J35_870_Bol%2C_Riva.jpg',
            'author': 'Falk2',
            'licence': 'CC BY-SA 3.0 de',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0/de/deed.en',
            'source_url': 'https://commons.wikimedia.org/wiki/File:J35_870_Bol,_Riva.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A town on the south coast of Brač, next to Zlatni Rat beach and below Vidova Gora.',
        'description': (
            'Bol is a small town on the south coast of the island of Brač, famous for Zlatni Rat,'
            ' a pebble spit that points into the sea and shifts shape with the wind and currents.'
            ' Vidova Gora, the highest peak on the Adriatic islands, rises behind.'
        ),
        'highlights': [
            'Zlatni Rat beach',
            'Vidova Gora, the highest island peak on the Adriatic',
            'The Dominican monastery and its museum',
            'Windsurfing and kitesurfing',
            'The waterfront promenade',
        ],
        'overview': (
            'Bol is a town on the south coast of Brač, the largest island in central Dalmatia. '
            'Its landmark is Zlatni Rat, a pebble beach in the shape of a spit that extends into '
            'the sea; the tip moves with the wind and currents over time. Behind the town rises '
            'Vidova Gora, which at 778 m is the highest point of any island in the Adriatic. The '
            'waterfront promenade runs along the harbour, and the Dominican monastery, with a '
            'museum, stands east of the centre. The wind along the channel makes Bol a known '
            'place for windsurfing and kitesurfing. Brač Airport (BWK) is on the island, and '
            'passenger boats link Bol with Split; the car ferry from Split lands at Supetar, on '
            'the north coast, and a road crosses the island.'
        ),
        'faqs': [
            {
                'q': 'Is Bol worth visiting?',
                'a': (
                    'Yes. Zlatni Rat and the views from Vidova Gora are the main reasons, and the'
                    ' town is a good base for water sports.'
                ),
            },
            {
                'q': 'How do I get to Bol?',
                'a': (
                    'Passenger boats run from Split to Bol, and Brač Airport (BWK) is on the '
                    'island. The car ferry from Split lands at Supetar, and a road crosses to '
                    'Bol.'
                ),
            },
            {
                'q': 'What is there to do in Bol?',
                'a': (
                    'Swim at Zlatni Rat, walk or drive up to Vidova Gora, visit the Dominican '
                    'monastery, and try windsurfing or kitesurfing.'
                ),
            },
            {
                'q': 'How long should I spend in Bol?',
                'a': (
                    'A day for the beach and the town, or several days to add the mountain and '
                    'the water sports.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June to September for swimming; wind sports through the warm season',
            },
            {'label': 'Ideal for', 'value': 'Beaches, water sports, views'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {
                'label': 'Getting there',
                'value': 'Passenger boat from Split; road from Supetar',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {
                'label': 'Nearest airport',
                'value': 'Brač Airport (BWK) or Split Airport (SPU)',
            },
        ],
        'good_for': ['beach holidays', 'windsurfing', 'kitesurfing', 'walkers', 'island stays'],
        'latitude': 43.2614,
        'longitude': 16.6561,
        'sections': [
            {
                'heading': 'Zlatni Rat',
                'body': (
                    'The Golden Horn is a pebble spit about a kilometre from the centre of Bol '
                    'and is reached by a shore path lined with pines. Because its tip is moved by'
                    ' the wind and currents, the shape of the beach changes over time. The beach '
                    'is popular in summer, so go early for space. Water shoes help on the '
                    'pebbles, and the pines along the path give shade on the walk from town.'
                ),
            },
            {
                'heading': 'Vidova Gora',
                'body': (
                    'Vidova Gora is the highest peak on the Adriatic islands at 778 m. A road and'
                    ' walking paths lead up from Bol, and the view covers Zlatni Rat and the '
                    'nearby islands. Bring water and good shoes, as the paths are rocky and the '
                    'top is exposed to sun and wind. The higher ground is cooler than the coast, '
                    'so a light layer is useful, and clear mornings give the best view.'
                ),
            },
            {
                'heading': 'Town and wind',
                'body': (
                    'The Dominican monastery east of the centre has a small museum. The channel '
                    'between Brač and Hvar is windy, and wind sports are popular in the warm '
                    'season, with schools and rentals in the town. The harbour and waterfront '
                    'promenade have cafés and restaurants, and boats leave from the harbour for '
                    'trips along the coast. Beginners should use a school and follow local advice'
                    ' on wind and sea conditions.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Bol — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Bol,_Croatia',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Supetar',
        'slug': 'supetar',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Supetar_Waterfront.jpg/1280px-Supetar_Waterfront.jpg',
            'author': 'WeatheredAviation',
            'licence': 'CC0',
            'licence_url': 'https://creativecommons.org/publicdomain/zero/1.0/deed.en',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Supetar_Waterfront.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'The main port of Brač, linked to Split by car ferry, with a harbour town and pebble '
            'beaches.'
        ),
        'description': (
            'Supetar is the largest town and the main ferry port of the island of Brač. A car '
            'ferry crosses from Split, and the town offers a harbour, pebble beaches and a '
            'notable cemetery with the Petrinović mausoleum.'
        ),
        'highlights': [
            'The Split–Supetar ferry',
            'The Petrinović mausoleum',
            'The harbour and promenade',
            'Pebble beaches',
            'Brač stone heritage',
        ],
        'overview': (
            'Supetar is the main town and ferry port on the north coast of Brač. The car ferry '
            'from Split crosses the channel to its harbour, which makes it the usual arrival '
            'point on the island. The town has a seafront promenade, and pebble beaches. On a '
            'headland stands the cemetery with the Petrinović mausoleum, a 20th-century monument '
            'by the sculptor Toma Rosandić. Brač is known for its white limestone, quarried on '
            'the island and used in buildings including Diocletian’s Palace in Split. Roads lead '
            'from Supetar across the island to Bol and to other villages. Brač Airport (BWK) is '
            'on the island, and Split Airport (SPU) is the other nearby airport. The town is a '
            'practical base for exploring Brač by car or bus, and a short walk from the quay '
            'brings you to the beaches and the waterfront.'
        ),
        'faqs': [
            {
                'q': 'Is Supetar worth visiting?',
                'a': (
                    'It is the usual arrival point on Brač and offers beaches, a harbour and a '
                    'short stay before travelling on.'
                ),
            },
            {
                'q': 'How do I get to Supetar?',
                'a': (
                    'Take the car ferry from Split to Supetar. Brač Airport (BWK) is on the '
                    'island, and Split Airport (SPU) is on the mainland.'
                ),
            },
            {
                'q': 'What is there to do in Supetar?',
                'a': (
                    'Walk the promenade, swim from the pebble beaches, visit the Petrinović '
                    'mausoleum, and travel on to Bol and other villages.'
                ),
            },
            {
                'q': 'How long should I spend in Supetar?',
                'a': 'A few hours to a day on arrival, or longer as a base on the island.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June to September for swimming'},
            {'label': 'Ideal for', 'value': 'Island arrival, beach stays'},
            {'label': 'Time needed', 'value': 'A few hours to a day'},
            {'label': 'Getting there', 'value': 'Car ferry from Split'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {
                'label': 'Nearest airport',
                'value': 'Brač Airport (BWK) or Split Airport (SPU)',
            },
        ],
        'good_for': [
            'island arrival',
            'families',
            'beach holidays',
            'ferry travellers',
            'short stays',
        ],
        'latitude': 43.3836,
        'longitude': 16.5547,
        'sections': [
            {
                'heading': 'The island’s main port',
                'body': (
                    'Supetar lies on the shore facing Split, and the ferry crossing is the main '
                    'link with the mainland. The harbour and waterfront make up the centre of the'
                    ' town, with cafés, shops and the ferry quay close together. Most visitors '
                    'arrive here by car or on foot, and the town is a convenient place to stop '
                    'before travelling on to Bol and the other villages by road or bus.'
                ),
            },
            {
                'heading': 'The mausoleum',
                'body': (
                    'The Petrinović mausoleum stands in the town cemetery on a headland and was '
                    'designed by the sculptor Toma Rosandić in the early 20th century. It is a '
                    'distinctive building in the white stone of the island. The cemetery is a '
                    'place of burial for local families, so visit quietly and respectfully, and '
                    'the walk out along the shore to the headland is pleasant in the evening.'
                ),
            },
            {
                'heading': 'Brač stone and the island',
                'body': (
                    'Brač is known for its white limestone, quarried on the island. Beyond '
                    'Supetar, roads lead to Bol on the south coast and to inland villages, so a '
                    'hire car or bus is useful for seeing more of the island. Stonemasonry is '
                    'still an island tradition, and the stone has been used in buildings in '
                    'Split, including Diocletian’s Palace, so the palace and the quarries are '
                    'linked across the water.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Supetar — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Supetar',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Vis',
        'slug': 'vis',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/J32_433_Vis-Stadt.jpg/1280px-J32_433_Vis-Stadt.jpg',
            'author': 'Falk2',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:J32_433_Vis-Stadt.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'The main town of Vis, a far-out Adriatic island that was closed to foreign visitors '
            'until 1989.'
        ),
        'description': (
            'Vis town lies on a bay on the northeast side of the island of Vis, the most distant '
            'of the central Dalmatian islands. The island was a military base closed to foreign '
            'visitors until 1989, and was settled by Greek colonists in antiquity.'
        ),
        'highlights': [
            'Vis town and its two old quarters, Kut and Luka',
            'Remains of Greek and Roman Issa',
            'Local wines such as Vugava',
            'The Split–Vis ferry',
            'Boat trips to Biševo',
        ],
        'overview': (
            'Vis is an island far out in the Adriatic, reached by ferry from Split, and Vis town '
            'is its main settlement. The town stands on a deep bay and has two old quarters, Kut '
            'and Luka, facing each other across the harbour. Greek colonists founded the town of '
            'Issa here in the 4th century BC, and traces of the Greek and Roman town survive. In '
            'modern times the island was a Yugoslav military base and was closed to foreign '
            'visitors until 1989, which helped keep it quiet. The island is known for its wine, '
            'including the local white grape Vugava. The town also serves as a base for boat '
            'trips to the island of Biševo and its Blue Cave, usually departing from Komiža on '
            'the west side. Split Airport (SPU) is the nearest airport, and the ferry crosses '
            'from Split.'
        ),
        'faqs': [
            {
                'q': 'Is Vis worth visiting?',
                'a': (
                    'Yes, for a quieter island with historic quarters, local wine and sea trips. '
                    'It takes longer to reach than the nearer islands.'
                ),
            },
            {
                'q': 'How do I get to Vis?',
                'a': (
                    'Ferries run from Split to Vis town. Split Airport (SPU) is the nearest '
                    'airport.'
                ),
            },
            {
                'q': 'What is there to do in Vis?',
                'a': (
                    'Walk through Kut and Luka, see the remains of Greek and Roman Issa, taste '
                    'local wine, and take a boat trip to Biševo.'
                ),
            },
            {
                'q': 'How long should I spend in Vis?',
                'a': 'Two or three days is a good length for the town and the island.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September'},
            {'label': 'Ideal for', 'value': 'Quiet island stays, history, wine'},
            {'label': 'Time needed', 'value': 'Two days or longer'},
            {'label': 'Getting there', 'value': 'Ferry from Split to Vis town'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['quiet stays', 'history lovers', 'wine', 'boat trips', 'island life'],
        'latitude': 43.0603,
        'longitude': 16.1836,
        'sections': [
            {
                'heading': 'An island far out',
                'body': (
                    'Vis is the farthest inhabited island of this part of the Adriatic from the '
                    'mainland, and the crossing from Split is longer than to Brač, Hvar or Šolta.'
                    ' For decades the island was a military base closed to foreign visitors, '
                    'until 1989. Because of that isolation the island kept much of its quiet, and'
                    ' its small harbours, stone houses and fields feel less developed than on the'
                    ' nearer islands.'
                ),
            },
            {
                'heading': 'Greek Issa',
                'body': (
                    'Greek colonists founded Issa here in the 4th century BC. Remains of the '
                    'Greek and Roman town, including a Roman bath complex, survive in and around '
                    'Vis town and can be seen there. Issa later issued its own coins and founded '
                    'colonies of its own, including, according to ancient sources, Tragurion, '
                    'today’s Trogir. Walking the town’s waterfront, you pass through the area '
                    'where the ancient settlement lay.'
                ),
            },
            {
                'heading': 'Wine and the sea',
                'body': (
                    'Vis has a long tradition of winemaking, and the white Vugava grape is '
                    'associated with the island. Boat trips from the island go to the Blue Cave '
                    'on Biševo and to quiet coves around the coast. The island’s roads link Vis '
                    'town with Komiža on the west coast, and a car, bicycle or scooter is the '
                    'easiest way to move between the two, and to reach the bays on the island’s '
                    'coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Komiža',
        'slug': 'komiza',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Komi%C5%BEa_Island_Vis.jpg/1280px-Komi%C5%BEa_Island_Vis.jpg',
            'author': 'ModriDirkac',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Komi%C5%BEa_Island_Vis.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A fishing town on the west coast of Vis, with a harbour, an old tower and boats to '
            'Biševo.'
        ),
        'description': (
            'Komiža is a traditional fishing town on the west coast of Vis, at the foot of Mount '
            'Hum. Its harbour is the usual departure point for boat trips to the Blue Cave on '
            'Biševo.'
        ),
        'highlights': [
            'The harbour and waterfront',
            'The Renaissance tower and town museum',
            'Boat trips to the Blue Cave',
            'The falkuša fishing boat tradition',
            'Mount Hum above the town',
        ],
        'overview': (
            'Komiža is a small town on the west side of the island of Vis, built around a harbour'
            ' at the foot of Mount Hum. For centuries its people were fishermen, and it is '
            'associated with the falkuša, a traditional wooden fishing boat. A Renaissance tower '
            'beside the harbour houses the town’s museum. Narrow lanes of stone houses run back '
            'from the waterfront. The harbour is the usual starting point for boat trips to '
            'Biševo, a small island southwest of Vis with the Blue Cave, and the road from Vis '
            'town crosses the island to reach Komiža. Hum, at 587 m the highest point on Vis, '
            'rises above the town. Ferries run from Split to Vis town, and Komiža can be reached '
            'by road from there. The town is quiet in the evenings, with cafés on the quay and '
            'the lights of the boats on the water.'
        ),
        'faqs': [
            {
                'q': 'Is Komiža worth visiting?',
                'a': (
                    'Yes, for the old harbour, the fishing heritage and as the departure point '
                    'for Biševo.'
                ),
            },
            {
                'q': 'How do I get to Komiža?',
                'a': (
                    'Take the ferry from Split to Vis town and continue by road across the island'
                    ' to Komiža. Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Komiža?',
                'a': (
                    'Walk the waterfront, visit the museum in the tower, take a boat trip to the '
                    'Blue Cave on Biševo, and walk up Mount Hum.'
                ),
            },
            {
                'q': 'How long should I spend in Komiža?',
                'a': 'A day for the town, or longer with boat trips.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September'},
            {'label': 'Ideal for', 'value': 'Fishing heritage, boat trips, quiet stays'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {
                'label': 'Getting there',
                'value': 'By road from Vis town, after the ferry from Split',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['quiet stays', 'boat trips', 'fishing heritage', 'photographers', 'walkers'],
        'latitude': 43.0444,
        'longitude': 16.0911,
        'sections': [
            {
                'heading': 'A fishing town',
                'body': (
                    'Komiža grew around fishing, and its boats and nets shaped the town’s life. '
                    'The falkuša, a traditional wooden boat of Komiža, is a symbol of this '
                    'history. Fishing for sardines and other fish was the town’s livelihood for '
                    'centuries, and today the harbour still holds fishing boats alongside the '
                    'boats that take visitors out to sea. Stone houses line the quay, and the '
                    'town keeps the look of a working harbour.'
                ),
            },
            {
                'heading': 'Tower and harbour',
                'body': (
                    'The Renaissance tower beside the harbour holds the town museum, and the '
                    'waterfront is lined with stone houses and cafés. Narrow lanes lead back from'
                    ' the quay, with small squares and churches among the houses. The harbour is '
                    'small, so the whole town can be seen on foot in an hour or two, and the '
                    'evening light on the water and the houses makes the waterfront a good place '
                    'to walk after the boats have returned.'
                ),
            },
            {
                'heading': 'Boats to Biševo',
                'body': (
                    'Boat trips to Biševo and the Blue Cave leave from Komiža’s harbour in the '
                    'season. Hum, above the town, can be climbed by a road or on foot for a wide '
                    'view of the coast. Trips are weather-dependent, so check with the operator '
                    'on the day, and bring sun protection and water. Komiža is reached from Vis '
                    'town by road across the island, which passes through vineyards and fields.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Komiža — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Komi%C5%BEa',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Biševo',
        'slug': 'bisevo',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Aerial_image_of_Bi%C5%A1evo_%28view_from_the_southwest%29.jpg/1280px-Aerial_image_of_Bi%C5%A1evo_%28view_from_the_southwest%29.jpg',
            'author': 'Carsten Steger',
            'licence': 'CC BY-SA 4.0',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/4.0',
            'source_url': 'https://commons.wikimedia.org/wiki/File:Aerial_image_of_Bi%C5%A1evo_(view_from_the_southwest).jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': 'A small island southwest of Vis, home to the Blue Cave, reached by boat from Komiža.',
        'description': (
            'Biševo is a small island southwest of Vis. Its Blue Cave (Modra špilja) is a sea '
            'cave where sunlight entering through an underwater opening lights the water silvery '
            'blue, best seen around midday in fair weather.'
        ),
        'highlights': [
            'The Blue Cave (Modra špilja)',
            'The boat crossing from Komiža',
            'Porat, the island’s landing',
            'Salbunara bay',
            'Walking on the island',
        ],
        'overview': (
            'Biševo is a small island southwest of Vis, with very few year-round residents. Its '
            'main attraction is the Blue Cave (Modra špilja), a sea cave on the east coast that '
            'is entered by small boat. Sunlight passes through an opening under the water and '
            'lights the inside of the cave with a silvery-blue glow, which is strongest around '
            'midday on a clear day. The cave has been known to visitors since the 19th century. '
            'Trips usually start from Komiža on Vis, often combined with stops at other coves, '
            'and the cave can be closed to visits when the sea is rough. The island has a small '
            'landing at Porat and coves such as Salbunara bay, and paths cross its low hills. '
            'Bring water and sun protection, as there is little shade.'
        ),
        'faqs': [
            {
                'q': 'Is Biševo worth visiting?',
                'a': (
                    'Yes, mainly for the Blue Cave. The boat trip from Komiža also passes quiet '
                    'coves.'
                ),
            },
            {
                'q': 'How do I get to Biševo?',
                'a': (
                    'Biševo is reached by boat, usually from Komiža on Vis. Ferries run from '
                    'Split to Vis, and Split Airport (SPU) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do on Biševo?',
                'a': 'Visit the Blue Cave by boat, swim in the coves, and walk on the island.',
            },
            {
                'q': 'How long should I spend on Biševo?',
                'a': 'A half day to a day, depending on the boat trip.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; around midday for the cave',
            },
            {'label': 'Ideal for', 'value': 'Boat trips, swimming'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {
                'label': 'Getting there',
                'value': 'By boat from Komiža; ferry from Split to Vis',
            },
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['boat trips', 'swimmers', 'photographers', 'day trips from Vis', 'sea caves'],
        'latitude': 42.983,
        'longitude': 16.017,
        'sections': [
            {
                'heading': 'The Blue Cave',
                'body': (
                    'The Blue Cave is a sea cave on the east coast of the island. The entrance is'
                    ' low, and visitors enter by small boat. Light that comes in through an '
                    'opening under the water gives the cave its silvery-blue colour, and the '
                    'effect is strongest around midday on a clear day. The visit inside is brief,'
                    ' so most of the trip is the boat ride, and the cave is not open when the sea'
                    ' is rough or the swell is high.'
                ),
            },
            {
                'heading': 'Getting there',
                'body': (
                    'Boats leave from Komiža on Vis and cross the channel to the island. Many '
                    'trips include swimming stops. Visits depend on the sea and weather, so a '
                    'trip may be changed or cancelled when conditions are poor. Book with a local'
                    ' operator, ask what the trip includes, and bring a swimsuit, a towel, sun '
                    'protection and water, because there is little shade on the boat and the '
                    'island.'
                ),
            },
            {
                'heading': 'On the island',
                'body': (
                    'The landing at Porat has a few houses, and Salbunara bay is a cove on the '
                    'island’s coast. Paths cross the low hills, and there is little shade, so '
                    'bring water and a hat. The island is small and quiet, with few year-round '
                    'residents, so services are limited and visitors should carry what they need.'
                    ' The surrounding sea is clear, and swimming stops are a regular part of boat'
                    ' trips.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Biševo — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Bi%C5%A1evo',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
    {
        'name': 'Šolta',
        'slug': 'solta',
        'photo': {
            'src': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c6/%C5%A0olta_Maslinica_Hrvatska_Hafen_2012_a.jpg/1280px-%C5%A0olta_Maslinica_Hrvatska_Hafen_2012_a.jpg',
            'author': 'Joadl',
            'licence': 'CC BY-SA 3.0 at',
            'licence_url': 'https://creativecommons.org/licenses/by-sa/3.0/at/deed.en',
            'source_url': 'https://commons.wikimedia.org/wiki/File:%C5%A0olta_Maslinica_Hrvatska_Hafen_2012_a.jpg',
        },
        'region': 'split',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'An island between Split and Brač, a short ferry ride from Split, with olive groves '
            'and quiet bays.'
        ),
        'description': (
            'Šolta lies in the channel between Split and Brač, reached by a short car ferry from '
            'Split to Rogač. The island is known for olive oil and honey, and has quiet bays, '
            'small ports and low hills.'
        ),
        'highlights': [
            'The Split–Rogač ferry',
            'Maslinica and its castle',
            'Nečujam bay',
            'Olive groves and honey',
            'Stomorska and Grohote',
        ],
        'overview': (
            'Šolta is an island between Split and Brač, close to Split. A car ferry crosses from '
            'Split to Rogač, and the island’s roads link the main settlements: Grohote, the '
            'inland village, Maslinica on the west coast, and Stomorska on the east. Maslinica '
            'has a harbour and a 17th-century castle, and Nečujam is a sheltered bay on the north'
            ' coast. Šolta’s landscape is low and rocky, with olive groves, vineyards and pine '
            'woods, and the island is known for olive oil and honey. It is quieter than the '
            'larger islands, and the crossing from Split is short, so it can be a day trip or a '
            'quiet stay. Split Airport (SPU) is the nearest airport. Local producers sell olive '
            'oil and honey, and the island’s roads suit a slow drive or a bicycle.'
        ),
        'faqs': [
            {
                'q': 'Is Šolta worth visiting?',
                'a': (
                    'It suits visitors who want a quiet island close to Split, with coves and '
                    'olive groves.'
                ),
            },
            {
                'q': 'How do I get to Šolta?',
                'a': (
                    'Take the car ferry from Split to Rogač. Split Airport (SPU) is the nearest '
                    'airport.'
                ),
            },
            {
                'q': 'What is there to do on Šolta?',
                'a': (
                    'Swim in the bays, visit Maslinica and its castle, walk through the olive '
                    'groves, and taste local olive oil and honey.'
                ),
            },
            {
                'q': 'How long should I spend on Šolta?',
                'a': (
                    'A day trip covers the main places, and a longer stay suits a quiet beach '
                    'holiday.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June to September for swimming; May and September are quieter',
            },
            {'label': 'Ideal for', 'value': 'Quiet island stays, short trips from Split'},
            {'label': 'Time needed', 'value': 'A day or longer'},
            {'label': 'Getting there', 'value': 'Car ferry from Split to Rogač'},
            {'label': 'Region', 'value': 'Split-Dalmatia County (Dalmatia)'},
            {'label': 'Nearest airport', 'value': 'Split Airport (SPU), then ferry'},
        ],
        'good_for': ['quiet stays', 'day trips from Split', 'swimmers', 'cyclists', 'families'],
        'latitude': 43.3925,
        'longitude': 16.2961,
        'sections': [
            {
                'heading': 'Close to Split',
                'body': (
                    'Šolta lies a short crossing from Split, which makes it an easy first island.'
                    ' The ferry lands at Rogač, and the island’s roads link the villages. The '
                    'island is small enough to see by car or bicycle in a day, and its quiet '
                    'roads wind through olive groves, pine woods and small stone villages. '
                    'Services are simpler than on the larger islands, so check opening '
                    'arrangements locally.'
                ),
            },
            {
                'heading': 'Maslinica and the bays',
                'body': (
                    'Maslinica is a small harbour village on the west coast with a castle from '
                    'the 17th century. Nečujam on the north coast is a sheltered bay with pine '
                    'woods and pebble beaches. Other coves are scattered around the coast and '
                    'reached by short roads or paths. The water is clear, and the bays suit '
                    'swimming and boating, with few crowds outside the height of summer.'
                ),
            },
            {
                'heading': 'Olives and honey',
                'body': (
                    'Olives and bees are traditional in the island’s farming, and olive oil and '
                    'honey are local products. Grohote is the main inland village, and Stomorska '
                    'lies on the east coast. Roads link all of them, and local producers sell oil'
                    ' and honey in the villages, so a drive around the island is a good way to '
                    'meet them, and to try the island’s food in small family restaurants.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Šolta — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/%C5%A0olta',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
    },
]
