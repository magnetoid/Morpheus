"""Croatia experiences: northern Dalmatia (Zadar, Šibenik) and Lika.

Each entry is a real activity at a real public place (national and nature parks, UNESCO
sites, towns). The host is the store itself, so no private operator is named. Prices are
typical 2026 per-person market prices in EUR. No reviews, ratings, "was" prices or
bestseller flags. Schema mirrors ``_experiences_data.py`` minus host and ratings.
"""

from __future__ import annotations

_FAQ_WEATHER = {
    'q': 'What happens if the weather is bad?',
    'a': (
        'If conditions make the experience unsafe, it is rescheduled free of charge or '
        'refunded in full. You are told at least 12 hours before the start time.'
    ),
}
_FAQ_PICKUP = {
    'q': 'Is hotel pickup included?',
    'a': (
        "Only if listed under What's included. Otherwise the exact meeting point is "
        'confirmed with your booking.'
    ),
}
_FAQ_KIDS = {
    'q': 'Is this suitable for children?',
    'a': (
        'Families are welcome. Confirm the minimum age when booking and mention the ages '
        'in your party.'
    ),
}
_FAQ_FITNESS = {
    'q': 'How fit do I need to be?',
    'a': (
        'A moderate fitness level is enough. The guide sets the pace with the group and '
        'adapts the route to conditions.'
    ),
}
_FAQ_SWIM = {
    'q': 'Do I need to be able to swim?',
    'a': 'Basic swimming ability is required; life jackets are provided and worn on the water.',
}
_FAQ_GEAR = {
    'q': 'Is equipment provided?',
    'a': (
        "All technical equipment is included, see What's included. You only need the "
        'personal items listed under What to bring.'
    ),
}
_FAQ_LANG = {
    'q': 'What languages does the guide speak?',
    'a': 'Departures run in English by default; Croatian is available on request.',
}
_FAQ_SEASON = {
    'q': 'When does this run?',
    'a': 'It operates seasonally, weather and water levels permitting. Dates are shown at booking.',
}
_FAQ_TICKET = {
    'q': 'Is the park entrance ticket included?',
    'a': (
        "Only if listed under What's included. Park tickets are set by the park and change "
        'by season, so check the listing before booking.'
    ),
}

_EN_HR = ['English', 'Croatian']
_EN_HR_DE = ['English', 'Croatian', 'German']
_EN_HR_IT = ['English', 'Croatian', 'Italian']

EXPERIENCES: list[dict] = [
    # ================= ZADAR =================
    {
        'slug': 'kornati-national-park-boat-day',
        'name': 'A Day Among the Kornati Islands',
        'category': 'Water Sports',
        'region': 'zadar',
        'location': 'Kornati National Park',
        'image': 'sailing.jpg',
        'price': 95,
        'duration_minutes': 480,
        'duration_label': '8 hours',
        'short_description': (
            'A full day by boat through the Kornati archipelago, with swim stops in clear '
            'coves and a lunch on board.'
        ),
        'description': (
            'The Kornati National Park holds around 140 islands, islets and reefs of bare '
            'white limestone, most of them uninhabited. This day trip crosses the '
            'archipelago by boat, passing the long cliffs on the seaward side of the outer '
            'islands and stopping in sheltered coves for a swim.\n\n'
            'Lunch is served on board, and there is time ashore on one of the islands to '
            'walk to a viewpoint over the channels. The park fee is paid separately on the '
            'day. The route depends on wind and sea state, and the skipper picks the coves '
            'that are calm.'
        ),
        'highlights': [
            'Boat route through the Kornati archipelago',
            'Swim stops in sheltered coves',
            'Walk to a viewpoint on one of the islands',
            'Lunch served on board',
            'Small group on a licensed boat',
        ],
        'included': ['Boat and skipper', 'Lunch and a drink on board', 'Snorkelling masks'],
        'not_included': ['Kornati National Park entrance fee', 'Transfer to the departure port'],
        'itinerary': [
            {'title': 'Departure', 'detail': 'Board in the morning and cross towards the park.'},
            {
                'title': 'Islands and coves',
                'detail': 'Cruise the outer islands, with two swim stops.',
            },
            {
                'title': 'Lunch and a walk',
                'detail': 'Lunch on board, then a short walk ashore to a viewpoint.',
            },
            {'title': 'Return', 'detail': 'Cruise back and arrive in the late afternoon.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_TICKET, _FAQ_KIDS, _FAQ_SEASON],
        'meeting_point': 'Departure port in the Zadar–Šibenik area, exact point confirmed with your booking',
        'latitude': 43.8000,
        'longitude': 15.3000,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Swimwear', 'Towel', 'Sun cream and a hat', 'Cash for the park fee'],
        'daily_capacity': 30,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'telascica-nature-park-dugi-otok-boat-day',
        'name': 'Telašćica Bay and the Cliffs of Dugi Otok',
        'category': 'Water Sports',
        'region': 'zadar',
        'location': 'Telašćica Nature Park',
        'image': 'sailing.jpg',
        'price': 80,
        'duration_minutes': 420,
        'duration_label': '7 hours',
        'short_description': (
            'A boat day to Telašćica Nature Park on Dugi Otok: the bay, the Stene cliffs and '
            'a swim in the salt lake.'
        ),
        'description': (
            'Telašćica is a long, sheltered bay on the south-east end of Dugi Otok, with a '
            'string of small islands inside it. The boat enters the bay from the open sea '
            'and stops for a swim before landing in the park.\n\n'
            'From the landing a path leads to the Stene cliffs, which drop about 160 m to '
            'the sea on the outer side of the island, and to Mir, a small salt lake that '
            'is saltier than the sea. Lunch is on board. The park fee is paid separately.'
        ),
        'highlights': [
            'Boat entry into Telašćica Bay',
            'Walk to the Stene cliffs',
            'Swim at the salt lake of Mir',
            'Swim stop in a cove',
            'Lunch served on board',
        ],
        'included': ['Boat and skipper', 'Lunch on board', 'Snorkelling masks'],
        'not_included': ['Telašćica Nature Park entrance fee', 'Transfer to the departure port'],
        'itinerary': [
            {'title': 'Crossing', 'detail': 'Depart in the morning and cross to Dugi Otok.'},
            {'title': 'Telašćica Bay', 'detail': 'Enter the bay and stop for a swim.'},
            {
                'title': 'Cliffs and salt lake',
                'detail': 'Walk to the Stene cliffs and the salt lake.',
            },
            {'title': 'Return', 'detail': 'Lunch on board while cruising back.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_TICKET, _FAQ_SWIM, _FAQ_SEASON],
        'meeting_point': 'Departure port near Zadar or Biograd, exact point confirmed with your booking',
        'latitude': 43.9000,
        'longitude': 15.1700,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Swimwear', 'Towel', 'Walking shoes', 'Sun cream and a hat'],
        'daily_capacity': 30,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'paklenica-canyon-hiking',
        'name': 'Hiking the Velika Paklenica Canyon',
        'category': 'Adventure',
        'region': 'zadar',
        'location': 'Paklenica National Park',
        'image': 'hiking.jpg',
        'price': 55,
        'duration_minutes': 300,
        'duration_label': '5 hours',
        'short_description': (
            'A guided walk up Velika Paklenica, between limestone walls of up to 400 m, to '
            'the old mill and the cave path.'
        ),
        'description': (
            'Paklenica National Park sits on the southern slopes of the Velebit range, '
            'above Starigrad. Velika Paklenica is its main canyon: a narrow gorge with '
            'vertical limestone walls, reached by a well-marked path from the park '
            'entrance.\n\n'
            'The guide leads the walk up the canyon floor, explains the geology, the '
            'beech and black pine forest and the history of the mill, and turns back at a '
            'point that suits the group. The walk is mostly on a gentle gradient. The '
            'park entrance fee is paid separately.'
        ),
        'highlights': [
            'Walk between canyon walls up to 400 m high',
            'Gentle path suitable for most walkers',
            'Beech and black pine forest',
            'Guide explains geology and wildlife',
            'Stop at the old mill',
        ],
        'included': ['Licensed hiking guide', 'Water refill and a snack'],
        'not_included': ['Paklenica National Park entrance fee', 'Transfer to Starigrad'],
        'itinerary': [
            {'title': 'Park entrance', 'detail': 'Meet at the entrance and set off up the canyon.'},
            {
                'title': 'Canyon floor',
                'detail': 'Walk the path beneath the cliffs, with photo stops.',
            },
            {'title': 'Old mill', 'detail': 'Rest at the mill, then walk back down.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_TICKET, _FAQ_KIDS, _FAQ_WEATHER],
        'meeting_point': 'Starigrad-Paklenica, exact point confirmed with your booking',
        'latitude': 44.3000,
        'longitude': 15.4400,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Walking shoes', 'Water bottle', 'Rain jacket', 'Sun cream and a hat'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'paklenica-sport-climbing-introduction',
        'name': 'Rock Climbing Introduction in Paklenica',
        'category': 'Adventure',
        'region': 'zadar',
        'location': 'Paklenica National Park',
        'image': 'hiking.jpg',
        'price': 85,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': (
            'A half day of guided sport climbing on the limestone of Paklenica, for beginners '
            'and climbers who want a guide.'
        ),
        'description': (
            'Paklenica is one of the best known climbing areas in Croatia, with bolted '
            'routes of many grades on compact limestone. This half day is led by a '
            'climbing guide and starts with knots, belaying and how to move on rock.\n\n'
            'Beginners climb easy, well-protected routes on top rope. Climbers with some '
            'experience can lead short routes with the guide beside them. The guide '
            'chooses the crag for the day depending on sun, wind and group level.'
        ),
        'highlights': [
            'Bolted limestone routes in a famous climbing area',
            'Instruction in knots and belaying',
            'Small groups with one guide',
            'Routes chosen for your level',
            'No experience needed',
        ],
        'included': ['Qualified climbing guide', 'Harness, helmet, rope and shoes', 'Insurance'],
        'not_included': ['Paklenica National Park entrance fee', 'Transfer to Starigrad'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'Fit equipment and learn knots and belay technique.'},
            {'title': 'Approach', 'detail': 'Short walk to the crag.'},
            {
                'title': 'Climbing',
                'detail': 'Climb several routes with the guide, with rest breaks.',
            },
        ],
        'faqs': [_FAQ_GEAR, _FAQ_FITNESS, _FAQ_WEATHER, _FAQ_TICKET],
        'meeting_point': 'Starigrad-Paklenica, exact point confirmed with your booking',
        'latitude': 44.3000,
        'longitude': 15.4400,
        'languages': _EN_HR,
        'what_to_bring': ['Sports clothes', 'Water bottle', 'Sun cream', 'Light backpack'],
        'daily_capacity': 8,
        'max_guests_per_booking': 4,
    },
    {
        'slug': 'zrmanja-river-kayaking',
        'name': 'Kayaking Down the Zrmanja River',
        'category': 'Water Sports',
        'region': 'zadar',
        'location': 'Zrmanja River',
        'image': 'kayak.jpg',
        'price': 60,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': (
            'A guided paddle on the Zrmanja through green canyon water, with swim stops and '
            'no experience needed.'
        ),
        'description': (
            'The Zrmanja runs from the Lika highlands through a limestone canyon to the '
            'Novigrad Sea. Its lower stretch is calm and clear, with low rapids and green '
            'water under steep rock walls.\n\n'
            'This guided paddle covers the gentler section in two-person kayaks. The guide '
            'gives a short lesson on land, leads the group on the water and stops for '
            'swims and a snack. Water levels in late summer can be low, and the guide '
            'adapts the route.'
        ),
        'highlights': [
            'Paddle through a limestone canyon',
            'Calm water suitable for beginners',
            'Swim stops in clear pools',
            'Short lesson before the start',
            'Small groups with one guide',
        ],
        'included': ['Kayak and paddles', 'Life jacket and dry bag', 'Guide', 'Snack and water'],
        'not_included': ['Transfer to Obrovac', 'Towel and swimwear'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'Meet, fit life jackets and learn the basics on land.'},
            {'title': 'Paddle', 'detail': 'Follow the river downstream with swim stops.'},
            {'title': 'Finish', 'detail': 'Reach the take-out and return to the start.'},
        ],
        'faqs': [_FAQ_SWIM, _FAQ_SEASON, _FAQ_WEATHER, _FAQ_GEAR],
        'meeting_point': 'Obrovac area, Zrmanja river bank, exact point confirmed with your booking',
        'latitude': 44.2000,
        'longitude': 15.6800,
        'languages': _EN_HR,
        'what_to_bring': ['Swimwear', 'Towel', 'Water shoes', 'Sun cream and a hat'],
        'daily_capacity': 24,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'zrmanja-river-rafting',
        'name': 'Rafting the Zrmanja Rapids',
        'category': 'Water Sports',
        'region': 'zadar',
        'location': 'Zrmanja River',
        'image': 'kayak.jpg',
        'price': 65,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': (
            'A guided raft trip on the Zrmanja, with moderate rapids, small drops and a swim '
            'stop in the canyon.'
        ),
        'description': (
            'The upper Zrmanja drops through a narrow limestone gorge with moderate '
            'rapids, small waterfalls and clear pools. A guided raft is a good way to see '
            'it if you want some excitement without technical skill.\n\n'
            'The guide briefs the group on paddle commands and safety, and steers the raft '
            'through the rapids while the group paddles. Rafting depends on water level, '
            'so it is offered in spring and early summer. Outside that period the '
            'experience may be switched to kayaking.'
        ),
        'highlights': [
            'Moderate rapids and small drops',
            'Limestone gorge and clear pools',
            'Guide steers the raft',
            'Swim stop on the way',
            'No experience needed',
        ],
        'included': ['Raft, paddles, helmet and life jacket', 'Wetsuit', 'Guide', 'Insurance'],
        'not_included': ['Transfer to Obrovac', 'Towel and swimwear'],
        'itinerary': [
            {'title': 'Safety briefing', 'detail': 'Fit equipment and learn paddle commands.'},
            {'title': 'Rapids', 'detail': 'Raft the gorge with a swim stop.'},
            {'title': 'Finish', 'detail': 'Take out and return to the start.'},
        ],
        'faqs': [_FAQ_SWIM, _FAQ_SEASON, _FAQ_KIDS, _FAQ_WEATHER],
        'meeting_point': 'Obrovac area, Zrmanja river bank, exact point confirmed with your booking',
        'latitude': 44.2000,
        'longitude': 15.6800,
        'languages': _EN_HR,
        'what_to_bring': ['Swimwear', 'Towel', 'Water shoes', 'Dry clothes'],
        'daily_capacity': 24,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'zadar-old-town-sea-organ-walk',
        'name': 'Zadar Old Town and the Sea Organ',
        'category': 'Culture',
        'region': 'zadar',
        'location': 'Zadar',
        'image': 'culture.jpg',
        'price': 25,
        'duration_minutes': 120,
        'duration_label': '2 hours',
        'short_description': (
            "A guided walk through Zadar's peninsula: Roman Forum, St Donatus, the Sea "
            'Organ and the Greeting to the Sun.'
        ),
        'description': (
            "Zadar's old town sits on a narrow peninsula, and two thousand years of its "
            'history are within a few streets. The walk starts at the Land Gate, '
            'one of the Venetian gates, and continues to the Roman Forum and the '
            'round pre-Romanesque Church of St Donatus.\n\n'
            'It ends on the waterfront, where the Sea Organ plays tones from the waves '
            'under the steps, and the Greeting to the Sun lights up a circle of glass at '
            'dusk. The guide explains how the city was shaped by Rome, Venice and the '
            'damage of the Second World War.'
        ),
        'highlights': [
            'Land Gate and the Venetian walls',
            'Roman Forum',
            'Church of St Donatus',
            'The Sea Organ',
            'Greeting to the Sun on the waterfront',
        ],
        'included': ['Licensed local guide'],
        'not_included': ['Entry to churches and museums', 'Food and drinks'],
        'itinerary': [
            {
                'title': 'Land Gate',
                'detail': 'Start at the Venetian gate and walk into the old town.',
            },
            {'title': 'Forum and St Donatus', 'detail': 'Roman remains and the round church.'},
            {
                'title': 'Waterfront',
                'detail': 'Listen to the Sea Organ and see the Greeting to the Sun.',
            },
        ],
        'faqs': [_FAQ_KIDS, _FAQ_LANG, _FAQ_WEATHER],
        'meeting_point': 'Land Gate area, Zadar, exact point confirmed with your booking',
        'latitude': 44.1194,
        'longitude': 15.2314,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes', 'Sun cream and a hat', 'Water bottle'],
        'daily_capacity': 25,
        'max_guests_per_booking': 12,
    },
    {
        'slug': 'pag-cheese-and-lace-day',
        'name': 'Pag Cheese, Salt and Lace',
        'category': 'Dining',
        'region': 'zadar',
        'location': 'Pag',
        'image': 'dining.jpg',
        'price': 70,
        'duration_minutes': 300,
        'duration_label': '5 hours',
        'short_description': (
            "A day on Pag island: tasting the island's sheep cheese, seeing Pag lace made "
            'and walking the old town.'
        ),
        'description': (
            'Pag is known for three things: its sheep cheese, its salt and its lace. The '
            "island's stony pastures are grazed by sheep, and the wind brings salt "
            'spray to the grass, which gives the cheese its flavour. Pag lace is made '
            "by hand with a needle and is on UNESCO's list of intangible heritage.\n\n"
            'The day combines a tasting of Pag cheese with local bread and olives, a '
            'stop to see lace being made, and a guided walk through the planned 15th '
            'century old town of Pag and its salt pans. Lunch is a light platter of '
            'island products.'
        ),
        'highlights': [
            'Pag sheep cheese tasting',
            "Pag lace, on UNESCO's intangible heritage list",
            'Walk through the 15th-century old town',
            'Salt pans of Pag',
            'Light lunch of island products',
        ],
        'included': ['Local guide', 'Cheese tasting and light lunch', 'Drinks with the tasting'],
        'not_included': ['Transfer to Pag', 'Lace and cheese for purchase'],
        'itinerary': [
            {'title': 'Old town', 'detail': 'Walk through Pag and its main square.'},
            {'title': 'Lace', 'detail': 'See how the lace is made.'},
            {'title': 'Cheese tasting', 'detail': 'Taste aged and young cheese with lunch.'},
            {'title': 'Salt pans', 'detail': 'Stop at the salt pans before the end.'},
        ],
        'faqs': [_FAQ_PICKUP, _FAQ_KIDS, _FAQ_WEATHER],
        'meeting_point': 'Pag town centre, exact point confirmed with your booking',
        'latitude': 44.4408,
        'longitude': 15.0536,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Sun hat', 'Cash for purchases'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'nin-salt-pans-and-old-town',
        'name': 'Nin: Salt Pans and the Old Royal Town',
        'category': 'Culture',
        'region': 'zadar',
        'location': 'Nin',
        'image': 'culture.jpg',
        'price': 35,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': (
            "A walk through Nin's island old town and its salt pans, with the story of "
            "Croatia's first rulers."
        ),
        'description': (
            'Nin sits on a small island in a lagoon, joined to the shore by two stone '
            'bridges. It was a seat of early Croatian rulers, and its 9th century Church '
            'of the Holy Cross is often called the smallest cathedral in the world.\n\n'
            'The guide leads a walk through the old town, past the Roman temple '
            'foundations and the monument to Bishop Grgur Ninski, then out to the salt '
            'pans, where salt is still gathered by hand in the season. A taste of '
            'the salt is part of the visit.'
        ),
        'highlights': [
            'Island old town reached by stone bridges',
            'Church of the Holy Cross',
            'Monument to Grgur Ninski',
            'Working salt pans',
            'Salt tasting',
        ],
        'included': ['Local guide', 'Salt tasting'],
        'not_included': ['Museum entry', 'Transfer to Nin'],
        'itinerary': [
            {'title': 'Old town', 'detail': 'Cross the bridge and walk through the island town.'},
            {'title': 'Holy Cross', 'detail': 'Visit the early medieval church.'},
            {'title': 'Salt pans', 'detail': 'Walk to the pans and taste the salt.'},
        ],
        'faqs': [_FAQ_KIDS, _FAQ_PICKUP, _FAQ_WEATHER],
        'meeting_point': 'Nin old town bridge, exact point confirmed with your booking',
        'latitude': 44.2406,
        'longitude': 15.1822,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Sun hat', 'Water bottle'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'vrana-lake-cycling-day',
        'name': 'Cycling Around Vrana Lake',
        'category': 'Adventure',
        'region': 'zadar',
        'location': 'Vrana Lake Nature Park',
        'image': 'hiking.jpg',
        'price': 40,
        'duration_minutes': 210,
        'duration_label': '3.5 hours',
        'short_description': (
            "A guided ride on flat tracks around Vrana Lake Nature Park, Croatia's "
            'largest natural lake, with birdwatching stops.'
        ),
        'description': (
            'Vrana Lake is the largest natural lake in Croatia. It lies a few hundred '
            'metres from the sea, and the park around it is a bird habitat with reeds, '
            'meadows and old farm tracks.\n\n'
            'The ride follows flat gravel and asphalt roads along the lake, with stops at '
            'viewpoints and the ruins of the old Ottoman caravanserai at Ostrovica '
            'direction. The guide points out herons, cormorants and other waterbirds. '
            'E-bikes can be added when booking.'
        ),
        'highlights': [
            'Largest natural lake in Croatia',
            'Flat tracks for all levels',
            'Waterbird viewpoints',
            'View across to the sea and the islands',
            'Bike and helmet included',
        ],
        'included': ['Bike and helmet', 'Guide', 'Water'],
        'not_included': ['Vrana Lake Nature Park fee', 'Transfer to the start'],
        'itinerary': [
            {'title': 'Bike fitting', 'detail': 'Choose a bike and set off.'},
            {'title': 'Lake ride', 'detail': 'Ride along the lake with viewpoint stops.'},
            {'title': 'Return', 'detail': 'Loop back to the start.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_KIDS, _FAQ_WEATHER, _FAQ_TICKET],
        'meeting_point': 'Vrana Lake Nature Park area, exact point confirmed with your booking',
        'latitude': 43.9300,
        'longitude': 15.5500,
        'languages': _EN_HR,
        'what_to_bring': ['Sports shoes', 'Sun cream and a hat', 'Water bottle'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    # ================= ŠIBENIK =================
    {
        'slug': 'krka-national-park-day-trip',
        'name': 'Krka National Park: Waterfalls and Boat Day',
        'category': 'Adventure',
        'region': 'sibenik',
        'location': 'Krka National Park',
        'image': 'hiking.jpg',
        'price': 65,
        'duration_minutes': 420,
        'duration_label': '7 hours',
        'short_description': (
            'A guided day in Krka National Park: the boardwalk at Skradinski buk, the '
            'museums and a boat ride on the river.'
        ),
        'description': (
            'The Krka River drops through a series of travertine waterfalls on its way to '
            'the sea. Skradinski buk, the lowest and largest, is crossed by a wooden '
            'boardwalk through reeds, pools and old watermills. Swimming at the falls has '
            'not been allowed since 2021.\n\n'
            'The guide leads the boardwalk walk, explains how travertine builds the '
            'falls, and visits the small ethnographic and hydroelectric exhibits. A '
            'boat ride on the river is part of the day. The park fee is paid '
            'separately and depends on the season.'
        ),
        'highlights': [
            'Boardwalk at Skradinski buk',
            'Travertine barriers and pools',
            'Old watermills and the ethnographic exhibit',
            'Boat ride on the Krka',
            "Guide explains the park's nature and history",
        ],
        'included': ['Licensed guide', 'Boat ride from Skradin'],
        'not_included': ['Krka National Park entrance fee', 'Lunch', 'Transfer to Skradin'],
        'itinerary': [
            {'title': 'Skradin', 'detail': 'Meet and take the boat up the river.'},
            {'title': 'Skradinski buk', 'detail': 'Walk the boardwalk, with time for photos.'},
            {'title': 'Exhibits', 'detail': 'See the mills and the exhibits, then free time.'},
            {'title': 'Return', 'detail': 'Boat back to Skradin.'},
        ],
        'faqs': [
            {
                'q': 'Can I swim at the falls?',
                'a': (
                    'No. Swimming in Krka National Park has been banned since 2021, and this '
                    'experience does not include it.'
                ),
            },
            _FAQ_TICKET,
            _FAQ_KIDS,
            _FAQ_WEATHER,
        ],
        'meeting_point': 'Skradin waterfront, exact point confirmed with your booking',
        'latitude': 43.8000,
        'longitude': 15.9700,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Walking shoes', 'Sun cream and a hat', 'Water bottle', 'Camera'],
        'daily_capacity': 24,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'skradin-old-town-and-krka-walk',
        'name': 'Skradin Old Town and Skradinski Buk Walk',
        'category': 'Culture',
        'region': 'sibenik',
        'location': 'Skradin',
        'image': 'culture.jpg',
        'price': 45,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': (
            "A short guided visit to Skradin's old town, then the boardwalk at "
            'Skradinski buk, without a full day commitment.'
        ),
        'description': (
            'Skradin is a small town on the Krka estuary, long a trading point between '
            'the sea and the interior. The walk starts in the old town with its Venetian '
            'streets and the Church of the Assumption, then crosses to the park by boat.\n\n'
            'The boardwalk at Skradinski buk takes about an hour at an easy pace. There is '
            'no swimming at the falls, which has been banned since 2021. This is a shorter '
            'alternative to the full Krka day trip.'
        ),
        'highlights': [
            'Skradin old town',
            'Boat to the park',
            'Boardwalk at Skradinski buk',
            'No full-day commitment',
            'Guide explains the river and the town',
        ],
        'included': ['Local guide', 'Boat from Skradin'],
        'not_included': ['Krka National Park entrance fee', 'Food and drinks'],
        'itinerary': [
            {'title': 'Old town', 'detail': "Walk through Skradin's streets."},
            {'title': 'Boat', 'detail': 'Cross to the park by boat.'},
            {'title': 'Boardwalk', 'detail': 'Walk the loop at Skradinski buk.'},
        ],
        'faqs': [_FAQ_TICKET, _FAQ_KIDS, _FAQ_WEATHER],
        'meeting_point': 'Skradin waterfront, exact point confirmed with your booking',
        'latitude': 43.8225,
        'longitude': 15.9242,
        'languages': _EN_HR,
        'what_to_bring': ['Walking shoes', 'Sun cream and a hat', 'Water bottle'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'sibenik-fortresses-and-cathedral-walk',
        'name': 'Šibenik: Cathedral and Fortresses',
        'category': 'Culture',
        'region': 'sibenik',
        'location': 'Šibenik',
        'image': 'culture.jpg',
        'price': 30,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': (
            'A guided walk through Šibenik: the UNESCO-listed Cathedral of St James and the '
            'fortresses above the old town.'
        ),
        'description': (
            'Šibenik was founded by Croats and has no Roman past, which sets it apart '
            'from other Dalmatian towns. Its Cathedral of St James, built in stone over '
            'more than a century, is on the UNESCO World Heritage list, and its barrel '
            'vault and carved faces of 71 figures on the apse are known across Europe.\n\n'
            'The walk climbs through the stepped lanes of the old town to the fortress of '
            'St Michael, and looks across to St Nicholas Fortress at the mouth of the '
            'channel, also on the UNESCO list as part of the Venetian defence works. '
            'Views over the harbour and the islands finish the walk.'
        ),
        'highlights': [
            'Cathedral of St James (UNESCO)',
            'Stepped lanes of the old town',
            'Fortress of St Michael with views',
            'View of St Nicholas Fortress',
            'Guide explains Venetian rule',
        ],
        'included': ['Licensed local guide'],
        'not_included': ['Cathedral and fortress entry fees', 'Food and drinks'],
        'itinerary': [
            {'title': 'Cathedral', 'detail': 'Outside and, if open, inside the cathedral.'},
            {'title': 'Old town', 'detail': 'Climb through the lanes.'},
            {'title': 'Fortress', 'detail': 'Panorama from St Michael.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_KIDS, _FAQ_WEATHER],
        'meeting_point': 'Republic Square, Šibenik, exact point confirmed with your booking',
        'latitude': 43.7350,
        'longitude': 15.8952,
        'languages': _EN_HR_IT,
        'what_to_bring': ['Comfortable shoes', 'Sun cream and a hat', 'Water bottle'],
        'daily_capacity': 25,
        'max_guests_per_booking': 12,
    },
    {
        'slug': 'primosten-babic-wine-tasting',
        'name': 'Babić Wine Tasting in Primošten',
        'category': 'Wine',
        'region': 'sibenik',
        'location': 'Primošten',
        'image': 'wine.jpg',
        'price': 55,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': (
            "A tasting of Primošten's red grape Babić among the stone-walled vineyards "
            'near the coast.'
        ),
        'description': (
            'Babić is the red grape of the Primošten area, grown on small plots '
            'in the red-brown karst soil. The vineyards around Primošten, at Bucavac, '
            "are terraced with dry stone walls and are on UNESCO's tentative "
            'list.\n\n'
            'The tasting covers three to four wines, with olive oil, bread and cured '
            'meat. A local guide explains the grape, the soil and why the vines are '
            'planted in small pockets between rocks. The visit starts with a short walk '
            'to a viewpoint over the vineyards and the coast.'
        ),
        'highlights': [
            'Babić, the grape of the Primošten area',
            'Stone-walled vineyards above the coast',
            'Three to four wines tasted',
            'Olive oil, bread and cured meat',
            'Viewpoint walk before the tasting',
        ],
        'included': ['Local guide', 'Wine tasting', 'Local snacks'],
        'not_included': ['Transfer to Primošten', 'Bottles for purchase'],
        'itinerary': [
            {'title': 'Walk to the viewpoint', 'detail': 'See the vineyards from above.'},
            {'title': 'Tasting', 'detail': 'Taste the wines with olive oil and snacks.'},
            {'title': 'Q&A', 'detail': 'Ask about vines, soil and the harvest.'},
        ],
        'faqs': [_FAQ_PICKUP, _FAQ_WEATHER, _FAQ_LANG],
        'meeting_point': 'Primošten town centre, exact point confirmed with your booking',
        'latitude': 43.5861,
        'longitude': 15.9257,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Sun hat'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'vodice-sea-kayaking',
        'name': 'Sea Kayaking from Vodice',
        'category': 'Water Sports',
        'region': 'sibenik',
        'location': 'Vodice',
        'image': 'kayak.jpg',
        'price': 50,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': (
            'A guided sea kayak along the Vodice coast and its small islands, with a swim stop.'
        ),
        'description': (
            'Vodice sits on a sheltered stretch of the Šibenik riviera, with small '
            'islands just offshore. The guide leads a paddle along the coast and across '
            'the channel to a nearby islet, over clear shallow water.\n\n'
            'The group paddles in two-person sea kayaks, with a short lesson before the '
            'start and a swim stop at a pebble cove. The route is chosen on the '
            'day depending on the wind.'
        ),
        'highlights': [
            'Sheltered coastal paddle',
            'Crossing to a nearby islet',
            'Swim stop in a cove',
            'Two-person sea kayaks',
            'Lesson before the start',
        ],
        'included': ['Kayak, paddle and life jacket', 'Guide', 'Dry bag'],
        'not_included': ['Towel and swimwear', 'Transfer to Vodice'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'Fit equipment and learn paddling basics.'},
            {'title': 'Paddle', 'detail': 'Follow the coast and cross to the islet.'},
            {'title': 'Swim and return', 'detail': 'Swim in a cove, then paddle back.'},
        ],
        'faqs': [_FAQ_SWIM, _FAQ_WEATHER, _FAQ_GEAR, _FAQ_KIDS],
        'meeting_point': 'Vodice waterfront, exact point confirmed with your booking',
        'latitude': 43.7606,
        'longitude': 15.7778,
        'languages': _EN_HR,
        'what_to_bring': ['Swimwear', 'Towel', 'Water shoes', 'Sun cream and a hat'],
        'daily_capacity': 20,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'murter-island-cycling-olive-groves',
        'name': 'Cycling Murter Island: Olives and Coves',
        'category': 'Adventure',
        'region': 'sibenik',
        'location': 'Murter',
        'image': 'hiking.jpg',
        'price': 35,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': (
            'A guided ride across Murter island through olive groves and dry-stone '
            'terraces to a quiet cove.'
        ),
        'description': (
            'Murter is joined to the mainland by a short bridge and is the usual gateway '
            'to the Kornati islands. Away from the harbour, the island is a mix of olive '
            'groves, dry-stone walls and small coves.\n\n'
            'The ride follows quiet roads and farm tracks with gentle hills, with a stop '
            'to taste local olive oil and a swim at a cove. E-bikes are available on '
            'request.'
        ),
        'highlights': [
            'Olive groves and dry-stone terraces',
            'Quiet roads and farm tracks',
            'Olive oil tasting',
            'Swim stop at a cove',
            'E-bikes available on request',
        ],
        'included': ['Bike and helmet', 'Guide', 'Olive oil tasting', 'Water'],
        'not_included': ['Transfer to Murter', 'Swimwear and towel'],
        'itinerary': [
            {'title': 'Start', 'detail': 'Fit bikes and ride out of town.'},
            {'title': 'Olive groves', 'detail': 'Ride the farm tracks and taste olive oil.'},
            {'title': 'Cove', 'detail': 'Swim at the cove, then ride back.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_KIDS, _FAQ_WEATHER],
        'meeting_point': 'Murter harbour, exact point confirmed with your booking',
        'latitude': 43.8176,
        'longitude': 15.5987,
        'languages': _EN_HR,
        'what_to_bring': ['Sports shoes', 'Swimwear', 'Sun cream and a hat'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'zlarin-island-sailing-day',
        'name': 'Zlarin Island by Boat from Šibenik',
        'category': 'Water Sports',
        'region': 'sibenik',
        'location': 'Zlarin',
        'image': 'sailing.jpg',
        'price': 55,
        'duration_minutes': 360,
        'duration_label': '6 hours',
        'short_description': (
            'A boat trip from Šibenik to car-free Zlarin, once known for its coral '
            'divers, with swims and time in the village.'
        ),
        'description': (
            'Zlarin is a small car-free island a short crossing from Šibenik. For '
            'centuries its people harvested red coral from the sea floor, and '
            'a few coral jewellery traditions survive on the island.\n\n'
            'The boat cruises the archipelago in the Šibenik channel, stops for a swim '
            'in a quiet bay and lands in Zlarin village for a walk and free time. Lunch '
            "is not included, so you can eat at one of the village's places."
        ),
        'highlights': [
            'Car-free island',
            'Coral-diving heritage',
            'Swim stop in a quiet bay',
            'Cruise through the Šibenik archipelago',
            'Free time in the village',
        ],
        'included': ['Boat and skipper', 'Snorkelling masks', 'Drinks on board'],
        'not_included': ['Lunch', 'Transfer to Šibenik'],
        'itinerary': [
            {'title': 'Departure', 'detail': 'Leave Šibenik harbour in the morning.'},
            {'title': 'Archipelago', 'detail': 'Cruise and swim in a bay.'},
            {'title': 'Zlarin', 'detail': 'Land and explore the village, then return.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_SWIM, _FAQ_KIDS, _FAQ_SEASON],
        'meeting_point': 'Šibenik waterfront, exact point confirmed with your booking',
        'latitude': 43.6958,
        'longitude': 15.8486,
        'languages': _EN_HR,
        'what_to_bring': ['Swimwear', 'Towel', 'Sun cream and a hat'],
        'daily_capacity': 24,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'drnis-mestrovic-otavice-cultural-day',
        'name': 'Drniš and the Meštrović Mausoleum at Otavice',
        'category': 'Culture',
        'region': 'sibenik',
        'location': 'Drniš',
        'image': 'culture.jpg',
        'price': 45,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': (
            'A half day in the hinterland near Drniš, the home country of the sculptor '
            'Ivan Meštrović, and his family mausoleum.'
        ),
        'description': (
            'Drniš lies inland of Šibenik, in the karst valley of the Čikola River. It is '
            'close to Otavice, the village where the sculptor Ivan Meštrović grew up and '
            'where he designed a family mausoleum in the 1920s.\n\n'
            'The visit combines a short walk in Drniš with the mausoleum, set in the '
            'landscape he came from. The guide explains his work, his link to this '
            'valley and the history of the region.'
        ),
        'highlights': [
            'Mausoleum designed by Ivan Meštrović',
            'Karst valley of the Čikola River',
            'Walk in Drniš',
            "Guide explains the sculptor's life",
            'Quiet, uncrowded inland Dalmatia',
        ],
        'included': ['Local guide'],
        'not_included': ['Entry fees', 'Transfer from Šibenik'],
        'itinerary': [
            {'title': 'Drniš', 'detail': 'Short walk through the town.'},
            {'title': 'Otavice', 'detail': 'Visit the mausoleum and the village.'},
            {'title': 'Return', 'detail': 'Drive back to the coast.'},
        ],
        'faqs': [_FAQ_PICKUP, _FAQ_KIDS, _FAQ_LANG],
        'meeting_point': 'Drniš town centre, exact point confirmed with your booking',
        'latitude': 43.8644,
        'longitude': 16.1592,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Sun hat', 'Water bottle'],
        'daily_capacity': 12,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'tribunj-sunrise-yoga-by-the-sea',
        'name': 'Sunrise Yoga in Tribunj',
        'category': 'Wellness',
        'region': 'sibenik',
        'location': 'Tribunj',
        'image': 'spa.jpg',
        'price': 30,
        'duration_minutes': 90,
        'duration_label': '90 minutes',
        'short_description': (
            'A gentle early-morning yoga class on the waterfront of Tribunj, a fishing '
            'village on a small peninsula.'
        ),
        'description': (
            'Tribunj is a small village on a peninsula between Vodice and Šibenik, with '
            'a narrow old centre and a quiet harbour. The class takes place on a terrace '
            'by the sea, before the day gets warm.\n\n'
            'It is a slow hatha-style session for all levels, with breathing and a short '
            'closing relaxation. Mats are provided. In rain the class moves indoors, '
            'to a covered space.'
        ),
        'highlights': [
            'Waterfront terrace at sunrise',
            'Gentle class for all levels',
            'Breathing and relaxation',
            'Mats provided',
            'Small group',
        ],
        'included': ['Qualified instructor', 'Yoga mat'],
        'not_included': ['Breakfast', 'Transfer to Tribunj'],
        'itinerary': [
            {'title': 'Arrival', 'detail': 'Settle on the terrace as the sun rises.'},
            {'title': 'Class', 'detail': 'Slow movement and breathing.'},
            {'title': 'Relaxation', 'detail': 'Finish with a short rest.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_SEASON, _FAQ_FITNESS],
        'meeting_point': 'Tribunj waterfront, exact point confirmed with your booking',
        'latitude': 43.7664,
        'longitude': 15.7494,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable clothes', 'Water bottle', 'A light layer'],
        'daily_capacity': 12,
        'max_guests_per_booking': 6,
    },
    # ================= LIKA =================
    {
        'slug': 'plitvice-lakes-guided-walk',
        'name': 'Plitvice Lakes: Guided Walk Through the Upper Lakes',
        'category': 'Adventure',
        'region': 'lika',
        'location': 'Plitvice Lakes National Park',
        'image': 'hiking.jpg',
        'price': 70,
        'duration_minutes': 240,
        'duration_label': '4 hours',
        'short_description': (
            'A guided walk on the boardwalks of the Upper Lakes at Plitvice, a UNESCO World '
            'Heritage Site.'
        ),
        'description': (
            'Plitvice Lakes National Park has sixteen terraced lakes joined by travertine '
            'barriers and waterfalls, and is on the UNESCO World Heritage list. The Upper '
            'Lakes sit in a dolomite valley, with clear water that changes colour with '
            'the light and the minerals.\n\n'
            'The guide leads a four-hour walk on the boardwalks along the lakes, explaining '
            'how travertine forms, the beech forest and the wildlife of the park. '
            'Swimming is not allowed anywhere in the park. The entrance ticket is paid '
            'separately and depends on the season.'
        ),
        'highlights': [
            'Boardwalks across the Upper Lakes',
            'Travertine barriers and waterfalls',
            'UNESCO World Heritage Site',
            'Beech forest and wildlife',
            'Guide explains how the lakes form',
        ],
        'included': ['Licensed park guide'],
        'not_included': ['Plitvice Lakes entrance ticket', 'Food and drinks'],
        'itinerary': [
            {'title': 'Entrance', 'detail': 'Meet at the entrance and walk to the lakes.'},
            {'title': 'Upper Lakes', 'detail': 'Follow the boardwalks past waterfalls.'},
            {'title': 'Viewpoints', 'detail': 'Photo stops, then walk back.'},
        ],
        'faqs': [
            {
                'q': 'Can I swim in the lakes?',
                'a': 'No. Swimming is not allowed anywhere in Plitvice Lakes National Park.',
            },
            _FAQ_TICKET,
            _FAQ_KIDS,
            _FAQ_WEATHER,
        ],
        'meeting_point': 'Plitvice Lakes National Park entrance, exact point confirmed with your booking',
        'latitude': 44.8654,
        'longitude': 15.5820,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Walking shoes', 'Rain jacket', 'Water bottle', 'Camera'],
        'daily_capacity': 24,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'plitvice-lakes-full-day-grand-tour',
        'name': 'Plitvice Lakes: Full-Day Grand Tour',
        'category': 'Adventure',
        'region': 'lika',
        'location': 'Plitvice Lakes National Park',
        'image': 'hiking.jpg',
        'price': 90,
        'duration_minutes': 360,
        'duration_label': '6 hours',
        'short_description': (
            'A full day at Plitvice: both the Upper and Lower Lakes, the park boat and '
            'shuttle, with a guide.'
        ),
        'description': (
            'This is the longer route through the park, covering both the Upper and Lower '
            'Lakes. It uses the electric boat across Kozjak Lake and the park shuttle, '
            'and walks the boardwalks to the largest waterfall, Veliki slap, about 78 m '
            'high.\n\n'
            'The guide keeps the group ahead of the crowds where possible and explains '
            'what makes the park a UNESCO site. The route involves around 8 km of walking '
            'on mostly flat boardwalks and some steps. The park ticket is bought separately.'
        ),
        'highlights': [
            'Upper and Lower Lakes in one day',
            'Boat across Kozjak Lake',
            'The 78 m Veliki slap waterfall',
            'Around 8 km on boardwalks',
            'UNESCO World Heritage Site',
        ],
        'included': ['Licensed park guide'],
        'not_included': ['Plitvice Lakes entrance ticket (includes boat and shuttle)', 'Lunch'],
        'itinerary': [
            {'title': 'Lower Lakes', 'detail': 'Walk down to Veliki slap and the canyon.'},
            {'title': 'Kozjak boat', 'detail': 'Cross the lake by electric boat.'},
            {'title': 'Upper Lakes', 'detail': 'Walk the boardwalks to the end of the route.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_TICKET, _FAQ_WEATHER, _FAQ_KIDS],
        'meeting_point': 'Plitvice Lakes National Park entrance, exact point confirmed with your booking',
        'latitude': 44.8654,
        'longitude': 15.5820,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Walking shoes', 'Rain jacket', 'Water bottle', 'Packed lunch'],
        'daily_capacity': 24,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'rastoke-slunj-waterfalls-walk',
        'name': 'Rastoke: Watermills and Waterfalls of Slunj',
        'category': 'Culture',
        'region': 'lika',
        'location': 'Rastoke',
        'image': 'culture.jpg',
        'price': 30,
        'duration_minutes': 120,
        'duration_label': '2 hours',
        'short_description': (
            'A guided walk through Rastoke, the old milling village where the Slunjčica '
            'River tumbles into the Korana.'
        ),
        'description': (
            'Rastoke is the old quarter of Slunj, where the Slunjčica River falls over '
            'travertine steps into the Korana. Small wooden watermills and houses are '
            'built on the rock between the waterfalls.\n\n'
            'The guide walks the footbridges and paths around the cascades, explains how '
            'the mills once ground grain and washed cloth, and points out the best '
            'viewpoints. It is a good stop on the road to or from Plitvice.'
        ),
        'highlights': [
            'Waterfalls in a village',
            'Wooden watermills on travertine',
            'Footbridges over the cascades',
            'Viewpoint over the Korana',
            'Easy walk for all ages',
        ],
        'included': ['Local guide'],
        'not_included': ['Food and drinks', 'Transfer to Slunj'],
        'itinerary': [
            {'title': 'Slunj', 'detail': 'Meet in the village and walk down to Rastoke.'},
            {'title': 'Cascades', 'detail': 'Cross the footbridges past the mills.'},
            {'title': 'Viewpoint', 'detail': 'See the confluence with the Korana.'},
        ],
        'faqs': [_FAQ_KIDS, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Slunj, Rastoke entrance, exact point confirmed with your booking',
        'latitude': 45.1167,
        'longitude': 15.5833,
        'languages': _EN_HR_DE,
        'what_to_bring': ['Non-slip shoes', 'Rain jacket', 'Camera'],
        'daily_capacity': 20,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'premuzic-trail-day-hike',
        'name': 'The Premužić Trail: A Day on the Velebit Ridge',
        'category': 'Adventure',
        'region': 'lika',
        'location': 'Northern Velebit National Park',
        'image': 'hiking.jpg',
        'price': 95,
        'duration_minutes': 540,
        'duration_label': '9 hours',
        'short_description': (
            'A guided day hike on a section of the Premužić Trail, a 1930s mountain path '
            'along the Velebit range in Northern Velebit National Park.'
        ),
        'description': (
            'The Premužić Trail was built in the 1930s by the engineer Ante Premužić and '
            'runs along the Velebit range for about 57 km through Northern Velebit and '
            'Paklenica. It is cut with such an even gradient that it can be walked '
            'for hours without steep climbs.\n\n'
            'The day hike follows a section of the trail in the northern part, with views '
            'of the Adriatic islands on one side and the beech and spruce forest on the '
            'other. The group is guided, carries lunch and is driven back to the start. '
            'Weather can change quickly, and the route may be shortened.'
        ),
        'highlights': [
            'A historic mountain trail with an even gradient',
            'Views to the Adriatic islands',
            'Beech and spruce forest',
            'Guided section with return transfer',
            'Karst rock formations',
        ],
        'included': ['Licensed mountain guide', 'Transfer back to the start', 'Insurance'],
        'not_included': [
            'Northern Velebit National Park fee',
            'Lunch (bring a packed lunch)',
            'Transfer to the start',
        ],
        'itinerary': [
            {'title': 'Start', 'detail': 'Meet and drive to the trailhead.'},
            {'title': 'Trail', 'detail': 'Walk a section of the Premužić Trail with breaks.'},
            {'title': 'Finish', 'detail': 'Reach the end of the section and transfer back.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_SEASON, _FAQ_TICKET],
        'meeting_point': 'Krasno or Gospić area, exact point confirmed with your booking',
        'latitude': 44.7000,
        'longitude': 15.0000,
        'languages': _EN_HR_DE,
        'what_to_bring': [
            'Hiking boots',
            'Rain jacket',
            'Packed lunch and water',
            'Sun cream and a hat',
        ],
        'daily_capacity': 12,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'northern-velebit-rozanski-kukovi-hike',
        'name': 'Hiking Rožanski and Hajdučki Kukovi',
        'category': 'Adventure',
        'region': 'lika',
        'location': 'Northern Velebit National Park',
        'image': 'hiking.jpg',
        'price': 110,
        'duration_minutes': 480,
        'duration_label': '8 hours',
        'short_description': (
            'A guided hike to the limestone towers of Rožanski and Hajdučki kukovi, the strict '
            'nature reserve zone of Northern Velebit.'
        ),
        'description': (
            'Rožanski and Hajdučki kukovi are fields of limestone peaks, towers and pits '
            'at the core of Northern Velebit National Park. The area is protected as a '
            'strict reserve, and visits follow marked paths only.\n\n'
            'The guide leads a day hike from the Zavižan area into the formations, '
            'explaining the karst, the rare plants and the geology. The path is rocky and '
            'involves some climbing, so it suits experienced walkers. A permit and fee '
            'for the reserve apply.'
        ),
        'highlights': [
            'Limestone towers and karst pits',
            'Marked paths in a strict nature reserve',
            'Rare mountain plants',
            'Views across to the sea',
            'Small groups with a guide',
        ],
        'included': ['Licensed mountain guide', 'Insurance'],
        'not_included': ['Park and reserve permit fees', 'Lunch', 'Transfer to the start'],
        'itinerary': [
            {'title': 'Zavižan', 'detail': 'Meet in the early morning and start the climb.'},
            {'title': 'Kukovi', 'detail': 'Walk the marked path through the formations.'},
            {'title': 'Return', 'detail': 'Descend by the same path.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_WEATHER, _FAQ_SEASON, _FAQ_TICKET],
        'meeting_point': 'Krasno or Zavižan area, exact point confirmed with your booking',
        'latitude': 44.8000,
        'longitude': 14.9700,
        'languages': _EN_HR,
        'what_to_bring': ['Hiking boots', 'Rain jacket', 'Packed lunch and water', 'Warm layer'],
        'daily_capacity': 10,
        'max_guests_per_booking': 6,
    },
    {
        'slug': 'gospic-tesla-smiljan-visit',
        'name': 'Smiljan: The Birthplace of Nikola Tesla',
        'category': 'Culture',
        'region': 'lika',
        'location': 'Gospić',
        'image': 'culture.jpg',
        'price': 35,
        'duration_minutes': 180,
        'duration_label': '3 hours',
        'short_description': (
            'A guided visit to Smiljan near Gospić, where Nikola Tesla was born, with the '
            'memorial centre and the Lika landscape.'
        ),
        'description': (
            'Nikola Tesla was born in 1856 in the village of Smiljan, a few kilometres '
            'from Gospić. The memorial centre there includes the house where he was born, '
            'the church where his father served as a priest and a museum with exhibits on '
            'his inventions.\n\n'
            'The guide explains his life, from this part of Lika to Prague, Budapest and '
            'New York, and what his work on alternating current changed. The visit ends '
            'with a short walk in the village and, time allowing, a stop in Gospić.'
        ),
        'highlights': [
            "Tesla's birthplace and the memorial centre",
            'Church of the Apostles Peter and Paul',
            'Exhibits on alternating current',
            'Guide explains his life and work',
            'Lika village landscape',
        ],
        'included': ['Local guide'],
        'not_included': ['Memorial centre entry fee', 'Transfer to Smiljan'],
        'itinerary': [
            {'title': 'Smiljan', 'detail': 'Visit the birthplace and church.'},
            {'title': 'Memorial centre', 'detail': 'See the exhibition on his inventions.'},
            {'title': 'Gospić', 'detail': 'Optional stop in the town centre.'},
        ],
        'faqs': [_FAQ_PICKUP, _FAQ_KIDS, _FAQ_LANG],
        'meeting_point': 'Gospić town centre, exact point confirmed with your booking',
        'latitude': 44.5461,
        'longitude': 15.3747,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Rain jacket'],
        'daily_capacity': 16,
        'max_guests_per_booking': 8,
    },
    {
        'slug': 'cerovac-caves-guided-tour',
        'name': 'Underground at the Cerovac Caves',
        'category': 'Adventure',
        'region': 'lika',
        'location': 'Cerovac Caves',
        'image': 'hiking.jpg',
        'price': 25,
        'duration_minutes': 90,
        'duration_label': '90 minutes',
        'short_description': (
            'A guided walk through the Cerovac Caves near Gračac: stalactites, '
            'stalagmites and the cool air of the karst.'
        ),
        'description': (
            'The Cerovac Caves are a system of limestone caves on the southern slopes of '
            'Velebit, near Gračac. A guided route of part of the system shows chambers with '
            'stalactites, stalagmites and calcite formations, and explains how the '
            'caves were found and studied.\n\n'
            'It is cool underground at any time of year, so bring a warm '
            'layer. The paths are uneven and damp. Helmets and lights are provided. '
            'The tour does not suit anyone who is afraid of dark or confined spaces.'
        ),
        'highlights': [
            'Stalactites and stalagmites',
            'Chambers in the Lika karst',
            'Helmet and light provided',
            'Cool at any time of year',
            'Guide explains the geology',
        ],
        'included': ['Cave guide', 'Helmet and lamp', 'Entrance'],
        'not_included': ['Transfer to the caves', 'Food and drinks'],
        'itinerary': [
            {'title': 'Briefing', 'detail': 'Fit helmets and lights.'},
            {'title': 'Cave route', 'detail': 'Walk through the chambers with stops.'},
            {'title': 'Exit', 'detail': 'Return to the surface.'},
        ],
        'faqs': [_FAQ_FITNESS, _FAQ_KIDS, _FAQ_SEASON, _FAQ_GEAR],
        'meeting_point': 'The cave entrance near Gračac, exact point confirmed with your booking',
        'latitude': 44.2719,
        'longitude': 15.8922,
        'languages': _EN_HR,
        'what_to_bring': ['Sturdy shoes', 'Warm jacket'],
        'daily_capacity': 24,
        'max_guests_per_booking': 10,
    },
    {
        'slug': 'krasno-velebit-forest-bathing',
        'name': 'Forest Bathing Above Krasno',
        'category': 'Wellness',
        'region': 'lika',
        'location': 'Krasno',
        'image': 'spa.jpg',
        'price': 45,
        'duration_minutes': 150,
        'duration_label': '2.5 hours',
        'short_description': (
            'A slow, guided walk in the beech and spruce forest on the edge of Northern '
            'Velebit, with breathing and quiet pauses.'
        ),
        'description': (
            'Krasno is a small village on the northern side of the Velebit range, in the '
            'forests that surround the national park. Forest bathing is not exercise but '
            'a slow walk, with time to stop, listen and look.\n\n'
            'The guide leads easy exercises in breathing and attention, with pauses in '
            'clearings and a hot herbal tea at the end. The route is short and flat, so '
            'it suits all ages. Mid-summer evenings and autumn are especially pleasant.'
        ),
        'highlights': [
            'Beech and spruce forest at the edge of the national park',
            'Slow walk with quiet pauses',
            'Breathing and attention exercises',
            'Hot herbal tea',
            'Short and flat, suits all ages',
        ],
        'included': ['Guide', 'Herbal tea'],
        'not_included': ['Transfer to Krasno'],
        'itinerary': [
            {'title': 'Start', 'detail': 'Meet at the village and walk into the forest.'},
            {'title': 'Slow walk', 'detail': 'Guided exercises and pauses.'},
            {'title': 'Tea', 'detail': 'End with a hot herbal tea.'},
        ],
        'faqs': [_FAQ_WEATHER, _FAQ_KIDS, _FAQ_SEASON],
        'meeting_point': 'Krasno village, exact point confirmed with your booking',
        'latitude': 44.8239,
        'longitude': 14.9647,
        'languages': _EN_HR,
        'what_to_bring': ['Walking shoes', 'A warm layer', 'Rain jacket'],
        'daily_capacity': 10,
        'max_guests_per_booking': 6,
    },
    {
        'slug': 'gacka-river-walk-and-trout-lunch',
        'name': 'The Gacka River Walk and Trout Lunch',
        'category': 'Dining',
        'region': 'lika',
        'location': 'Gacka River',
        'image': 'dining.jpg',
        'price': 50,
        'duration_minutes': 210,
        'duration_label': '3.5 hours',
        'short_description': (
            'A guided walk along the clear Gacka River near Otočac, followed by a lunch of '
            'river trout and Lika sides.'
        ),
        'description': (
            'The Gacka is a spring-fed river in the Lika karst, known for its cold, clear '
            'water and its trout. Stone mills and small bridges line the banks '
            'near Otočac and Sinac.\n\n'
            'The guide leads an easy walk along the river and explains how the water '
            'comes underground from the karst and why the trout live here. Lunch follows '
            'with trout and local sides such as Lika potatoes. Vegetarian choices '
            'can be requested when booking.'
        ),
        'highlights': [
            'Clear spring-fed river',
            'Old stone mills and bridges',
            'Easy walk on level paths',
            'Trout lunch with Lika sides',
            'Vegetarian choice on request',
        ],
        'included': ['Local guide', 'Lunch and a drink'],
        'not_included': ['Transfer to Otočac', 'Additional drinks'],
        'itinerary': [
            {'title': 'River walk', 'detail': 'Walk along the banks near Otočac.'},
            {'title': 'Mills and bridges', 'detail': 'Learn how the water and mills worked.'},
            {'title': 'Lunch', 'detail': 'Eat trout with local sides.'},
        ],
        'faqs': [_FAQ_KIDS, _FAQ_WEATHER, _FAQ_PICKUP],
        'meeting_point': 'Otočac, Gacka river bank, exact point confirmed with your booking',
        'latitude': 44.8689,
        'longitude': 15.2331,
        'languages': _EN_HR,
        'what_to_bring': ['Comfortable shoes', 'Rain jacket', 'Camera'],
        'daily_capacity': 14,
        'max_guests_per_booking': 8,
    },
]
