"""Croatia places: continental Croatia (the north, Slavonia, Baranja and the Sava).

Editorial town and nature-park guides for croatia-experience.me. Plain, factual text with no
prices, opening hours or ratings. Read by ``seed_croatia``.
"""

from __future__ import annotations

PLACES: list[dict] = [
    {
        'name': 'Varaždin',
        'slug': 'varazdin',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A baroque town on the Drava in northern Croatia, with a walkable centre and '
        'an old fortress.',
        'description': (
            'Varaždin lies in the far north of Croatia, on the Drava river. Its compact centre '
            'is lined with baroque palaces and churches, and the Old Town fortress at its edge '
            'holds the town museum. It is a quiet base for the castles and hills of the '
            'Zagorje and Međimurje.'
        ),
        'highlights': [
            'Old Town fortress and City Museum',
            'Town Hall on the main square',
            'Baroque palaces of the old centre',
            'Cathedral of the Assumption',
            'Varaždin Cemetery',
        ],
        'overview': (
            'Varaždin grew up on the Drava as a trading and administrative town, and in the '
            '18th century it was the seat of the Croatian government for a few years. A fire '
            'in 1776 led to a large rebuilding, which is why the centre is so consistently '
            'baroque. The streets around the main square, Trg kralja Tomislava, are lined with '
            'palaces, and the Town Hall stands on the square itself. The Old Town, a fortress '
            'with towers and a moat, now houses the City Museum. A short walk away, Varaždin '
            'Cemetery is laid out as a park with clipped hedges and is often visited for its '
            'design. The town is pleasant on foot, and each late summer it fills with street '
            'performers during Špancirfest, and in autumn with concerts at the Baroque '
            'Evenings. Trakošćan Castle and the Zagorje hills are within reach by car.'
        ),
        'faqs': [
            {
                'q': 'Is Varaždin worth visiting?',
                'a': 'Yes, for its baroque centre, the Old Town fortress and its festivals. It '
                'suits a day or a night on the way between Zagreb and the Zagorje castles.',
            },
            {
                'q': 'How do I get to Varaždin?',
                'a': 'By road or rail from Zagreb, which is also the nearest major airport '
                '(ZAG). Buses connect Varaždin with Zagreb and the surrounding towns.',
            },
            {
                'q': 'What is there to do in Varaždin?',
                'a': 'Walk the old centre, visit the Old Town fortress and its City Museum, '
                'see the Town Hall and the cathedral, and stroll through Varaždin Cemetery.',
            },
            {
                'q': 'How long should I spend in Varaždin?',
                'a': 'A few hours covers the centre; a full day adds the museum and the cemetery.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'Architecture, short city breaks, festivals'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'Road and rail from Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'architecture lovers',
            'short city breaks',
            'festival visitors',
            'walkers',
            'castle routes',
        ],
        'sections': [
            {
                'heading': 'A baroque town centre',
                'body': 'Much of Varaždin was rebuilt in the baroque style after a fire in '
                '1776, and the result is an unusually unified old town. The palaces around the '
                'main square and the streets leading off it carry the town’s history, and the '
                'Town Hall, one of the older town halls in Croatia, stands on the square. The '
                'centre is small and mostly pedestrian, so a morning on foot is enough to see '
                'the main buildings and to stop in the cafés on the square.',
            },
            {
                'heading': 'The Old Town and the cemetery',
                'body': 'The Old Town is a fortress at the edge of the centre, with towers, '
                'walls and a moat. It houses the Varaždin City Museum, whose collections '
                'cover the town’s history and everyday life. On the other side of the centre, '
                'Varaždin Cemetery was laid out in the early 20th century as a park, with '
                'trimmed hedges and avenues of trees, and it is visited as much for its '
                'landscaping as for its monuments. Both fit comfortably into one day.',
            },
            {
                'heading': 'Festivals and the surrounding country',
                'body': 'Varaždin is known for two events: Špancirfest, a street festival in '
                'late summer, and the Baroque Evenings, a series of concerts in churches and '
                'palaces in autumn. Outside town, the Zagorje hills have castles and '
                'vineyards, and Trakošćan Castle can be reached by car. Zagreb is the nearest '
                'large city and the entry point for most visitors arriving by air.',
            },
        ],
        'external_links': [
            {'label': 'Varaždin — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Vara%C5%BEdin'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 46.3057,
        'longitude': 16.3366,
    },
    {
        'name': 'Trakošćan Castle',
        'slug': 'trakoscan-castle',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A hilltop castle above a small lake in the Zagorje hills, now a museum with '
        'a landscaped park.',
        'description': (
            'Trakošćan stands on a wooded hill above an artificial lake in the hills of '
            'northern Croatia. The castle dates back to the Middle Ages, was restored in the '
            '19th century, and today is a museum of furnished rooms and arms, set in a park '
            'with a path around the lake.'
        ),
        'highlights': [
            'The castle museum and its furnished rooms',
            'Walk around the lake',
            'The castle park',
            'Collection of arms and portraits',
            'Views of the castle from the lake shore',
        ],
        'overview': (
            'Trakošćan Castle sits on a hill in the Zagorje, in the north of Croatia, close to '
            'the Slovenian border. The first fortification here is medieval. From the late '
            '16th century the castle belonged to the Drašković family, who held it for '
            'generations and, in the 19th century, remodelled it in a romantic historicist '
            'style and landscaped the park and the lake below. Today the castle is a museum. '
            'Its rooms are furnished as they were in the family’s time, with portraits, '
            'furniture and a collection of arms. The usual visit is the castle, then a walk '
            'along the path around the lake, with views back up to the walls. It is a half-day '
            'stop on a drive through the Zagorje, often combined with Varaždin or Krapina.'
        ),
        'faqs': [
            {
                'q': 'Is Trakošćan Castle worth visiting?',
                'a': 'Yes, if you like castles and countryside. The museum rooms and the walk '
                'around the lake make an easy half-day visit.',
            },
            {
                'q': 'How do I get to Trakošćan?',
                'a': 'By car from Varaždin or Zagreb; public transport is limited, so check '
                'bus connections in advance. Zagreb (ZAG) is the nearest major airport.',
            },
            {
                'q': 'What is there to do at Trakošćan?',
                'a': 'Visit the castle museum, walk the path around the lake and through the '
                'park, and photograph the castle from the water’s edge.',
            },
            {
                'q': 'How long should I spend at Trakošćan?',
                'a': 'Two to three hours covers the castle and the lake walk.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn'},
            {'label': 'Ideal for', 'value': 'Castles, history, easy walks'},
            {'label': 'Time needed', 'value': 'Two to three hours'},
            {'label': 'Getting there', 'value': 'By car from Varaždin or Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia (Zagorje)'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'castle lovers',
            'history fans',
            'families',
            'easy walkers',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'A castle with a long history',
                'body': 'The fortification at Trakošćan dates to the Middle Ages and guarded '
                'the surrounding valley. In the late 16th century it passed to the Drašković '
                'family, who kept it for generations. In the 19th century they remodelled the '
                'castle in a romantic historicist style, with the look of a fairy-tale '
                'fortress, and laid out the park and lake that now set it off.',
            },
            {
                'heading': 'Inside the museum',
                'body': 'Today the castle is a museum. The rooms are furnished in the style of '
                'the family’s time, and the collection includes family portraits, furniture '
                'and a display of arms. Information is available in several languages. Plan '
                'about an hour inside, longer if you stop for the weapons and the portrait '
                'galleries.',
            },
            {
                'heading': 'The lake and the park',
                'body': 'Below the castle, a path leads around the artificial lake through the '
                'landscaped park. It is flat and easy, and from the far shore you can see the '
                'castle reflected in the water. The setting suits families and anyone who '
                'wants a short walk after the visit. The surrounding Zagorje hills and nearby '
                'Varaždin make it simple to build a day around Trakošćan.',
            },
        ],
        'external_links': [
            {
                'label': 'Trakošćan Castle — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Trakoš%C4%87an_Castle',
            },
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 46.2544,
        'longitude': 15.9400,
    },
    {
        'name': 'Krapina',
        'slug': 'krapina',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A small Zagorje town known for the Neanderthal finds of Hušnjakovo hill and '
        'its museum.',
        'description': (
            'Krapina is a small town in the Zagorje, north of Zagreb. It is known worldwide '
            'for the Neanderthal remains found on nearby Hušnjakovo hill, which are presented '
            'at the Krapina Neanderthal Museum.'
        ),
        'highlights': [
            'Krapina Neanderthal Museum',
            'Hušnjakovo hill site',
            'The old town centre',
            'Birthplace of Ljudevit Gaj',
            'Walks in the Zagorje hills',
        ],
        'overview': (
            'Krapina is a small town in the Hrvatsko Zagorje, in the north of Croatia. It is '
            'best known as the site of one of the richest Neanderthal finds in Europe. In '
            '1899 the geologist and palaeontologist Dragutin Gorjanović-Kramberger began '
            'excavating a rock shelter on Hušnjakovo hill and recovered the remains of many '
            'Neanderthal individuals, thought to be around 130,000 years old. The finds are '
            'the reason the town has a modern museum, the Krapina Neanderthal Museum, which '
            'sets them in the story of human evolution and of the site itself. The old '
            'centre is small and easy to cover on foot, and the town is also linked to the '
            '19th-century Croatian national revival: Ljudevit Gaj, a leader of the Illyrian '
            'movement, was born here.'
        ),
        'faqs': [
            {
                'q': 'Is Krapina worth visiting?',
                'a': 'Yes, mainly for the Neanderthal Museum and the Hušnjakovo hill site. It '
                'fits well into a day through the Zagorje.',
            },
            {
                'q': 'How do I get to Krapina?',
                'a': 'By road from Zagreb, and there are rail and bus connections as well. '
                'Zagreb (ZAG) is the nearest airport.',
            },
            {
                'q': 'What is there to do in Krapina?',
                'a': 'Visit the Krapina Neanderthal Museum, walk to the Hušnjakovo hill site '
                'and explore the small old centre.',
            },
            {
                'q': 'How long should I spend in Krapina?',
                'a': 'Two to three hours covers the museum and the hill; add time if you '
                'combine it with Trakošćan or Kumrovec.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn'},
            {'label': 'Ideal for', 'value': 'Archaeology, families, history'},
            {'label': 'Time needed', 'value': 'Two to three hours'},
            {'label': 'Getting there', 'value': 'Road from Zagreb; also rail and bus'},
            {'label': 'Region', 'value': 'Continental Croatia (Zagorje)'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'archaeology fans',
            'families',
            'history lovers',
            'day trips from Zagreb',
            'museum visitors',
        ],
        'sections': [
            {
                'heading': 'The Neanderthals of Krapina',
                'body': 'In 1899 Dragutin Gorjanović-Kramberger began excavating a rock '
                'shelter on Hušnjakovo hill and recovered the remains of many Neanderthals, '
                'together with stone tools and animal bones. The material is dated to roughly '
                '130,000 years ago and is still studied by researchers. The site made Krapina '
                'a reference point in the study of early humans in Europe.',
            },
            {
                'heading': 'The museum and the hill',
                'body': 'The Krapina Neanderthal Museum stands beside the hill and presents the '
                'finds in the context of human evolution, with reconstructions and displays '
                'built around the excavation. The hill itself, where the shelter was found, '
                'can be visited on foot and gives a sense of the place the Neanderthals '
                'lived in. Allow about two hours for both.',
            },
            {
                'heading': 'The town and the region',
                'body': 'The old centre of Krapina is small, with a few streets, a church and '
                'places for coffee. Ljudevit Gaj, a leading figure of the 19th-century Illyrian '
                'movement, was born here, and the town remembers him. Around Krapina, the '
                'Zagorje hills are dotted with castles, churches and wine cellars, and '
                'Trakošćan and Kumrovec are both a drive away.',
            },
        ],
        'external_links': [
            {'label': 'Krapina — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Krapina'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 46.1608,
        'longitude': 15.8789,
    },
    {
        'name': 'Marija Bistrica',
        'slug': 'marija-bistrica',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'The national shrine of Croatia, a pilgrimage village in the hills north of '
        'Zagreb.',
        'description': (
            'Marija Bistrica is a village in the Zagorje hills north of Zagreb and the '
            'national shrine of Croatia. Pilgrims come to the church of the Mother of God of '
            'Bistrica, which holds a carved statue of the Virgin, and to the Calvary on the '
            'hill above the village.'
        ),
        'highlights': [
            'The shrine church of the Mother of God of Bistrica',
            'The statue of the Virgin',
            'The open-air chapel at the church',
            'The Calvary on the hill',
            'Walks in the Zagorje hills',
        ],
        'overview': (
            'Marija Bistrica is a village in the hills of the Zagorje, north of Zagreb, and is '
            'regarded as the national shrine of Croatia. Its church holds a carved statue of the '
            'Virgin, the Mother of God of Bistrica, a place of pilgrimage for centuries. Large '
            'groups of pilgrims arrive on feast days, and the village has an open-air chapel '
            'beside the church for services. Above the village, the Calvary is a path with '
            'stations of the cross that climbs the hill through the woods, and it gives wide '
            'views over the Zagorje. For visitors who are not on a pilgrimage, the village is a '
            'quiet stop on a route that also takes in Krapina, Trakošćan and the wine '
            'villages. Visitors are asked to dress and behave respectfully in the church.'
        ),
        'faqs': [
            {
                'q': 'Is Marija Bistrica worth visiting?',
                'a': 'Yes, if you are interested in pilgrimage traditions or want a quiet stop '
                'in the Zagorje hills north of Zagreb.',
            },
            {
                'q': 'How do I get to Marija Bistrica?',
                'a': 'By road from Zagreb; buses also run from the capital. Zagreb (ZAG) is '
                'the nearest airport.',
            },
            {
                'q': 'What is there to do in Marija Bistrica?',
                'a': 'Visit the shrine church, walk the Calvary path up the hill, and take in '
                'the views over the Zagorje.',
            },
            {
                'q': 'How long should I spend in Marija Bistrica?',
                'a': 'One to two hours covers the church and a walk on the Calvary.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn; busy on feast days'},
            {'label': 'Ideal for', 'value': 'Pilgrimage, quiet walks, culture'},
            {'label': 'Time needed', 'value': 'One to two hours'},
            {'label': 'Getting there', 'value': 'Road or bus from Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia (Zagorje)'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'pilgrims',
            'quiet walks',
            'culture lovers',
            'day trips from Zagreb',
            'scenic views',
        ],
        'sections': [
            {
                'heading': 'The shrine',
                'body': 'The church in Marija Bistrica is the national shrine of Croatia and '
                'keeps a carved statue of the Virgin, known as the Mother of God of Bistrica. '
                'The statue has drawn pilgrims for centuries. The church is a working place of '
                'worship, so visits should be quiet and respectful, and services may limit '
                'access at times.',
            },
            {
                'heading': 'The Calvary',
                'body': 'A path with stations of the cross climbs the hill above the village, '
                'through the woods, to a viewpoint. The walk is steady rather than steep and '
                'takes a reasonable amount of time at a gentle pace. It is used by pilgrims '
                'and by walkers who simply want the view over the Zagorje hills and the '
                'village below.',
            },
            {
                'heading': 'In the surrounding hills',
                'body': 'Marija Bistrica lies on the way between Zagreb and the castles and '
                'museums of the Zagorje. Many visitors fit it between Krapina, Kumrovec and '
                'Trakošćan, and the hills around the village have farms and small cellars. A '
                'visit works well as part of a day trip by car from Zagreb.',
            },
        ],
        'external_links': [
            {
                'label': 'Marija Bistrica — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Marija_Bistrica',
            },
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 46.0,
        'longitude': 15.9667,
    },
    {
        'name': 'Kumrovec',
        'slug': 'kumrovec',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A village on the Sutla river near the Slovenian border, with an open-air '
        'ethnographic museum.',
        'description': (
            'Kumrovec is a village on the Sutla river, on the border with Slovenia. It is the '
            'birthplace of Josip Broz Tito and the home of the Staro selo (Old Village) '
            'museum, an open-air collection of restored rural houses from the Zagorje.'
        ),
        'highlights': [
            'Staro selo (Old Village) open-air museum',
            'The house where Josip Broz Tito was born',
            'Restored Zagorje rural houses',
            'Traditional crafts on show',
            'The Sutla river valley',
        ],
        'overview': (
            'Kumrovec is a village on the Sutla river, which forms the border between Croatia '
            'and Slovenia. Josip Broz Tito, later the leader of socialist Yugoslavia, was born '
            'here in 1892. The village’s main attraction is the Staro selo (Old Village) '
            'museum, an open-air ethnographic museum made up of restored traditional houses '
            'along the village street. The houses show how people in the Zagorje lived and '
            'worked, with furnished interiors, tools and displays of local crafts. The house '
            'where Tito was born is part of the museum. The setting is rural and green, with '
            'orchards and hills around, and it is an easy stop on a trip through the Zagorje, '
            'close to Krapina and Marija Bistrica.'
        ),
        'faqs': [
            {
                'q': 'Is Kumrovec worth visiting?',
                'a': 'Yes, for the open-air museum and a look at traditional rural life in '
                'the Zagorje.',
            },
            {
                'q': 'How do I get to Kumrovec?',
                'a': 'By road from Zagreb or Krapina. Zagreb (ZAG) is the nearest airport.',
            },
            {
                'q': 'What is there to do in Kumrovec?',
                'a': 'Walk through the Staro selo museum, see the restored houses and craft '
                'displays, and visit the house where Tito was born.',
            },
            {
                'q': 'How long should I spend in Kumrovec?',
                'a': 'Around two hours covers the open-air museum.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn'},
            {'label': 'Ideal for', 'value': 'Open-air museums, history, families'},
            {'label': 'Time needed', 'value': 'About two hours'},
            {'label': 'Getting there', 'value': 'By road from Zagreb or Krapina'},
            {'label': 'Region', 'value': 'Continental Croatia (Zagorje)'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'history lovers',
            'families',
            'museum visitors',
            'rural culture',
            'day trips from Zagreb',
        ],
        'sections': [
            {
                'heading': 'The Staro selo museum',
                'body': 'Staro selo is an open-air ethnographic museum set along the village '
                'street. Its restored houses, built in the traditional style of the Zagorje, '
                'are furnished as homes and workshops of the past. Displays show tools, '
                'household objects and local crafts, and some craft traditions are '
                'demonstrated. It gives a clear picture of rural life in the region.',
            },
            {
                'heading': 'Tito’s birthplace',
                'body': 'Josip Broz Tito was born in Kumrovec in 1892, and the house where he '
                'was born is part of the museum complex. The village is therefore also a '
                'place of historical interest for those studying 20th-century Yugoslavia. '
                'The exhibition is presented as part of the village’s ethnographic story.',
            },
            {
                'heading': 'The valley and the border',
                'body': 'Kumrovec lies in the valley of the Sutla river, which marks the '
                'border with Slovenia. The countryside around it is quiet and agricultural, '
                'with orchards, small vineyards and wooded hills. It combines easily with '
                'Krapina, Marija Bistrica and Trakošćan on a driving route through the '
                'Zagorje.',
            },
        ],
        'external_links': [
            {'label': 'Kumrovec — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Kumrovec'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 46.0786,
        'longitude': 15.6767,
    },
    {
        'name': 'Karlovac',
        'slug': 'karlovac',
        'region': 'continental',
        'place_type': 'cities',
        'featured': False,
        'summary': 'A city on four rivers with a star-shaped old centre, south-west of Zagreb.',
        'description': (
            'Karlovac was founded in 1579 as a star-shaped fortress town and sits where the '
            'Kupa, Korana, Mrežnica and Dobra rivers meet. Its geometric old centre, '
            'riverside walks and long brewing tradition make it an easy stop between Zagreb '
            'and the coast.'
        ),
        'highlights': [
            'The star-shaped old centre (Zvijezda)',
            'Riverside walks along the Kupa and Korana',
            'Karlovac City Museum',
            'Aquatika freshwater aquarium',
            'The Mrežnica and Korana rivers nearby',
        ],
        'overview': (
            'Karlovac was founded in 1579 by Archduke Charles II of Austria as a fortress '
            'against the Ottoman advance, and its centre still follows the plan of a six-pointed '
            'star with a grid of streets inside. Four rivers meet around the city: the Kupa, '
            'the Korana, the Mrežnica and the Dobra, which is why it is often called the city '
            'of four rivers. The old centre, called Zvijezda (the Star), has a central square, '
            'baroque and later buildings and the remains of the earthworks, now parkland. '
            'Karlovac is known for its beer tradition, with a brewery in town, and for the '
            'rivers that offer walks, swimming spots and canoeing nearby. It lies south-west of '
            'Zagreb on the main road to the coast, which makes it an easy stop.'
        ),
        'faqs': [
            {
                'q': 'Is Karlovac worth visiting?',
                'a': 'Yes, for a short stop: the star-shaped centre, the rivers and the '
                'freshwater aquarium. It is on the road between Zagreb and the coast.',
            },
            {
                'q': 'How do I get to Karlovac?',
                'a': 'By road or rail from Zagreb, about an hour away. Zagreb (ZAG) is the '
                'nearest airport.',
            },
            {
                'q': 'What is there to do in Karlovac?',
                'a': 'Walk the old star-shaped centre, follow the river promenades, visit the '
                'city museum and the Aquatika aquarium, and try canoeing on the Mrežnica or '
                'Korana.',
            },
            {
                'q': 'How long should I spend in Karlovac?',
                'a': 'A few hours cover the centre and a river walk; a full day allows an '
                'excursion to the Mrežnica or Korana.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'Short stops, river walks, canoeing'},
            {'label': 'Time needed', 'value': 'A few hours to a day'},
            {'label': 'Getting there', 'value': 'Road and rail from Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'road trips',
            'river walks',
            'canoeing',
            'families',
            'short stops',
        ],
        'sections': [
            {
                'heading': 'A fortress town with a star plan',
                'body': 'Karlovac was laid out in 1579 as a planned fortress town, with six '
                'bastions forming a star and straight streets inside. The pattern is still '
                'visible on a map, and the old centre, Zvijezda, keeps its main square with '
                'its surrounding buildings. The former defensive ditches and earthworks are '
                'now green space, which gives the centre its open feel.',
            },
            {
                'heading': 'City of four rivers',
                'body': 'The Kupa, Korana, Mrežnica and Dobra rivers all flow around Karlovac. '
                'The Kupa and Korana pass right by the centre, and walks along their banks '
                'are part of daily life in the city. Upstream, the Korana and Mrežnica are '
                'known for clear water and for canoeing and kayaking, and several small '
                'villages along them have bridges and mills.',
            },
            {
                'heading': 'Beer, museums and the aquarium',
                'body': 'Karlovac has a long brewing tradition, and its beer is known '
                'throughout Croatia. The city museum is in the old centre, and Aquatika, a '
                'freshwater aquarium, presents the fish and habitats of Croatian rivers. In '
                'late summer the city hosts a beer festival. Karlovac is on the road to the '
                'coast and the national parks of Lika.',
            },
        ],
        'external_links': [
            {'label': 'Karlovac — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Karlovac'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.4870,
        'longitude': 15.5478,
    },
    {
        'name': 'Osijek',
        'slug': 'osijek',
        'region': 'continental',
        'place_type': 'cities',
        'featured': False,
        'summary': 'The main city of Slavonia, on the Drava, with a baroque fortress quarter and '
        'a riverside promenade.',
        'description': (
            'Osijek is the largest city of Slavonia, in the east of Croatia, on the Drava '
            'river. It has a baroque fortress quarter called Tvrđa, a tall neo-Gothic '
            'co-cathedral, parks and a long riverside promenade, and it is the gateway to '
            'Kopački Rit Nature Park.'
        ),
        'highlights': [
            'Tvrđa baroque fortress quarter',
            'Co-cathedral of St Peter and St Paul',
            'The Drava riverside promenade',
            'Osijek Zoo',
            'Day trip to Kopački Rit Nature Park',
        ],
        'overview': (
            'Osijek is the main city of Slavonia and sits on the right bank of the Drava, in '
            'the flat farmland of eastern Croatia. Its best-known district is Tvrđa, a baroque '
            'fortress built in the 18th century when the area belonged to the Habsburg '
            'monarchy, with a main square, barracks, churches and the remains of its walls. '
            'It is now a quarter of cafés, museums and university buildings. Elsewhere in the '
            'city, the neo-Gothic co-cathedral of St Peter and St Paul has a bell tower that '
            'is visible from far away. A long promenade follows the Drava, with parks and a '
            'pedestrian bridge. Osijek has an airport (OSI), which makes it the natural base '
            'for eastern Croatia, and the Kopački Rit wetlands, Đakovo and Vukovar are all '
            'within a day trip.'
        ),
        'faqs': [
            {
                'q': 'Is Osijek worth visiting?',
                'a': 'Yes, as a base for Slavonia and Baranja: it has a baroque fortress '
                'quarter, riverside walks and good access to Kopački Rit.',
            },
            {
                'q': 'How do I get to Osijek?',
                'a': 'Osijek Airport (OSI) has limited flights; most visitors come by road or '
                'rail from Zagreb. Buses link Osijek with Đakovo, Vukovar and the region.',
            },
            {
                'q': 'What is there to do in Osijek?',
                'a': 'Walk Tvrđa, see the co-cathedral, follow the Drava promenade, visit the '
                'zoo and take a day trip to Kopački Rit.',
            },
            {
                'q': 'How long should I spend in Osijek?',
                'a': 'A day covers the main sights; two or three days allow trips to Kopački '
                'Rit, Đakovo and Vukovar.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'April to October'},
            {'label': 'Ideal for', 'value': 'City breaks, Slavonia base, nature trips'},
            {'label': 'Time needed', 'value': 'One to three days'},
            {'label': 'Getting there', 'value': 'Osijek Airport; road and rail from Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia (Slavonia)'},
            {'label': 'Nearest airport', 'value': 'Osijek (OSI)'},
        ],
        'good_for': [
            'city breaks',
            'architecture lovers',
            'nature day trips',
            'cyclists',
            'regional exploring',
        ],
        'sections': [
            {
                'heading': 'Tvrđa, the fortress quarter',
                'body': 'Tvrđa was built in the 18th century as a star-shaped Habsburg fortress, '
                'and it is the best-preserved baroque ensemble in the city. Its main square, '
                'with a plague column in the middle, is surrounded by former military '
                'buildings, and the Tvrđa quarter now has museums, galleries, cafés and part '
                'of the university. Walking the cobbled streets and along the old ramparts '
                'takes a couple of hours.',
            },
            {
                'heading': 'The rest of the city',
                'body': 'Beyond Tvrđa, the upper town has the neo-Gothic co-cathedral of St '
                'Peter and St Paul, whose tower is one of the tallest in Croatia. Parks, '
                'squares and 19th-century buildings give the centre a Central European '
                'feel. The Drava promenade runs for several kilometres, past a pedestrian '
                'bridge, and is popular with walkers and cyclists. Osijek also has a zoo.',
            },
            {
                'heading': 'A base for eastern Croatia',
                'body': 'Osijek is the transport hub for the east, with an airport, rail and bus '
                'connections. Kopački Rit Nature Park, a floodplain wetland at the meeting of '
                'the Danube and Drava, is a short drive away, and Đakovo, Vukovar and Ilok '
                'can each be visited in a day. The area is also known for its wine, and '
                'Slavonian and Baranja cooking.',
            },
        ],
        'external_links': [
            {'label': 'Osijek — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Osijek'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.5550,
        'longitude': 18.6955,
    },
    {
        'name': 'Kopački Rit Nature Park',
        'slug': 'kopacki-rit-nature-park',
        'region': 'continental',
        'place_type': 'lakes',
        'featured': False,
        'summary': 'A floodplain wetland where the Drava meets the Danube, known for birdlife '
        'and boat trips.',
        'description': (
            'Kopački Rit is a large floodplain wetland near Osijek, in the angle between the '
            'Danube and the Drava. Its channels, lakes, reedbeds and flooded forests shelter '
            'many birds and other wildlife, and it is explored mainly by boat and on foot.'
        ),
        'highlights': [
            'Boat trips on the lakes and channels',
            'Birdwatching in the wetland',
            'Flooded forests and reedbeds',
            'Walking and cycling trails',
            'Wildlife of the floodplain',
        ],
        'overview': (
            'Kopački Rit lies in the north-east of Croatia, in the area of Baranja, between '
            'the Danube and the Drava rivers. The park is a floodplain: in spring and early '
            'summer the rivers rise and cover much of it with water, leaving a mosaic of lakes, '
            'channels, reedbeds and willow forest, which shrinks again later in the year. '
            'This changing landscape supports a wealth of wildlife and the park is best known '
            'for its birds, including many species of waterbirds. It is a Ramsar wetland of '
            'international importance. Visitors usually come for a boat trip along the '
            'channels, a walk on the marked trails, or a cycling ride along the dykes, and '
            'the park’s visitor centre, in the village of Kopačevo, helps with orientation. It is a short drive from '
            'Osijek, so most people visit on a day trip.'
        ),
        'faqs': [
            {
                'q': 'Is Kopački Rit worth visiting?',
                'a': 'Yes, especially for birdwatchers and anyone who enjoys wetland '
                'landscapes. A boat trip is the usual way to see it.',
            },
            {
                'q': 'How do I get to Kopački Rit?',
                'a': 'By car from Osijek, which is a short drive away. Osijek Airport (OSI) '
                'is the nearest airport. Public transport is limited, so check ahead.',
            },
            {
                'q': 'What is there to do in Kopački Rit?',
                'a': 'Take a boat trip, walk the trails, look for birds and cycle along the dykes.',
            },
            {
                'q': 'How long should I spend in Kopački Rit?',
                'a': 'Half a day is enough for a boat trip and a walk; birdwatchers may want '
                'a full day.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to early autumn; water levels vary'},
            {'label': 'Ideal for', 'value': 'Birdwatching, boat trips, nature photography'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'By car from Osijek'},
            {'label': 'Region', 'value': 'Continental Croatia (Baranja)'},
            {'label': 'Nearest airport', 'value': 'Osijek (OSI)'},
        ],
        'good_for': [
            'birdwatchers',
            'nature lovers',
            'photographers',
            'cyclists',
            'families',
        ],
        'sections': [
            {
                'heading': 'A floodplain that changes with the water',
                'body': 'Kopački Rit is shaped by the rise and fall of the Danube and the '
                'Drava. When the water is high, in spring and early summer, much of the park '
                'is flooded and boats can reach areas that are dry later. As the water falls '
                'the landscape becomes a patchwork of lakes, marsh, meadow and woodland. The '
                'experience therefore differs from one season to the next.',
            },
            {
                'heading': 'Birds and wildlife',
                'body': 'The park is a protected wetland, recognised under the Ramsar '
                'convention, and it is known for its birdlife, including many waterbirds that '
                'nest or feed there. Other wildlife includes deer and other mammals of the '
                'riverside forest, as well as fish and amphibians. Birdwatchers often bring '
                'binoculars and visit in the early morning.',
            },
            {
                'heading': 'Visiting the park',
                'body': 'Most visitors start at the visitor centre in Kopačevo, where boat trips '
                'and guided visits can be arranged. Marked trails and dyke paths allow walking '
                'and cycling, and the nearby villages of Baranja serve local dishes. Osijek '
                'is the nearest city and the usual base. Bring water, sun protection and, in '
                'warm months, insect repellent.',
            },
        ],
        'external_links': [
            {
                'label': 'Kopački Rit — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Kopa%C4%8Dki_Rit',
            },
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.6000,
        'longitude': 18.8000,
    },
    {
        'name': 'Vukovar',
        'slug': 'vukovar',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A Danube town in eastern Croatia, remembered for the siege of 1991, with '
        'museums and a rebuilt baroque centre.',
        'description': (
            'Vukovar lies on the right bank of the Danube, in the east of Croatia. It was '
            'besieged for three months in 1991, and its memorial sites, the water tower and '
            'the Ovčara memorial recall that time. The town also has a baroque centre, Eltz '
            'Manor and the nearby Vučedol Culture Museum.'
        ),
        'highlights': [
            'The water tower, a symbol of the town',
            'Memorial Cemetery of the Victims of the Homeland War',
            'Eltz Manor and the City Museum',
            'Vučedol Culture Museum',
            'The Danube promenade',
        ],
        'overview': (
            'Vukovar is a town on the right bank of the Danube, in the far east of Croatia, '
            'close to the border with Serbia. In 1991, during the war, it was under siege for '
            'about three months and was heavily destroyed. Remembrance is a part of any visit. '
            'The water tower, left damaged and now restored as a memorial, has become the '
            'symbol of the town, and the Memorial Cemetery of the Victims of the Homeland War '
            'and the Ovčara memorial are places of remembrance. Alongside this, Vukovar has '
            'been rebuilt: Eltz Manor, in the baroque centre, houses the City Museum, and a '
            'promenade runs along the Danube. Just outside town, the Vučedol Culture Museum '
            'presents a prehistoric culture of the Copper Age, known for its pottery and for a '
            'ceramic bird known as the Vučedol dove. Visitors should come with respect, '
            'and many choose a guide to explain the history.'
        ),
        'faqs': [
            {
                'q': 'Is Vukovar worth visiting?',
                'a': 'Yes, for its recent history, its museums and its Danube setting. It is a '
                'place for reflection as much as sightseeing.',
            },
            {
                'q': 'How do I get to Vukovar?',
                'a': 'By road or rail from Zagreb or Osijek. Osijek Airport (OSI) is the '
                'nearest airport.',
            },
            {
                'q': 'What is there to do in Vukovar?',
                'a': 'See the water tower and the memorial sites, visit Eltz Manor and the '
                'Vučedol Culture Museum, and walk along the Danube.',
            },
            {
                'q': 'How long should I spend in Vukovar?',
                'a': 'Half a day to a day, depending on how many museums and memorials you visit.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn; 18 November is the day of remembrance',
            },
            {'label': 'Ideal for', 'value': 'History, museums, Danube walks'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'Road and rail from Zagreb or Osijek'},
            {'label': 'Region', 'value': 'Continental Croatia (Slavonia)'},
            {'label': 'Nearest airport', 'value': 'Osijek (OSI)'},
        ],
        'good_for': [
            'history lovers',
            'museum visitors',
            'archaeology fans',
            'thoughtful travellers',
            'Danube walks',
        ],
        'sections': [
            {
                'heading': 'Remembrance and the water tower',
                'body': 'In 1991 Vukovar was besieged for about three months and left in ruins. '
                'The town’s water tower, hit by many shells, was kept in its damaged state for '
                'years as a memorial and has since been restored; it now stands as the '
                'symbol of Vukovar. The Memorial Cemetery of the Victims of the Homeland War '
                'and the Ovčara memorial are solemn sites, and each year on 18 November the '
                'town marks the anniversary of the fall of Vukovar with a remembrance walk.',
            },
            {
                'heading': 'Museums and the old centre',
                'body': 'Eltz Manor, a baroque mansion in the centre, houses the Vukovar City '
                'Museum, with collections on the town’s history. Around it the centre has been '
                'rebuilt, and a promenade follows the Danube. A few kilometres away, the Vučedol '
                'Culture Museum presents the finds of an archaeological site of the Copper '
                'Age, including the pottery for which the Vučedol culture is known.',
            },
            {
                'heading': 'Planning a visit',
                'body': 'Vukovar is about an hour from Osijek and can be visited in a day from '
                'there, or combined with Ilok farther down the Danube. A guide can help to '
                'explain the history and the memorial sites. Visitors are asked to be '
                'respectful at memorials. Local restaurants serve Slavonian dishes, and the '
                'Danube setting is pleasant for an evening walk.',
            },
        ],
        'external_links': [
            {'label': 'Vukovar — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Vukovar'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.3513,
        'longitude': 18.9987,
    },
    {
        'name': 'Ilok',
        'slug': 'ilok',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'The easternmost town in Croatia, on the Danube, with a walled old town and '
        'wine cellars.',
        'description': (
            'Ilok is the easternmost town in Croatia, on a hill above the Danube. Its walled '
            'old town includes a fortress, a Franciscan monastery and the Odescalchi castle, '
            'and it is known for the wines of the surrounding hills.'
        ),
        'highlights': [
            'The walled old town and the Odescalchi castle',
            'Franciscan monastery and church',
            'Ilok wine cellars and tastings',
            'Vineyards on the hills above the Danube',
            'Views over the Danube',
        ],
        'overview': (
            'Ilok sits on a hill on the right bank of the Danube, at the eastern tip of '
            'Croatia, facing Serbia across the river. The old town is enclosed by medieval '
            'walls, with towers and gates, and inside are a castle that later belonged to the '
            'Odescalchi family, a Franciscan monastery and churches. The Franciscan church '
            'holds the tomb of St John of Capistrano, who died in Ilok in 1456. The town is '
            'also known as a wine place: vineyards cover the slopes around it, and the cellars '
            'beneath the old town, run by the local winery, are open to visitors '
            'for tastings. The grape variety traditionally associated with '
            'the area is Traminac. Ilok is usually reached from Osijek or Vukovar, and an '
            'overnight stay suits those who want to taste the wines.'
        ),
        'faqs': [
            {
                'q': 'Is Ilok worth visiting?',
                'a': 'Yes, for its walled old town, the Danube views and the local wines.',
            },
            {
                'q': 'How do I get to Ilok?',
                'a': 'By road from Vukovar or Osijek. Osijek Airport (OSI) is the nearest '
                'airport, and buses run from the larger towns.',
            },
            {
                'q': 'What is there to do in Ilok?',
                'a': 'Walk the old town and its walls, visit the castle and the Franciscan '
                'church, taste wine in the cellars and look out over the Danube.',
            },
            {
                'q': 'How long should I spend in Ilok?',
                'a': 'Half a day covers the old town and a tasting; stay overnight if you want '
                'to explore the vineyards.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn; the grape harvest in early autumn'},
            {'label': 'Ideal for', 'value': 'Wine, history, quiet breaks'},
            {'label': 'Time needed', 'value': 'Half a day to overnight'},
            {'label': 'Getting there', 'value': 'By road from Vukovar or Osijek'},
            {'label': 'Region', 'value': 'Continental Croatia (Syrmia)'},
            {'label': 'Nearest airport', 'value': 'Osijek (OSI)'},
        ],
        'good_for': [
            'wine lovers',
            'history fans',
            'quiet breaks',
            'Danube views',
            'couples',
        ],
        'sections': [
            {
                'heading': 'The walled old town',
                'body': 'Ilok’s old town is surrounded by walls and towers dating from the '
                'Middle Ages, and the streets inside climb the hill to the castle. After the '
                'Ottoman period, the castle passed to the Odescalchi family. Today part of it '
                'houses the town museum. Walking the walls gives views across the Danube and '
                'the plain on the Serbian side.',
            },
            {
                'heading': 'The Franciscan monastery',
                'body': 'The Franciscan monastery and church in the old town hold the tomb of St '
                'John of Capistrano, a Franciscan preacher who died in Ilok in 1456 and is '
                'remembered here. The monastery is a working religious house, so visits '
                'should be respectful. Together with the castle it is the historical heart '
                'of the town.',
            },
            {
                'heading': 'Wine in the hills',
                'body': 'The slopes around Ilok are planted with vines, and the town is one of '
                'the wine centres of eastern Croatia. Cellars under the old town are open '
                'for tours and tastings, and small family producers sell wine in the '
                'surrounding villages. Traminac is the variety most often associated with '
                'Ilok, alongside Graševina and other whites. Tastings are best booked in '
                'advance.',
            },
        ],
        'external_links': [
            {'label': 'Ilok — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Ilok'},
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.2256,
        'longitude': 19.3736,
    },
    {
        'name': 'Đakovo',
        'slug': 'dakovo',
        'region': 'continental',
        'place_type': 'cultural',
        'featured': False,
        'summary': 'A Slavonian town known for its twin-towered cathedral, its Lipizzaner stud '
        'farm and an embroidery festival.',
        'description': (
            'Đakovo is a town in Slavonia, south of Osijek. Its red-brick cathedral of St '
            'Peter, built in the 19th century under Bishop Strossmayer, dominates the town. '
            'Đakovo is also known for its Lipizzaner stud farm and for the Đakovački vezovi '
            'folk festival every summer.'
        ),
        'highlights': [
            'Cathedral of St Peter',
            'Lipizzaner stud farm',
            'Strossmayer park and the old centre',
            'Đakovački vezovi festival',
            'Slavonian food and folklore',
        ],
        'overview': (
            'Đakovo is a town in the Slavonian plain, about 35 km south of Osijek. Its '
            'landmark is the cathedral of St Peter, a red-brick church in the neo-Romanesque '
            'style with two tall towers, built between 1866 and 1882 on the initiative of '
            'Bishop Josip Juraj Strossmayer, a leading figure of 19th-century Croatia. The '
            'bishop’s legacy also shapes the town centre and its parks. Đakovo is known '
            'for its Lipizzaner horses: the stud farm here breeds the white horses famous for '
            'classical riding, and visitors can see them in the paddocks and, at times, in '
            'riding displays. Each summer, in early July, the Đakovački vezovi festival '
            'brings folk costume, embroidery, song and dance to the streets. Combined with '
            'Osijek, Đakovo makes a good day trip in Slavonia.'
        ),
        'faqs': [
            {
                'q': 'Is Đakovo worth visiting?',
                'a': 'Yes, for the cathedral, the Lipizzaner horses and the folk festival in '
                'early July.',
            },
            {
                'q': 'How do I get to Đakovo?',
                'a': 'By road or rail from Osijek or Zagreb. Osijek Airport (OSI) is the '
                'nearest airport.',
            },
            {
                'q': 'What is there to do in Đakovo?',
                'a': 'See the cathedral, visit the Lipizzaner stud farm, walk through the old '
                'centre and the park, and, in July, enjoy the Đakovački vezovi festival.',
            },
            {
                'q': 'How long should I spend in Đakovo?',
                'a': 'Half a day covers the cathedral, the centre and the horses.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring to autumn; early July for the festival'},
            {'label': 'Ideal for', 'value': 'Architecture, horses, folk culture'},
            {'label': 'Time needed', 'value': 'Half a day'},
            {'label': 'Getting there', 'value': 'Road and rail from Osijek or Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia (Slavonia)'},
            {'label': 'Nearest airport', 'value': 'Osijek (OSI)'},
        ],
        'good_for': [
            'horse lovers',
            'architecture fans',
            'folk culture',
            'day trips from Osijek',
            'families',
        ],
        'sections': [
            {
                'heading': 'The cathedral of St Peter',
                'body': 'The cathedral was built between 1866 and 1882 for Bishop '
                'Strossmayer, who wanted a major church for his diocese. Its red brick, '
                'neo-Romanesque style and two tall towers make it visible from across the '
                'surrounding plain. Inside, wall paintings cover the nave and the '
                'apse. It is an active church, so check access around services.',
            },
            {
                'heading': 'Lipizzaner horses',
                'body': 'The Đakovo stud farm breeds Lipizzaners, the white horses known for '
                'classical riding. The stable and the paddocks are open to visitors, and '
                'displays or events are sometimes held. The farm has been part of the '
                'town’s life for a long time, and the horses are a point of local pride. '
                'They can be seen in an hour or so.',
            },
            {
                'heading': 'Đakovački vezovi',
                'body': 'Every year in early July the town hosts Đakovački vezovi, a folk '
                'festival named after the region’s embroidery. Groups from across Croatia '
                'and beyond wear traditional costume, sing, dance and take part in a parade. '
                'Embroidery and other crafts are displayed. The festival is one of the '
                'main folklore events in Slavonia.',
            },
        ],
        'external_links': [
            {
                'label': 'Đakovo — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/%C4%90akovo',
            },
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.3106,
        'longitude': 18.4100,
    },
    {
        'name': 'Lonjsko Polje Nature Park',
        'slug': 'lonjsko-polje-nature-park',
        'region': 'continental',
        'place_type': 'lakes',
        'featured': False,
        'summary': 'A large Sava floodplain of wet meadows, oak forest and wooden villages, '
        'known for storks and grazing horses.',
        'description': (
            'Lonjsko Polje is a vast floodplain of the Sava river, south-east of Zagreb. '
            'Its wet meadows and oak forests host many birds, especially white storks, and '
            'the traditional wooden villages of the area, such as Čigoć, are part of what the '
            'park protects.'
        ),
        'highlights': [
            'Čigoć, a village of nesting storks',
            'Traditional wooden houses',
            'Wet meadows and oak forests',
            'Birdwatching',
            'Posavina horses and Turopolje pigs',
        ],
        'overview': (
            'Lonjsko Polje lies along the Sava river in central Croatia, south-east of Zagreb, '
            'and is one of the largest protected wetlands in the Danube basin. Its floods '
            'fill the meadows and forests every year, a rhythm that local people have lived '
            'with for centuries. The villages of the area, among them Čigoć and Krapje, are '
            'built of oak timber on raised ground, with wooden houses and barns in traditional '
            'style, and are protected as heritage. Čigoć is known as a village for its white '
            'storks, which nest on the rooftops in spring and summer. The park is also a '
            'place for grazing livestock, including the Posavina horse and the Turopolje pig, '
            'both local breeds. It is a Ramsar wetland of international importance. '
            'Visitors come for birdwatching, walks, bicycle rides and boat trips, and there '
            'are visitor centres in the villages.'
        ),
        'faqs': [
            {
                'q': 'Is Lonjsko Polje worth visiting?',
                'a': 'Yes, especially for birdwatching, traditional wooden villages and a '
                'quiet landscape close to Zagreb.',
            },
            {
                'q': 'How do I get to Lonjsko Polje?',
                'a': 'By car from Zagreb, which takes a little over an hour; public transport '
                'is limited. Zagreb (ZAG) is the nearest airport.',
            },
            {
                'q': 'What is there to do in Lonjsko Polje?',
                'a': 'Watch birds, walk or cycle on the dykes, visit the wooden villages such '
                'as Čigoć, and take a boat or cart trip when it is offered.',
            },
            {
                'q': 'How long should I spend in Lonjsko Polje?',
                'a': 'A half-day visit covers a village and a walk; birdwatchers may want a '
                'full day or an overnight stay.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and summer for storks; autumn and winter for floods',
            },
            {'label': 'Ideal for', 'value': 'Birdwatching, rural heritage, quiet walks'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {'label': 'Getting there', 'value': 'By car from Zagreb'},
            {'label': 'Region', 'value': 'Continental Croatia (Posavina)'},
            {'label': 'Nearest airport', 'value': 'Zagreb (ZAG)'},
        ],
        'good_for': [
            'birdwatchers',
            'nature lovers',
            'photographers',
            'cyclists',
            'rural heritage',
        ],
        'sections': [
            {
                'heading': 'A floodplain shaped by the Sava',
                'body': 'Lonjsko Polje is a wide floodplain of the Sava and its tributaries. '
                'When the river rises, usually in autumn and spring, water covers the '
                'meadows and forests, and the area becomes a shallow wetland. The water '
                'retreats later and leaves rich grassland. This cycle has shaped the '
                'landscape, its wildlife and the way people live in it.',
            },
            {
                'heading': 'Villages and livestock',
                'body': 'The traditional villages here, such as Čigoć and Krapje, are built of '
                'oak timber on raised ground, with houses, barns and storehouses in the old '
                'Posavina style. Čigoć is known for its white storks, which nest on the '
                'rooftops in spring and summer. Local breeds graze the meadows, among them '
                'the Posavina horse and the Turopolje pig.',
            },
            {
                'heading': 'Visiting the park',
                'body': 'The park has visitor centres in several villages, where guided '
                'visits, boat trips and walks can be arranged. Marked paths and dykes allow '
                'walking and cycling, and some guesthouses offer local food. The best time '
                'for storks is spring and summer; in other seasons the landscape of flooded '
                'meadows is the draw. Take water, sun protection and insect repellent.',
            },
        ],
        'external_links': [
            {
                'label': 'Lonjsko Polje — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Lonjsko_Polje',
            },
            {'label': 'Croatian National Tourist Board', 'url': 'https://croatia.hr/en-gb'},
        ],
        'latitude': 45.3500,
        'longitude': 16.8000,
    },
]
