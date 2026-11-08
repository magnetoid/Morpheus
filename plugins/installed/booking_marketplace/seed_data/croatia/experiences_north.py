"""Croatia experiences, batch 1: Istria, Kvarner, Zagreb and continental Croatia.

Each entry is a real activity at a real public place (towns, national and nature parks,
museums, UNESCO sites). The host is the store itself, so no operator, winery, restaurant,
boat company or hotel is named. Prices are typical 2026 per-person market prices in EUR.
No ratings, reviews, "was" prices or bestseller flags.
"""

from __future__ import annotations

_FAQ_WEATHER = {
    'q': 'What happens if the weather is bad?',
    'a': 'If conditions make the experience unsafe, you are offered a free reschedule or a '
    'full refund. You are told at least 12 hours before the start time.',
}
_FAQ_PICKUP = {
    'q': 'Is hotel pickup included?',
    'a': "Only if listed under What's included. Otherwise the exact meeting point is "
    'confirmed with your booking.',
}
_FAQ_KIDS = {
    'q': 'Is this suitable for children?',
    'a': 'Families are welcome. Mention the ages in your party when booking so the host can '
    'confirm the minimum age.',
}
_FAQ_FITNESS = {
    'q': 'How fit do I need to be?',
    'a': 'A moderate fitness level is enough. The guide sets the pace with the group.',
}
_FAQ_SWIM = {
    'q': 'Do I need to be able to swim?',
    'a': 'Basic swimming ability is required. Life jackets are provided and worn on the water.',
}
_FAQ_SEASON = {
    'q': 'When does this run?',
    'a': 'It runs seasonally, weather permitting. The dates open for booking show the '
    'current season.',
}
_FAQ_DRINK = {
    'q': 'Can I take part if I am driving?',
    'a': 'Yes. Tastings are small and you can spit or skip any pour. Please arrange a '
    'designated driver or transfer if you plan to taste everything.',
}

_EN_HR = ['English', 'Croatian']
_EN_HR_DE = ['English', 'Croatian', 'German']
_EN_HR_IT = ['English', 'Croatian', 'Italian']

EXPERIENCES: list[dict] = [
    # ======================= ISTRIA =======================
    {
        'slug': 'buzet-truffle-hunting-with-dogs',
        'name': 'Truffle Hunting in the Mirna Valley Woods',
        'category': 'Dining',
        'region': 'istria',
        'location': 'Buzet',
        'image': 'dining.jpg',
        'price': 90,
        'duration_minutes': 210,
        'duration_label': '3.5 hours',
        'short_description': 'Walk the oak woods around Buzet with a truffle hunter and '
        'his dogs, then taste what you find over a simple Istrian lunch.',
        'description': 'The woods of the Mirna valley around Buzet are the heart of Istrian '
        'truffle country. A local truffle hunter leads a short walk through oak and hazel '
        'forest while trained dogs search the ground, and explains how the white and black '
        'truffles differ and why the hunt is done at dawn or in the cool of the day.\n\n'
        'Back at a family farmhouse the finds are shaved over eggs, homemade fuži pasta and '
        'local cheese. In the autumn white-truffle season the hunt is the main event; in '
        'spring and summer black summer truffles are found. Which kind you taste depends on '
        'the month, and finds are never guaranteed.',
        'highlights': [
            'Hunt with a truffle hunter and trained dogs',
            'Easy forest walk in the Mirna valley',
            'Learn how to tell white from black truffles',
            'Truffle lunch with fuži pasta, eggs and cheese',
            'Small groups only',
        ],
        'included': [
            'Guided truffle hunt',
            'Truffle lunch with local wine or water',
            'Truffle-tasting notes',
        ],
        'not_included': ['Transport to Buzet', 'Truffles to take home', 'Gratuities'],
        'itinerary': [
            {
                'title': 'Meet the hunter',
                'detail': 'A short briefing on truffles and the dogs '
                'at the start of the woodland track.',
            },
            {
                'title': 'The hunt',
                'detail': 'About 90 minutes of easy walking while the dogs '
                'search the forest floor.',
            },
            {
                'title': 'Lunch',
                'detail': "A farmhouse table with the day's truffles shaved "
                'over simple Istrian dishes.',
            },
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_SEASON, _FAQ_KIDS],
        'meeting_point': 'Buzet town centre area, exact point confirmed with your booking',
        'latitude': 45.4108,
        'longitude': 13.9647,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Closed walking shoes', 'Light rain jacket', 'Insect repellent'],
        'daily_capacity': 12,
        'max_guests_per_booking': 6,
    },
    {
        'slug': 'motovun-malvazija-teran-wine-tasting',
        'name': 'Malvazija and Teran Tasting Above the Mirna Valley',
        'category': 'Wine',
        'region': 'istria',
        'location': 'Motovun',
        'image': 'wine.jpg',
        'price': 55,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'Taste Istrian Malvazija and Teran at a family winery near '
        'Motovun, with local prosciutto, cheese and olive oil.',
        'description': 'Motovun sits on a hilltop above the Mirna valley, in the middle of '
        "Istria's wine country. At a family winery nearby you walk through the vines, see "
        'the cellar and learn why white Malvazija Istarska and red Teran taste the way they '
        "do on the region's red soil.\n\n"
        'You taste four to five wines, with Istrian prosciutto, sheep cheese and olive oil '
        'on the table. Before or after, there is time to walk up to the medieval walls of '
        'Motovun for the view over the valley.',
        'highlights': [
            'Vineyard and cellar visit at a family winery',
            'Malvazija Istarska and Teran side by side',
            'Prosciutto, cheese and olive oil pairings',
            'Free time on the Motovun town walls',
            'Small tasting group',
        ],
        'included': ['Winery visit', 'Tasting of 4 to 5 wines', 'Local food pairing'],
        'not_included': ['Transport to the winery', 'Bottles to take home'],
        'itinerary': [
            {
                'title': 'Vineyard walk',
                'detail': 'A short stroll through the vines and an '
                'introduction to Istrian grapes and soils.',
            },
            {
                'title': 'Cellar visit',
                'detail': 'Steel tanks and barrels, and how each wine is made.',
            },
            {'title': 'Tasting', 'detail': 'Four to five wines with local food at the table.'},
        ],
        'faqs': [_FAQ_DRINK, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Foot of Motovun hill, exact point confirmed with your booking',
        'latitude': 45.3369,
        'longitude': 13.8283,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes', 'Sun hat in summer'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'parenzana-trail-guided-bike-ride-groznjan',
        'name': 'Parenzana Trail by Bike Through Hilltop Istria',
        'category': 'Adventure',
        'region': 'istria',
        'location': 'Grožnjan',
        'image': 'hiking.jpg',
        'price': 59,
        'duration_minutes': 300,
        'duration_label': '5 hours',
        'short_description': 'Ride a stretch of the old Parenzana railway line, past '
        'tunnels, viaducts and vineyards, with a break in Grožnjan.',
        'description': 'The Parenzana was a narrow-gauge railway that ran between Trieste and '
        'Poreč from 1902 to 1935. Today much of its route in Istria is a cycling trail, '
        'with gentle gradients, stone viaducts and tunnels between hill towns.\n\n'
        'A guide leads a 30 to 35 km ride on the Croatian section around Grožnjan, a hill '
        "town known for its artists' studios. The pace is easy, with stops for views, a "
        'coffee break and a picnic-style lunch. Bikes and e-bikes are available; mention '
        'which you prefer when booking.',
        'highlights': [
            'Ride along the former Parenzana railway',
            'Stone viaducts and old railway tunnels',
            'Stop in the hill town of Grožnjan',
            'Mostly flat or gently downhill',
            'Bike or e-bike',
        ],
        'included': ['Guide', 'Bike, helmet and repair kit', 'Light lunch and water'],
        'not_included': [
            'E-bike supplement',
            'Transfer back if you ride one way',
            'Personal expenses',
        ],
        'itinerary': [
            {'title': 'Bike fitting', 'detail': 'Bikes, helmets and a short route briefing.'},
            {
                'title': 'Ride the trail',
                'detail': 'About 30 km on the old railway bed with views stops.',
            },
            {'title': 'Grožnjan break', 'detail': 'Time in the town and a light lunch.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Grožnjan area, exact point confirmed with your booking',
        'latitude': 45.3797,
        'longitude': 13.7219,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Sun cream', 'Sunglasses', 'Water bottle', 'Light jacket'],
        'daily_capacity': 14,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'rovinj-sea-kayaking-at-sunset',
        'name': 'Sunset Sea Kayaking Around Rovinj',
        'category': 'Water Sports',
        'region': 'istria',
        'location': 'Rovinj',
        'image': 'kayak.jpg',
        'price': 45,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': 'Paddle out from Rovinj along the coast and past small '
        'islands as the old town turns gold in the evening light.',
        'description': 'Rovinj looks its best from the water. A guide leads a sea-kayak '
        'tour out of the harbour area along the rocky shore and around small islets, with '
        'a view back to the old town and the bell tower of St Euphemia on its peninsula.\n\n'
        'The route is calm and sheltered, with a swim stop in a quiet cove. Double kayaks '
        'make it easy for beginners and families with older children.',
        'highlights': [
            "View of Rovinj's old town from the sea",
            'Paddle around small islands',
            'Swim stop in a quiet cove',
            'Beginner-friendly double kayaks',
            'Evening light for photos',
        ],
        'included': ['Guide', 'Kayak, paddle, life jacket', 'Dry bag', 'Safety briefing'],
        'not_included': ['Towel and swimwear', 'Photos', 'Gratuities'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'Paddling basics and safety on the beach.'},
            {
                'title': 'Along the coast',
                'detail': 'About 90 minutes of easy paddling with stops to look and swim.',
            },
            {'title': 'Back at sunset', 'detail': 'Return as the light changes over the town.'},
        ],
        'faqs': [_FAQ_SWIM, _FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Rovinj coast, exact point confirmed with your booking',
        'latitude': 45.0812,
        'longitude': 13.6387,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Swimwear', 'Towel', 'Sun cream', 'Water shoes'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'rovinj-old-town-walking-tour',
        'name': 'Rovinj Old Town: Alleys, Churches and Fishing History',
        'category': 'Culture',
        'region': 'istria',
        'location': 'Rovinj',
        'image': 'culture.jpg',
        'price': 25,
        'duration_minutes': 90,
        'duration_label': '1.5 hours',
        'short_description': "A guided walk through Rovinj's old town: Venetian history, "
        'the Church of St Euphemia and the fishing past.',
        'description': 'Rovinj grew on an island that was joined to the mainland in the 18th '
        'century, and it kept its Venetian look. A local guide walks you through the '
        "steep stone lanes, the harbour and the main squares, explaining the town's "
        'Venetian and Italian past and its fishing tradition.\n\n'
        'The walk ends at the Church of St Euphemia, whose bell tower rises above the old '
        'town. Wear shoes with grip: the stone paving is smooth.',
        'highlights': [
            'Venetian-era lanes and squares',
            'Harbour and fishing tradition',
            'Church of St Euphemia and its bell tower',
            'Local stories and Istro-Venetian dialect',
            'Easy pace, mostly flat',
        ],
        'included': ['Local guide', 'Small group'],
        'not_included': ['Church bell tower entry', 'Food and drinks'],
        'itinerary': [
            {'title': 'Harbour', 'detail': "The waterfront and the story of Rovinj's fishermen."},
            {
                'title': 'Old town lanes',
                'detail': "Arches, squares and the town's Venetian architecture.",
            },
            {'title': 'St Euphemia', 'detail': 'Up to the church at the top of the peninsula.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Old town waterfront, exact point confirmed with your booking',
        'latitude': 45.0812,
        'longitude': 13.6387,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes with grip', 'Hat', 'Water'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'pula-arena-and-roman-city-walk',
        'name': 'Pula Arena and the Roman City Walk',
        'category': 'Culture',
        'region': 'istria',
        'location': 'Pula',
        'image': 'culture.jpg',
        'price': 30,
        'duration_minutes': 120,
        'duration_label': '2 hours',
        'short_description': 'Walk Roman Pula with a guide: the 1st-century amphitheatre, '
        'the Arch of the Sergii, the Temple of Augustus and the Forum.',
        'description': 'Pula was a Roman colony, and its monuments are still in the middle '
        'of town. The amphitheatre, built in the 1st century, is among the best-preserved '
        'Roman arenas in the world and is where the walk starts.\n\n'
        'From there a guide takes you through the Arch of the Sergii, the Temple of '
        'Augustus and the Forum, and explains how the city changed under Venice, Austria '
        'and Italy. Entry to the arena is paid on site.',
        'highlights': [
            'Pula Arena, a Roman amphitheatre',
            'Arch of the Sergii',
            'Temple of Augustus on the Forum',
            'Roman, Venetian and Austrian layers of the city',
            'Compact walking route',
        ],
        'included': ['Local guide', 'Walking route map'],
        'not_included': ['Arena entry ticket', 'Food and drinks'],
        'itinerary': [
            {
                'title': 'The Arena',
                'detail': 'History of the amphitheatre and what it was used for.',
            },
            {
                'title': 'Roman gates and arch',
                'detail': 'The Arch of the Sergii and the old city line.',
            },
            {'title': 'The Forum', 'detail': 'The Temple of Augustus and the old town square.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Pula city centre, exact point confirmed with your booking',
        'latitude': 44.8731,
        'longitude': 13.8467,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Hat', 'Sun cream', 'Comfortable shoes'],
        'daily_capacity': 24,
        'max_guests_per_booking': 12,
    },
    {
        'slug': 'brijuni-national-park-day-trip',
        'name': 'Brijuni National Park Island Day Trip',
        'category': 'Culture',
        'region': 'istria',
        'location': 'Brijuni National Park',
        'image': 'sailing.jpg',
        'price': 85,
        'duration_minutes': 360,
        'duration_label': '6 hours',
        'short_description': 'Take the boat to Brijuni National Park for a guided tour of '
        'Veli Brijun, with its Roman ruins, safari park and old olive trees.',
        'description': 'The Brijuni islands lie off Fažana, a short boat ride from the Istrian '
        'coast, and are a national park. The tour takes in the main island, Veli Brijun, '
        'by small tourist train with a guide, passing the safari park, a Roman villa '
        'site, the Byzantine castrum and an ancient olive tree.\n\n'
        'There is free time on the island for a walk, a coffee or a swim. The trip includes '
        'the ferry from Fažana and the park entry fee.',
        'highlights': [
            'Boat from Fažana to Veli Brijun',
            'Guided tour of the island by train',
            'Roman and Byzantine remains',
            'Safari park and an olive tree centuries old',
            'Free time for a swim or a walk',
        ],
        'included': ['Return boat from Fažana', 'National park entry', 'Guided island tour'],
        'not_included': ['Lunch', 'Optional bike hire on the island', 'Hotel transfers'],
        'itinerary': [
            {'title': 'Boat to Brijuni', 'detail': 'A 15-minute crossing from Fažana.'},
            {'title': 'Island tour', 'detail': 'About two hours with the guide, mostly by train.'},
            {'title': 'Free time', 'detail': 'Walk, swim or eat before the afternoon boat back.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS, _FAQ_SEASON],
        'meeting_point': 'Fažana harbour, exact point confirmed with your booking',
        'latitude': 44.9167,
        'longitude': 13.7667,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Swimwear', 'Sun cream', 'Hat', 'Water'],
        'daily_capacity': 30,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'cape-kamenjak-kayak-and-snorkel',
        'name': 'Cape Kamenjak Kayak and Snorkel Coast Trip',
        'category': 'Water Sports',
        'region': 'istria',
        'location': 'Cape Kamenjak',
        'image': 'kayak.jpg',
        'price': 50,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'Paddle the rocky southern tip of Istria in Kamenjak nature '
        'park, with a snorkel stop in clear coves.',
        'description': 'Kamenjak is a protected nature park at the very south of Istria, '
        'with rocky coves, cliffs and clear, shallow water. By kayak you can reach '
        'stretches of coast that have no road.\n\n'
        'The guide paddles along the shore and stops in two coves for snorkelling. Wind '
        'can pick up on this exposed coast, so the route is chosen on the day and may '
        'change.',
        'highlights': [
            'Paddle the southern tip of Istria',
            'Snorkel in clear coves',
            'Limestone cliffs and sea caves from the water',
            'Guide chooses route by the wind',
            'Park entry arranged',
        ],
        'included': ['Guide', 'Kayak, paddle, life jacket', 'Snorkel and mask'],
        'not_included': ['Park entry fee at the gate', 'Towel', 'Food and drinks'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'Safety and paddling basics on the shore.'},
            {'title': 'Coastal paddle', 'detail': 'Along the cliffs and between small coves.'},
            {'title': 'Snorkel stops', 'detail': 'Two stops in sheltered, shallow water.'},
        ],
        'faqs': [_FAQ_SWIM, _FAQ_WEATHER, _FAQ_SEASON],
        'meeting_point': 'Premantura area, exact point confirmed with your booking',
        'latitude': 44.7667,
        'longitude': 13.9167,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Swimwear', 'Water shoes', 'Sun cream', 'Towel'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'porec-euphrasian-basilica-old-town-walk',
        'name': 'Poreč: Euphrasian Basilica and the Roman Streets',
        'category': 'Culture',
        'region': 'istria',
        'location': 'Poreč',
        'image': 'culture.jpg',
        'price': 28,
        'duration_minutes': 105,
        'duration_label': '1 hour 45 min',
        'short_description': 'See the UNESCO-listed Euphrasian Basilica and the Roman '
        "street plan of Poreč's old town with a local guide.",
        'description': 'Poreč still follows the grid of its Roman street plan. The '
        'Euphrasian Basilica, built in the 6th century, is a UNESCO World Heritage Site and '
        'is known for its Byzantine mosaics.\n\n'
        'The walk starts at the basilica, then follows the Decumanus, past the Temple of '
        'Neptune ruins and Romanesque houses. Churches may close for services; the guide '
        'adjusts the order. Basilica entry is paid on site.',
        'highlights': [
            'UNESCO Euphrasian Basilica and its mosaics',
            'Roman street grid along the Decumanus',
            'Romanesque House and the Neptune temple ruins',
            'Local stories about Poreč',
            'Easy walking, flat ground',
        ],
        'included': ['Local guide'],
        'not_included': ['Basilica entry', 'Bell tower climb', 'Food and drinks'],
        'itinerary': [
            {'title': 'Basilica', 'detail': 'The 6th-century mosaics and atrium.'},
            {'title': 'Decumanus', 'detail': 'Along the Roman main street.'},
            {'title': 'Waterfront', 'detail': 'Finish by the sea walls.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Poreč old town, exact point confirmed with your booking',
        'latitude': 45.2272,
        'longitude': 13.5946,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Covered shoulders for the basilica', 'Hat', 'Water'],
        'daily_capacity': 24,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'lim-bay-boat-trip-shellfish-tasting',
        'name': 'Lim Bay by Boat with a Shellfish Tasting',
        'category': 'Dining',
        'region': 'istria',
        'location': 'Lim Bay',
        'image': 'sailing.jpg',
        'price': 65,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'Cruise the Lim Fjord, learn how mussels and oysters are '
        'farmed, and taste them fresh with local white wine.',
        'description': 'The Lim Bay, often called a fjord, is a long, narrow inlet in western '
        'Istria with steep green sides. Shellfish farming has been done here for '
        'generations because the water mixes sea and freshwater.\n\n'
        'A small boat takes you along the channel. At a shellfish farm you see the ropes '
        'and cages, then taste mussels and oysters straight from the water with bread and '
        'a glass of local white wine.',
        'highlights': [
            'Boat trip along the Lim Fjord',
            'See how mussels and oysters are farmed',
            'Fresh shellfish tasting',
            'Local wine and bread',
            'Quiet, green landscape',
        ],
        'included': ['Boat trip', 'Shellfish tasting', 'Wine or soft drink'],
        'not_included': ['Transport to the bay', 'Additional food and drinks'],
        'itinerary': [
            {'title': 'Board and cruise', 'detail': 'Along the length of the bay.'},
            {'title': 'Shellfish farm', 'detail': 'How the ropes and cages work.'},
            {'title': 'Tasting', 'detail': 'Mussels and oysters on the boat or at the farm.'},
        ],
        'faqs': [
            _FAQ_WEATHER,
            {
                'q': 'Can I join if I do not eat shellfish?',
                'a': 'The tasting is built on shellfish. Tell us when booking and the host '
                'will say whether another option is possible.',
            },
        ],
        'meeting_point': 'Lim Bay near Vrsar, exact point confirmed with your booking',
        'latitude': 45.1333,
        'longitude': 13.7167,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Sun cream', 'Hat', 'Light jacket'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'hum-smallest-town-glagolitic-alley-walk',
        'name': 'Hum, the Smallest Town, and the Glagolitic Alley',
        'category': 'Culture',
        'region': 'istria',
        'location': 'Hum',
        'image': 'culture.jpg',
        'price': 38,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': 'Visit Hum, said to be the smallest town in the world, and '
        'walk part of the Glagolitic Alley with its stone monuments.',
        'description': 'Hum has fewer than a few dozen residents and is known as the smallest '
        'town in the world. A walled hilltop settlement, it has a church, a small main '
        'street and a tradition of writing in Glagolitic, the oldest Slavic alphabet.\n\n'
        'The Glagolitic Alley is a road between Roč and Hum lined with stone monuments '
        'to that script. The tour walks a section of it, then explores Hum on foot and '
        'tries a glass of biska, a mistletoe brandy made in the area.',
        'highlights': [
            'Hum, a walled hilltop town',
            'Glagolitic Alley monuments',
            'History of the oldest Slavic alphabet',
            'Biska, the local mistletoe brandy',
            'Quiet Istrian countryside',
        ],
        'included': ['Guide', 'Glass of biska or a soft drink'],
        'not_included': ['Transport to Hum', 'Lunch'],
        'itinerary': [
            {'title': 'Glagolitic Alley', 'detail': 'A walk along the monuments.'},
            {'title': 'Hum', 'detail': "Gate, church and the town's one street."},
            {'title': 'Biska tasting', 'detail': 'A short stop with the local brandy.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS, _FAQ_PICKUP],
        'meeting_point': 'Hum village car park area, exact point confirmed with your booking',
        'latitude': 45.2211,
        'longitude': 13.9358,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes', 'Water', 'Hat'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'rabac-coastal-yoga-and-sea-swim',
        'name': 'Morning Coastal Yoga and Sea Swim in Rabac',
        'category': 'Wellness',
        'region': 'istria',
        'location': 'Rabac',
        'image': 'spa.jpg',
        'price': 30,
        'duration_minutes': 90,
        'duration_label': '1.5 hours',
        'short_description': 'A gentle yoga session on the Rabac shore, followed by a '
        'swim in the Adriatic and a herbal tea.',
        'description': 'Rabac is a small seaside town below Labin on the eastern coast of '
        'Istria. This session takes place on a quiet part of the coast early in the '
        'morning, before the day gets hot.\n\n'
        'An instructor leads a gentle hatha flow suitable for all levels, finishing with '
        'breathing exercises. After that you can swim, and the session ends with a herbal '
        'tea. Mats are provided.',
        'highlights': [
            'Yoga on the shore at sunrise',
            'All levels welcome',
            'Optional swim after the session',
            'Herbal tea to finish',
            'Small group',
        ],
        'included': ['Instructor', 'Yoga mat', 'Herbal tea'],
        'not_included': ['Towel', 'Swimwear'],
        'itinerary': [
            {'title': 'Warm-up', 'detail': 'Slow stretching as the sun rises.'},
            {'title': 'Yoga flow', 'detail': 'About 60 minutes of gentle hatha practice.'},
            {'title': 'Swim and tea', 'detail': 'Time in the sea, then tea.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_SEASON],
        'meeting_point': 'Rabac seafront, exact point confirmed with your booking',
        'latitude': 45.0792,
        'longitude': 14.1569,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable clothes', 'Towel', 'Swimwear', 'Water'],
        'daily_capacity': 12,
        'max_guests_per_booking': 6,
    },
    # ======================= KVARNER =======================
    {
        'slug': 'mali-losinj-dolphin-watching-boat-trip',
        'name': 'Dolphin Watching Around the Lošinj Islands',
        'category': 'Water Sports',
        'region': 'kvarner',
        'location': 'Mali Lošinj',
        'image': 'sailing.jpg',
        'price': 55,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': 'Boat trip from Mali Lošinj into the waters of the dolphin '
        "reserve, with a marine biologist's commentary.",
        'description': 'The waters around Cres and Lošinj are home to a resident group of '
        'bottlenose dolphins, and the area has a protected dolphin reserve. A guide with '
        'knowledge of the animals leads this boat trip, which follows the code of conduct: '
        'slow approach, no chasing and no swimming with the dolphins.\n\n'
        'Sightings are likely but never guaranteed. The trip also includes a swim stop '
        'and time to look at the small islands and cliffs. The best season is late spring '
        'to autumn.',
        'highlights': [
            'Search for bottlenose dolphins in the reserve',
            'Responsible-viewing code of conduct',
            'Commentary on dolphin behaviour',
            'Swim stop at a quiet bay',
            'Islands and cliffs of the Lošinj archipelago',
        ],
        'included': ['Boat with skipper and guide', 'Water and fruit', 'Swim stop'],
        'not_included': ['Food', 'Towel', 'Gratuities'],
        'itinerary': [
            {'title': 'Departure', 'detail': 'Leave the harbour and cruise to the reserve.'},
            {
                'title': 'Search',
                'detail': 'Follow the guide and the skipper to likely feeding grounds.',
            },
            {'title': 'Swim stop', 'detail': 'A short stop in a sheltered bay on the return.'},
        ],
        'faqs': [
            {
                'q': 'Will we see dolphins?',
                'a': 'Most trips do, but wild animals cannot be promised. Sightings depend '
                'on the day and the sea conditions.',
            },
            _FAQ_WEATHER,
            _FAQ_KIDS,
        ],
        'meeting_point': 'Mali Lošinj harbour, exact point confirmed with your booking',
        'latitude': 44.5333,
        'longitude': 14.4667,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Sun cream', 'Hat', 'Light jacket', 'Swimwear'],
        'daily_capacity': 24,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'opatija-lungomare-coastal-walk',
        'name': 'Opatija and the Lungomare Seaside Promenade',
        'category': 'Culture',
        'region': 'kvarner',
        'location': 'Opatija',
        'image': 'culture.jpg',
        'price': 25,
        'duration_minutes': 120,
        'duration_label': '2 hours',
        'short_description': 'Walk the Lungomare, the seaside path between Volosko and '
        'Lovran, and hear about Opatija as a Habsburg-era resort.',
        'description': 'The Lungomare is a 12 km promenade along the coast of the Opatija '
        'Riviera, built from the 1880s as the town became a fashionable resort of the '
        'Austro-Hungarian court. The walk covers the section from Opatija towards '
        'Volosko, passing villas, parks and small bays.\n\n'
        'A guide tells the story of how a fishing village became a health resort, points out '
        'the villas and the statue of the Maiden with the Seagull, and explains the park '
        'plantings. The walk is mostly flat with some steps.',
        'highlights': [
            'The Lungomare seaside promenade',
            'Habsburg-era villas and parks',
            'Maiden with the Seagull statue',
            'Sea views and small bays',
            'Mostly flat walking',
        ],
        'included': ['Local guide'],
        'not_included': ['Food and drinks', 'Transport back from the end point'],
        'itinerary': [
            {'title': 'Opatija centre', 'detail': 'Park Angiolina and the main villas.'},
            {'title': 'Along the promenade', 'detail': "About 3 km on the water's edge."},
            {'title': 'Volosko', 'detail': 'End at the old fishing village.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Opatija town centre, exact point confirmed with your booking',
        'latitude': 45.3377,
        'longitude': 14.3053,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes', 'Sun cream', 'Water'],
        'daily_capacity': 24,
        'max_guests_per_booking': 12,
    },
    {
        'slug': 'lovran-forest-and-coast-wellness-walk',
        'name': 'Lovran Forest Walk with Sea Breathing and a Herbal Tea',
        'category': 'Wellness',
        'region': 'kvarner',
        'location': 'Lovran',
        'image': 'spa.jpg',
        'price': 40,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': 'A slow guided walk through laurel and chestnut woods above '
        'Lovran, with breathing exercises and herbal tea by the sea.',
        'description': 'Lovran sits between the sea and the slopes of Učka, and its older '
        'streets are lined with laurel and chestnut trees. This is a slow-paced walk '
        'in the woods above the town, with pauses to listen and breathe.\n\n'
        'A wellness guide leads simple breathing and stretching exercises, and the walk '
        'ends by the sea with an herbal tea made from plants of the area. It is not a '
        'workout; it suits anyone who wants a quiet morning.',
        'highlights': [
            'Slow walk in laurel and chestnut woods',
            'Breathing and stretching exercises',
            'Sea view finish in Lovran',
            'Herbal tea from local plants',
            'No fitness needed',
        ],
        'included': ['Wellness guide', 'Herbal tea'],
        'not_included': ['Transport to Lovran', 'Food'],
        'itinerary': [
            {'title': 'Into the woods', 'detail': 'A gentle uphill walk on a shaded path.'},
            {'title': 'Stillness', 'detail': 'Breathing and stretching in a quiet spot.'},
            {'title': 'By the sea', 'detail': 'Descend to the coast for tea.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_FITNESS],
        'meeting_point': 'Lovran town centre area, exact point confirmed with your booking',
        'latitude': 45.2933,
        'longitude': 14.2733,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable walking shoes', 'Light jacket', 'Water'],
        'daily_capacity': 12,
        'max_guests_per_booking': 6,
    },
    {
        'slug': 'ucka-nature-park-vojak-summit-hike',
        'name': 'Učka Nature Park: Hike to Vojak, the Summit',
        'category': 'Adventure',
        'region': 'kvarner',
        'location': 'Učka Nature Park',
        'image': 'hiking.jpg',
        'price': 60,
        'duration_minutes': 300,
        'duration_label': '5 hours',
        'short_description': 'Hike to Vojak, the highest peak of Učka at 1,401 m, with '
        'views over the Kvarner Gulf and the Istrian peninsula.',
        'description': 'Učka is the mountain that separates Istria from Kvarner, and the '
        'protected nature park around it covers beech forest, rocky ridges and meadows. '
        'Vojak is the highest point, at 1,401 m, and from the top you can see the '
        'islands of Kvarner and the hills of Istria on a clear day.\n\n'
        'A guide leads the hike from the Poklon pass, a walk of about 3 to 4 hours return '
        'on marked paths with moderate climbing. The weather on the mountain can change '
        'quickly; the route is adjusted on the day.',
        'highlights': [
            'Summit of Vojak at 1,401 m',
            'Views of Kvarner and Istria',
            'Beech forest and mountain meadows',
            'Marked paths with a local guide',
            'Wildlife and flora information',
        ],
        'included': ['Mountain guide', 'Water and snack'],
        'not_included': ['Park entry if charged', 'Transport to Poklon', 'Lunch'],
        'itinerary': [
            {'title': 'Start at the pass', 'detail': 'Briefing and gear check.'},
            {'title': 'Climb to Vojak', 'detail': 'About 2 hours up on marked trails.'},
            {'title': 'Summit and return', 'detail': 'Views, rest and the walk down.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Poklon pass in Učka Nature Park, exact point confirmed with your booking',
        'latitude': 45.2808,
        'longitude': 14.1983,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Hiking boots', 'Rain jacket', 'Warm layer', 'Water', 'Sun cream'],
        'daily_capacity': 14,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'risnjak-national-park-leska-educational-trail',
        'name': 'Risnjak National Park: Leska Trail and the Kupa Spring',
        'category': 'Adventure',
        'region': 'kvarner',
        'location': 'Risnjak National Park',
        'image': 'hiking.jpg',
        'price': 55,
        'duration_minutes': 270,
        'duration_label': '4.5 hours',
        'short_description': 'A guided walk in Risnjak National Park on the Leska '
        'educational trail, with a visit to the Kupa river spring.',
        'description': 'Risnjak National Park protects forests, karst and the source of '
        'the Kupa river in Gorski Kotar. The Leska educational trail is a loop of about '
        '4 km that passes information boards on plants, animals and the forest, and '
        'is easy for most people.\n\n'
        "After the walk, the group drives to the Kupa spring on the park's northern edge, "
        'a clear basin that feeds the river. '
        'Lynx live in the park but are rarely seen. Mountain weather changes fast, so a '
        'jacket is wise even in summer.',
        'highlights': [
            'Leska educational trail in the national park',
            'Source of the Kupa river',
            'Dense fir and beech forest',
            'Wildlife and plant information',
            'Cool, quiet woodland',
        ],
        'included': ['Guide', 'Park entry', 'Water', 'Drive from Crni Lug to the Kupa spring'],
        'not_included': ['Transport to Crni Lug', 'Lunch'],
        'itinerary': [
            {'title': 'Park entrance', 'detail': 'Briefing at the visitor area.'},
            {'title': 'Leska trail', 'detail': 'A loop through the forest with stops.'},
            {'title': 'Kupa spring', 'detail': 'A drive to the source of the river.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Crni Lug park entrance, exact point confirmed with your booking',
        'latitude': 45.4167,
        'longitude': 14.6167,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Walking shoes', 'Rain jacket', 'Insect repellent', 'Water'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'baska-sea-kayak-along-the-coast',
        'name': 'Baška Sea Kayak Tour Along the Krk Coast',
        'category': 'Water Sports',
        'region': 'kvarner',
        'location': 'Baška',
        'image': 'kayak.jpg',
        'price': 48,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'Paddle along the cliffs south of Baška on the island of Krk, '
        'with a swim stop in a cove near the Vela Plaža bay.',
        'description': 'Baška lies at the southern end of Krk, in a bay below bare limestone '
        'ridges. By kayak you leave the long town beach and head along the coast, past '
        'cliffs and small coves that cannot be reached by road.\n\n'
        'The guide chooses the direction on the day; on the island of Krk the bora wind '
        'can be strong, so the route stays sheltered. Stops for swimming and snorkelling.',
        'highlights': [
            'Limestone cliffs and coves from the water',
            'Swim and snorkel stops',
            'Route chosen to avoid the wind',
            'Easy for beginners',
            "View of Baška's bay and hills",
        ],
        'included': ['Guide', 'Kayak, paddle and life jacket', 'Dry bag'],
        'not_included': ['Towel', 'Swimwear', 'Food'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'On the beach, with a short paddling lesson.'},
            {'title': 'Along the shore', 'detail': 'Easy paddling beside the cliffs.'},
            {'title': 'Cove stop', 'detail': 'Swim and snorkel before heading back.'},
        ],
        'faqs': [_FAQ_SWIM, _FAQ_WEATHER, _FAQ_SEASON],
        'meeting_point': 'Baška beach, exact point confirmed with your booking',
        'latitude': 44.9667,
        'longitude': 14.75,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Swimwear', 'Towel', 'Sun cream', 'Water shoes'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'vrbnik-zlahtina-wine-cellar-tasting',
        'name': 'Vrbnik Žlahtina Tasting in a Family Cellar',
        'category': 'Wine',
        'region': 'kvarner',
        'location': 'Vrbnik',
        'image': 'wine.jpg',
        'price': 40,
        'duration_minutes': 120,
        'duration_label': '2 hours',
        'short_description': 'Taste Žlahtina, the white wine of Vrbnik on Krk, in a family '
        'cellar in the old town, with local cheese and prosciutto.',
        'description': 'Vrbnik is a small walled town on a cliff on the island of Krk, and the '
        'home of Žlahtina, a crisp white wine from a grape grown in the Vrbnik valley. '
        'The old town is full of cellars in stone houses.\n\n'
        'A guide shows you the town, including one of the narrowest streets in Croatia, '
        'then takes you to a family cellar for a tasting of three Žlahtina wines with '
        'local cheese and prosciutto.',
        'highlights': [
            'Žlahtina, the wine of Krk',
            'Family cellar in the old town',
            'One of the narrowest streets in Croatia',
            'Cheese and prosciutto pairing',
            'Views over the sea from the cliff',
        ],
        'included': ['Short old town walk', 'Tasting of 3 wines', 'Cheese and prosciutto'],
        'not_included': ['Transport to Vrbnik', 'Bottles to take home'],
        'itinerary': [
            {'title': 'Old town walk', 'detail': 'Lanes, walls and the cliff edge.'},
            {'title': 'Cellar visit', 'detail': 'How Žlahtina is made and stored.'},
            {'title': 'Tasting', 'detail': 'Three wines with local food.'},
        ],
        'faqs': [_FAQ_DRINK, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Vrbnik old town entrance, exact point confirmed with your booking',
        'latitude': 45.0728,
        'longitude': 14.6717,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes'],
        'daily_capacity': 14,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'cres-tramontana-hike-to-beli',
        'name': 'Cres Tramontana Hike Towards Beli',
        'category': 'Adventure',
        'region': 'kvarner',
        'location': 'Cres',
        'image': 'hiking.jpg',
        'price': 52,
        'duration_minutes': 300,
        'duration_label': '5 hours',
        'short_description': 'Hike the Tramontana, the wild north of Cres, through sheep '
        'pastures and oak woods to the cliff village of Beli.',
        'description': 'The north of Cres, called Tramontana, is a quiet landscape of dry-stone '
        'walls, pastures, oak woods and few roads. This hike follows old paths towards '
        'Beli, a small village on a cliff above the sea.\n\n'
        'The guide explains the sheep farming and Griffon vulture colony that make this '
        'part of the island known; vultures can be seen soaring over the cliffs. The walk '
        'has some stony sections, so good shoes matter.',
        'highlights': [
            'Old paths across the Tramontana',
            'Dry-stone walls and sheep pastures',
            'Cliff village of Beli',
            'Griffon vultures over the cliffs',
            'Few people, big views',
        ],
        'included': ['Guide', 'Water and snack'],
        'not_included': ['Transport to the trailhead', 'Lunch'],
        'itinerary': [
            {'title': 'Trailhead', 'detail': 'Briefing and first stretch through oak woods.'},
            {'title': 'The pastures', 'detail': 'Across open ground and stone walls.'},
            {'title': 'Beli', 'detail': 'Arrive at the village and take a rest.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Cres town area, exact point confirmed with your booking',
        'latitude': 44.9606,
        'longitude': 14.4083,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Hiking shoes', 'Hat', 'Sun cream', 'Water'],
        'daily_capacity': 12,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'rab-old-town-four-bell-towers-walk',
        'name': 'Rab Old Town and the Four Bell Towers',
        'category': 'Culture',
        'region': 'kvarner',
        'location': 'Rab',
        'image': 'culture.jpg',
        'price': 28,
        'duration_minutes': 105,
        'duration_label': '1 hour 45 min',
        'short_description': 'Walk the medieval old town of Rab, known for its four bell '
        'towers on one ridge, with a guide.',
        'description': 'The old town of Rab sits on a narrow peninsula, and its skyline is '
        'defined by four bell towers in a line. A guide leads a walk along the three main '
        "streets, explaining the town's Venetian and medieval history and its churches, "
        'loggia and gardens.\n\n'
        'You can climb one of the towers (not included) for a view of the roofs and '
        'the sea. The walk is mostly flat with some steps.',
        'highlights': [
            'Four bell towers on the ridge',
            'Medieval streets and loggia',
            'Park Komrčar and sea views',
            'Venetian history',
            'Easy pace',
        ],
        'included': ['Local guide'],
        'not_included': ['Bell tower climb', 'Food and drinks'],
        'itinerary': [
            {'title': 'Old town gate', 'detail': 'History of the town walls.'},
            {'title': 'The ridge', 'detail': 'Churches and bell towers on the main streets.'},
            {'title': 'Park Komrčar', 'detail': 'Finish in the shaded park above the sea.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Rab old town, exact point confirmed with your booking',
        'latitude': 44.7586,
        'longitude': 14.7606,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes', 'Hat', 'Water'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'rijeka-central-market-and-city-food-walk',
        'name': 'Rijeka Central Market and City Food Walk',
        'category': 'Dining',
        'region': 'kvarner',
        'location': 'Rijeka',
        'image': 'dining.jpg',
        'price': 52,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'Taste your way through Rijeka: the market hall, fish market '
        'and old town, with stops for local specialities.',
        'description': "Rijeka is Croatia's main port and its food reflects Kvarner, with "
        'seafood, Italian influences and mountain produce from Gorski Kotar. The walk begins '
        'at the Central Market, a group of historic halls from the early 20th century.\n\n'
        'You taste local cheese, cured meat, seasonal fruit and pastries at the stalls and '
        'in small places nearby, then walk the Korzo and the old town while a guide '
        "explains the city's history.",
        'highlights': [
            'Rijeka Central Market halls',
            'Fish market and local seafood',
            'Cheese, cured meat and pastries',
            'The Korzo and old town streets',
            'Local guide with city stories',
        ],
        'included': ['Guide', 'Food tastings at 5 stops', 'Water'],
        'not_included': ['Additional drinks', 'Gratuities'],
        'itinerary': [
            {'title': 'Market halls', 'detail': 'Produce, cheese and cured meat.'},
            {'title': 'Fish market', 'detail': 'What the Kvarner fishermen bring in.'},
            {'title': 'Korzo and old town', 'detail': 'A final sweet or coffee stop.'},
        ],
        'faqs': [
            _FAQ_WEATHER,
            {
                'q': 'Can you cater for dietary needs?',
                'a': 'Tell us about vegetarian, gluten-free or other needs when booking '
                'and the guide will plan the stops accordingly.',
            },
        ],
        'meeting_point': 'Rijeka city centre, exact point confirmed with your booking',
        'latitude': 45.3271,
        'longitude': 14.4422,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Appetite', 'Comfortable shoes'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    # ======================= ZAGREB =======================
    {
        'slug': 'zagreb-food-and-history-walk',
        'name': 'Zagreb Food and History Walk: Dolac Market and the Upper Town',
        'category': 'Dining',
        'region': 'zagreb',
        'location': 'Zagreb',
        'image': 'dining.jpg',
        'price': 55,
        'duration_minutes': 195,
        'duration_label': '3 hours 15 min',
        'short_description': 'Taste Zagreb at Dolac market and in the old streets, with '
        "stories about the city's past between the stops.",
        'description': 'Zagreb has two old towns, Gornji grad (Upper Town) and Kaptol, and '
        'a market, Dolac, between them. A guide leads you from the market stalls to '
        'small food places, with tastings of štrukli, local cheese, cured meat and '
        'pastries.\n\n'
        'The walk also passes Zagreb Cathedral, the Stone Gate and the Funicular, with '
        'a short history of how the city grew. Ask about dietary needs when booking.',
        'highlights': [
            'Dolac market tasting',
            'Štrukli and other Zagreb dishes',
            'Cathedral, Stone Gate and the funicular',
            'Local cheese and cured meat',
            'City history on foot',
        ],
        'included': ['Guide', 'Food tastings at 5 stops', 'Water'],
        'not_included': ['Additional drinks', 'Gratuities'],
        'itinerary': [
            {'title': 'Dolac market', 'detail': 'Stalls, produce and a first tasting.'},
            {'title': 'Kaptol and Upper Town', 'detail': 'Street food and historic sights.'},
            {'title': 'Final tasting', 'detail': 'A sweet stop and coffee.'},
        ],
        'faqs': [
            _FAQ_WEATHER,
            {
                'q': 'Can you cater for dietary needs?',
                'a': 'Tell us about vegetarian, gluten-free or other needs when booking.',
            },
        ],
        'meeting_point': 'Zagreb city centre, exact point confirmed with your booking',
        'latitude': 45.815,
        'longitude': 15.9819,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Comfortable shoes', 'Appetite'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'zagreb-upper-town-history-walk',
        'name': 'Zagreb Upper Town: Gates, Churches and Legends',
        'category': 'Culture',
        'region': 'zagreb',
        'location': 'Zagreb',
        'image': 'culture.jpg',
        'price': 25,
        'duration_minutes': 120,
        'duration_label': '2 hours',
        'short_description': "A guided walk through Gornji grad: the Stone Gate, St Mark's "
        'Church, Lotrščak Tower and the legends of old Zagreb.',
        'description': 'Gornji grad is the medieval hilltop town of Zagreb, with narrow '
        'streets, gas lamps and small squares. The walk covers the Stone Gate, with its '
        "chapel to the Virgin Mary, St Mark's Church with its tiled roof, and the "
        'Lotrščak Tower, where a cannon is fired at noon.\n\n'
        'The guide tells legends and history of the city, from the rival towns of Gradec and '
        'Kaptol to the 1880 earthquake. Entry to museums is not included.',
        'highlights': [
            'Stone Gate and its chapel',
            "St Mark's Church tiled roof",
            'Lotrščak Tower and the noon cannon',
            'Legends of old Zagreb',
            'Views over the lower town',
        ],
        'included': ['Local guide'],
        'not_included': ['Museum entry', 'Tower climb', 'Food and drinks'],
        'itinerary': [
            {'title': 'Stone Gate', 'detail': 'The oldest gate and the chapel inside.'},
            {'title': "St Mark's Square", 'detail': 'Church, parliament and government.'},
            {'title': 'Lotrščak Tower', 'detail': 'Views and the story of the noon cannon.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Zagreb Upper Town, exact point confirmed with your booking',
        'latitude': 45.8161,
        'longitude': 15.9737,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Comfortable shoes', 'Umbrella or sun hat'],
        'daily_capacity': 24,
        'max_guests_per_booking': 12,
    },
    {
        'slug': 'samobor-plesivica-wine-road-tasting',
        'name': 'Plešivica Wine Road Day from Samobor',
        'category': 'Wine',
        'region': 'zagreb',
        'location': 'Samobor',
        'image': 'wine.jpg',
        'price': 70,
        'duration_minutes': 300,
        'duration_label': '5 hours',
        'short_description': 'Visit Samobor, then drive the Plešivica wine road for tastings '
        'of sparkling and white wines at small family wineries.',
        'description': "The Plešivica hills southwest of Zagreb are one of Croatia's "
        'continental wine regions, known for sparkling wines and for white grapes like '
        'Chardonnay, Pinot Gris and Rhine Riesling. The day starts in Samobor, a small '
        'town with a Habsburg centre and a tradition of pastry and mustard.\n\n'
        'You then travel up to the wine road for tastings at two family wineries, with '
        'cheese, cured meat and bread. Transport between stops is included.',
        'highlights': [
            'Samobor town centre and its pastry tradition',
            'Plešivica hills vineyards',
            'Sparkling and white wine tastings',
            'Two family wineries',
            'Transport between stops included',
        ],
        'included': ['Guide and transport', 'Tastings at 2 wineries', 'Light food'],
        'not_included': ['Bottles to take home', 'Pickup from Zagreb hotels'],
        'itinerary': [
            {'title': 'Samobor', 'detail': 'A short walk and a coffee stop.'},
            {'title': 'Winery one', 'detail': 'Vineyard view and sparkling wine tasting.'},
            {'title': 'Winery two', 'detail': 'White wines and a food pairing.'},
        ],
        'faqs': [_FAQ_DRINK, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Samobor main square area, exact point confirmed with your booking',
        'latitude': 45.8014,
        'longitude': 15.7108,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Comfortable shoes', 'Light jacket'],
        'daily_capacity': 12,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'medvednica-nature-park-sljeme-hike',
        'name': 'Medvednica Nature Park: Hike to Sljeme above Zagreb',
        'category': 'Adventure',
        'region': 'zagreb',
        'location': 'Medvednica Nature Park',
        'image': 'hiking.jpg',
        'price': 35,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': 'A guided half-day hike on Medvednica, the mountain above '
        'Zagreb, up to Sljeme at 1,035 m.',
        'description': 'Medvednica is the forested mountain that rises directly above Zagreb, and '
        'a nature park. Its highest point, Sljeme, is at 1,035 m and has a TV tower and '
        'views over the city on clear days.\n\n'
        'The guide chooses a route on marked paths through beech forest, passing the '
        'ruins of the Medvedgrad fortress or a waterfall depending on conditions. It is a '
        'moderate walk with some climbing; sturdy shoes needed.',
        'highlights': [
            'Summit of Sljeme at 1,035 m',
            'Beech forest paths',
            'Views over Zagreb',
            'Medvedgrad fortress or waterfall option',
            'Wildlife and flora information',
        ],
        'included': ['Guide', 'Water'],
        'not_included': ['Transport to the trailhead', 'Lunch'],
        'itinerary': [
            {'title': 'Trailhead', 'detail': 'Briefing and warm-up.'},
            {'title': 'Climb', 'detail': 'Through beech woods on marked paths.'},
            {'title': 'Sljeme', 'detail': 'Rest at the top and return.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Medvednica trailhead near Zagreb, exact point confirmed with your '
        'booking',
        'latitude': 45.9,
        'longitude': 15.9667,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Hiking shoes', 'Rain jacket', 'Water', 'Snack'],
        'daily_capacity': 14,
        'max_guests_per_booking': 8,
    },
    # ======================= CONTINENTAL =======================
    {
        'slug': 'varazdin-baroque-city-walk',
        'name': 'Varaždin: The Baroque City Walk',
        'category': 'Culture',
        'region': 'continental',
        'location': 'Varaždin',
        'image': 'culture.jpg',
        'price': 25,
        'duration_minutes': 105,
        'duration_label': '1 hour 45 min',
        'short_description': "A guided walk through Varaždin's baroque centre: the old town "
        'fortress, the town hall and the palaces on the main squares.',
        'description': 'Varaždin was the capital of Croatia in the 18th century, and the baroque '
        'architecture of that period still defines the centre. The walk starts at the Old '
        'Town fortress and moves through the main square, past the town hall and the '
        'palaces along the pedestrian streets.\n\n'
        'The guide tells how a fire in 1776 led to the rebuilding of the town in the '
        'baroque style and explains the cemetery, one of the best-known in Europe, if '
        'time allows. Museum entry is not included.',
        'highlights': [
            'Baroque centre of Varaždin',
            'Old Town fortress',
            'Town hall and palaces',
            'Capital of Croatia in the 18th century',
            'Flat, easy walking',
        ],
        'included': ['Local guide'],
        'not_included': ['Museum entry', 'Food and drinks'],
        'itinerary': [
            {'title': 'Old Town fortress', 'detail': 'History of the castle and the town.'},
            {'title': 'Main square', 'detail': 'Town hall and baroque palaces.'},
            {'title': 'Pedestrian streets', 'detail': 'Quiet lanes and churches.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Varaždin main square, exact point confirmed with your booking',
        'latitude': 46.3057,
        'longitude': 16.3366,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Comfortable shoes', 'Water'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'kopacki-rit-birdwatching-boat-trip',
        'name': 'Birdwatching by Boat in Kopački Rit Nature Park',
        'category': 'Adventure',
        'region': 'continental',
        'location': 'Kopački Rit Nature Park',
        'image': 'sailing.jpg',
        'price': 38,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'A boat trip through the wetlands of Kopački Rit, one of '
        "Europe's largest, to watch herons, storks and sea eagles.",
        'description': 'Kopački Rit is a vast floodplain where the Danube and Drava meet, in '
        'eastern Croatia. It is a protected nature park, and its channels and lakes are '
        'home to over 280 bird species, including white-tailed eagles, black storks and '
        'many herons.\n\n'
        'A park guide takes the group by boat along the channels at a slow pace for '
        'photographs and observation. Water levels change through the year, and the '
        'best birdwatching is in spring and early autumn. Bring binoculars if you have them.',
        'highlights': [
            'Boat through the Danube-Drava wetlands',
            'White-tailed eagles, herons and storks',
            'Park guide with local knowledge',
            'Quiet channels and lakes',
            'Good for photography',
        ],
        'included': ['Boat trip', 'Park guide', 'Park entry'],
        'not_included': ['Binoculars (bring your own)', 'Transport', 'Food'],
        'itinerary': [
            {'title': 'Park entrance', 'detail': 'Short introduction at the visitor centre.'},
            {'title': 'Boat trip', 'detail': 'About 2 hours along the channels.'},
            {'title': 'Return', 'detail': 'Time to ask questions at the end.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_SEASON, _FAQ_KIDS],
        'meeting_point': 'Kopački Rit visitor area, exact point confirmed with your booking',
        'latitude': 45.6167,
        'longitude': 18.9167,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Binoculars', 'Insect repellent', 'Hat', 'Light jacket'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'ilok-traminac-wine-cellars-tasting',
        'name': 'Ilok Cellars and Traminac Tasting on the Danube',
        'category': 'Wine',
        'region': 'continental',
        'location': 'Ilok',
        'image': 'wine.jpg',
        'price': 45,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': "Walk Ilok's old town and fortress, then taste Traminac and "
        'Graševina in a historic cellar above the Danube.',
        'description': 'Ilok is the easternmost town in Croatia, on a hill above the Danube. '
        'It has a medieval fortress, a Franciscan monastery and old cellars, and it is '
        'known for Traminac, an aromatic white wine whose grape has grown here for centuries.\n\n'
        'The tour walks through the walled old town and into a historic cellar for a '
        'tasting of three to four wines, including Traminac and Graševina, with local '
        'cheese. The cellar is cool all year round.',
        'highlights': [
            'Ilok fortress and old town',
            'Historic cellar tasting',
            'Traminac and Graševina',
            'View of the Danube',
            'Local cheese pairing',
        ],
        'included': ['Old town walk', 'Tasting of 3 to 4 wines', 'Local cheese'],
        'not_included': ['Transport to Ilok', 'Bottles to take home'],
        'itinerary': [
            {'title': 'Old town walk', 'detail': 'Fortress walls and the Danube view.'},
            {'title': 'Cellar', 'detail': 'How the wine is stored in the old cellars.'},
            {'title': 'Tasting', 'detail': 'Three to four wines with cheese.'},
        ],
        'faqs': [_FAQ_DRINK, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Ilok old town, exact point confirmed with your booking',
        'latitude': 45.2253,
        'longitude': 19.3769,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Light jacket for the cellar'],
        'daily_capacity': 14,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'trakoscan-castle-and-zagorje-hills-tour',
        'name': 'Trakošćan Castle and the Hills of Zagorje',
        'category': 'Culture',
        'region': 'continental',
        'location': 'Trakošćan Castle',
        'image': 'culture.jpg',
        'price': 42,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': 'Visit Trakošćan Castle on its lake in Zagorje, with a guided '
        'walk through the rooms and around the lakeside park.',
        'description': 'Trakošćan Castle stands on a wooded hill above an artificial lake in '
        'Hrvatsko zagorje, in the north of Croatia. It dates from the 13th century and '
        'was rebuilt in the 19th century in a romantic style, and now houses a museum '
        'with period furniture, weapons and portraits.\n\n'
        'A guide leads you through the rooms and then along the path around the lake, '
        'telling the story of the Drašković family who owned it. Castle entry is paid on '
        'site.',
        'highlights': [
            'Castle on a hilltop above a lake',
            'Museum rooms with period furniture',
            'The Drašković family story',
            'Walk around the lake park',
            'Green Zagorje countryside',
        ],
        'included': ['Local guide'],
        'not_included': ['Castle entry', 'Transport to the castle', 'Food and drinks'],
        'itinerary': [
            {'title': 'Castle rooms', 'detail': 'Guided visit inside the museum.'},
            {'title': 'Lake path', 'detail': 'A flat walk with views of the castle.'},
            {'title': 'Free time', 'detail': 'Café or the park at your own pace.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS, _FAQ_PICKUP],
        'meeting_point': 'Trakošćan Castle car park, exact point confirmed with your booking',
        'latitude': 46.2536,
        'longitude': 16.0339,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Comfortable shoes', 'Rain jacket'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
]
