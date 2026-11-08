"""Real Croatian hotels for croatia-experience.me (``manage.py seed_croatia``).

Name, type, official star category (0 when unsure), region, town and a short
factual description only: no rooms, rates, ratings or amenities. A guest sends an enquiry.
"""

from __future__ import annotations

HOTELS: list[dict] = [
    {
        'name': 'Grand Park Hotel Rovinj',
        'slug': 'grand-park-hotel-rovinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A hotel on the Rovinj peninsula.',
        'description': 'Grand Park Hotel Rovinj is in Rovinj, a coastal town on the west coast of '
        'Istria with a Venetian-style old town on a peninsula, dominated by the '
        'Church of St Euphemia.\n'
        '\n'
        'It is a hotel on the Rovinj peninsula.',
    },
    {
        'name': 'Hotel Monte Mulini',
        'slug': 'hotel-monte-mulini-rovinj',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A hotel on the Cuvi bay, a short walk from the old town in Rovinj.',
        'description': 'Hotel Monte Mulini is in Rovinj, a coastal town on the west coast of Istria '
        'with a Venetian-style old town on a peninsula, dominated by the Church of St '
        'Euphemia.\n'
        '\n'
        'It is a hotel on the Cuvi bay, a short walk from the old town.',
    },
    {
        'name': 'Hotel Lone',
        'slug': 'hotel-lone-rovinj',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A design hotel near Monte Mulini park in Rovinj.',
        'description': 'Hotel Lone is in Rovinj, a coastal town on the west coast of Istria with a '
        'Venetian-style old town on a peninsula, dominated by the Church of St '
        'Euphemia.\n'
        '\n'
        'It is a design hotel near Monte Mulini park.',
    },
    {
        'name': 'Hotel Adriatic',
        'slug': 'hotel-adriatic-rovinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A hotel at the foot of the old town, facing the harbour in Rovinj.',
        'description': 'Hotel Adriatic is in Rovinj, a coastal town on the west coast of Istria with '
        'a Venetian-style old town on a peninsula, dominated by the Church of St '
        'Euphemia.\n'
        '\n'
        'It is a hotel at the foot of the old town, facing the harbour.',
    },
    {
        'name': 'Hotel Eden',
        'slug': 'hotel-eden-rovinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A hotel in the Monsena bay area south of the old town in Rovinj.',
        'description': 'Hotel Eden is in Rovinj, a coastal town on the west coast of Istria with a '
        'Venetian-style old town on a peninsula, dominated by the Church of St '
        'Euphemia.\n'
        '\n'
        'It is a hotel in the Monsena bay area south of the old town.',
    },
    {
        'name': "Hotel Villa Angelo d'Oro",
        'slug': 'hotel-villa-angelo-d-oro-rovinj',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A boutique hotel in a restored Venetian-style house in the old town in '
        'Rovinj.',
        'description': "Hotel Villa Angelo d'Oro is in Rovinj, a coastal town on the west coast of "
        'Istria with a Venetian-style old town on a peninsula, dominated by the '
        'Church of St Euphemia.\n'
        '\n'
        'It is a boutique hotel in a restored Venetian-style house in the old town.',
    },
    {
        'name': 'Hotel Casa Garzotto',
        'slug': 'hotel-casa-garzotto-rovinj',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A small boutique hotel in the old town in Rovinj.',
        'description': 'Hotel Casa Garzotto is in Rovinj, a coastal town on the west coast of Istria '
        'with a Venetian-style old town on a peninsula, dominated by the Church of St '
        'Euphemia.\n'
        '\n'
        'It is a small boutique hotel in the old town.',
    },
    {
        'name': 'Hotel Istra',
        'slug': 'hotel-istra-rovinj',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Rovinj',
        'short_description': 'A hotel on the island of Sveti Andrija, reached by boat from Rovinj.',
        'description': 'Hotel Istra is in Rovinj, a coastal town on the west coast of Istria with a '
        'Venetian-style old town on a peninsula, dominated by the Church of St '
        'Euphemia.\n'
        '\n'
        'It is a hotel on the island of Sveti Andrija, reached by boat from Rovinj.',
    },
    {
        'name': 'Valamar Isabella Island Resort',
        'slug': 'valamar-isabella-island-resort-porec',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Poreč',
        'short_description': 'A resort on the small island of Sveti Nikola, reached by a short boat '
        'ride from Poreč.',
        'description': 'Valamar Isabella Island Resort is in Poreč, a coastal town on the west coast '
        'of Istria; its Euphrasian Basilica is a UNESCO World Heritage Site.\n'
        '\n'
        'It is a resort on the small island of Sveti Nikola, reached by a short boat '
        'ride from Poreč.',
    },
    {
        'name': 'Hotel Valamar Diamant',
        'slug': 'hotel-valamar-diamant-porec',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Poreč',
        'short_description': 'A hotel on the Brulo peninsula, south of the old town in Poreč.',
        'description': 'Hotel Valamar Diamant is in Poreč, a coastal town on the west coast of '
        'Istria; its Euphrasian Basilica is a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on the Brulo peninsula, south of the old town.',
    },
    {
        'name': 'Hotel Valamar Riviera',
        'slug': 'hotel-valamar-riviera-porec',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Poreč',
        'short_description': 'A hotel on the seafront promenade of Poreč.',
        'description': 'Hotel Valamar Riviera is in Poreč, a coastal town on the west coast of '
        'Istria; its Euphrasian Basilica is a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on the seafront promenade of Poreč.',
    },
    {
        'name': 'Hotel Parentium',
        'slug': 'hotel-parentium-porec',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'istria',
        'location': 'Poreč',
        'short_description': 'A hotel in the Plava Laguna holiday area south of Poreč.',
        'description': 'Hotel Parentium is in Poreč, a coastal town on the west coast of Istria; its '
        'Euphrasian Basilica is a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel in the Plava Laguna holiday area south of Poreč.',
    },
    {
        'name': 'Grand Hotel Brioni Pula',
        'slug': 'grand-hotel-brioni-pula',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'istria',
        'location': 'Pula',
        'short_description': 'A historic seafront hotel in Pula.',
        'description': 'Grand Hotel Brioni Pula is in Pula, the largest city of Istria, known for '
        'its well-preserved Roman amphitheatre.\n'
        '\n'
        'It is a historic seafront hotel in Pula.',
    },
    {
        'name': 'Hotel Amfiteatar',
        'slug': 'hotel-amfiteatar-pula',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'istria',
        'location': 'Pula',
        'short_description': 'A small hotel a short walk from the Roman amphitheatre in Pula.',
        'description': 'Hotel Amfiteatar is in Pula, the largest city of Istria, known for its '
        'well-preserved Roman amphitheatre.\n'
        '\n'
        'It is a small hotel a short walk from the Roman amphitheatre.',
    },
    {
        'name': 'Hotel Scaletta',
        'slug': 'hotel-scaletta-pula',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Pula',
        'short_description': 'A hotel close to the centre of Pula.',
        'description': 'Hotel Scaletta is in Pula, the largest city of Istria, known for its '
        'well-preserved Roman amphitheatre.\n'
        '\n'
        'It is a hotel close to the centre of Pula.',
    },
    {
        'name': 'Park Plaza Histria Pula',
        'slug': 'park-plaza-histria-pula',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Pula',
        'short_description': 'A hotel on the Verudela peninsula, south of the city in Pula.',
        'description': 'Park Plaza Histria Pula is in Pula, the largest city of Istria, known for '
        'its well-preserved Roman amphitheatre.\n'
        '\n'
        'It is a hotel on the Verudela peninsula, south of the city.',
    },
    {
        'name': 'Hotel Sol Garden Istra',
        'slug': 'hotel-sol-garden-istra-umag',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Umag',
        'short_description': 'A holiday hotel on the coast near Umag.',
        'description': 'Hotel Sol Garden Istra is in Umag, a coastal town in the north-west of '
        'Istria, close to the Slovenian border.\n'
        '\n'
        'It is a holiday hotel on the coast near Umag.',
    },
    {
        'name': 'Hotel Meliá Coral',
        'slug': 'hotel-melia-coral-umag',
        'property_type': 'resort',
        'star_rating': 0,
        'region': 'istria',
        'location': 'Umag',
        'short_description': 'A coastal holiday hotel near Umag.',
        'description': 'Hotel Meliá Coral is in Umag, a coastal town in the north-west of Istria, '
        'close to the Slovenian border.\n'
        '\n'
        'It is a coastal holiday hotel near Umag.',
    },
    {
        'name': 'Kempinski Hotel Adriatic',
        'slug': 'kempinski-hotel-adriatic-savudrija',
        'property_type': 'resort',
        'star_rating': 5,
        'region': 'istria',
        'location': 'Savudrija',
        'short_description': 'A seaside resort hotel in a pine park on the coast in Savudrija.',
        'description': 'Kempinski Hotel Adriatic is in Savudrija, a village at the north-western tip '
        'of Istria, close to the Slovenian border.\n'
        '\n'
        'It is a seaside resort hotel in a pine park on the coast.',
    },
    {
        'name': 'Hotel Kaštel Motovun',
        'slug': 'hotel-kastel-motovun',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Motovun',
        'short_description': 'A heritage hotel in the old town of Motovun.',
        'description': 'Hotel Kaštel Motovun is in Motovun, a hill town in the interior of Istria, '
        'above the valley of the Mirna river.\n'
        '\n'
        'It is a heritage hotel in the old town of Motovun.',
    },
    {
        'name': 'Hotel San Rocco',
        'slug': 'hotel-san-rocco-brtonigla',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'istria',
        'location': 'Brtonigla',
        'short_description': 'A family-run boutique hotel in the village in Brtonigla.',
        'description': 'Hotel San Rocco is in Brtonigla, a village in north-western Istria, in wine '
        'country between Umag and Novigrad.\n'
        '\n'
        'It is a family-run boutique hotel in the village.',
    },
    {
        'name': 'Hotel Kvarner',
        'slug': 'hotel-kvarner-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A historic hotel on the Opatija seafront, dating from the 1880s.',
        'description': 'Hotel Kvarner is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a historic hotel on the Opatija seafront, dating from the 1880s.',
    },
    {
        'name': 'Grand Hotel Adriatic',
        'slug': 'grand-hotel-adriatic-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A seafront hotel on the Lungomare promenade in Opatija.',
        'description': 'Grand Hotel Adriatic is in Opatija, a seaside resort on the Kvarner Bay, at '
        'the foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a seafront hotel on the Lungomare promenade.',
    },
    {
        'name': 'Hotel Milenij',
        'slug': 'hotel-milenij-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A hotel in a historic building on the Opatija seafront.',
        'description': 'Hotel Milenij is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a hotel in a historic building on the Opatija seafront.',
    },
    {
        'name': 'Hotel Ambassador',
        'slug': 'hotel-ambassador-opatija',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A hotel on the Opatija seafront.',
        'description': 'Hotel Ambassador is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a hotel on the Opatija seafront.',
    },
    {
        'name': 'Hotel Bristol',
        'slug': 'hotel-bristol-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A historic hotel in the centre of Opatija.',
        'description': 'Hotel Bristol is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a historic hotel in the centre of Opatija.',
    },
    {
        'name': 'Hotel Astoria',
        'slug': 'hotel-astoria-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A hotel in a former Habsburg-era building in the centre in Opatija.',
        'description': 'Hotel Astoria is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a hotel in a former Habsburg-era building in the centre.',
    },
    {
        'name': 'Hotel Mozart',
        'slug': 'hotel-mozart-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A boutique-style hotel in a historic Opatija villa.',
        'description': 'Hotel Mozart is in Opatija, a seaside resort on the Kvarner Bay, at the foot '
        'of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a boutique-style hotel in a historic Opatija villa.',
    },
    {
        'name': 'Hotel Imperial',
        'slug': 'hotel-imperial-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A historic hotel on the Opatija seafront.',
        'description': 'Hotel Imperial is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a historic hotel on the Opatija seafront.',
    },
    {
        'name': 'Hotel Villa Ariston',
        'slug': 'hotel-villa-ariston-opatija',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A historic villa hotel on the Lungomare promenade in Opatija.',
        'description': 'Hotel Villa Ariston is in Opatija, a seaside resort on the Kvarner Bay, at '
        'the foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a historic villa hotel on the Lungomare promenade.',
    },
    {
        'name': 'Hotel Lungomare',
        'slug': 'hotel-lungomare-opatija',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Opatija',
        'short_description': 'A hotel on the Lungomare promenade in Opatija.',
        'description': 'Hotel Lungomare is in Opatija, a seaside resort on the Kvarner Bay, at the '
        'foot of Mount Učka, popular since the Habsburg era.\n'
        '\n'
        'It is a hotel on the Lungomare promenade.',
    },
    {
        'name': 'Hotel Continental Rijeka',
        'slug': 'hotel-continental-rijeka',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Rijeka',
        'short_description': 'A historic city hotel in the centre of Rijeka.',
        'description': "Hotel Continental Rijeka is in Rijeka, Croatia's main port city, on the "
        'Kvarner Bay.\n'
        '\n'
        'It is a historic city hotel in the centre of Rijeka.',
    },
    {
        'name': 'Hotel Bonavia',
        'slug': 'hotel-bonavia-rijeka',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Rijeka',
        'short_description': 'A city hotel in the centre of Rijeka.',
        'description': "Hotel Bonavia is in Rijeka, Croatia's main port city, on the Kvarner Bay.\n"
        '\n'
        'It is a city hotel in the centre of Rijeka.',
    },
    {
        'name': 'Hotel Esplanade',
        'slug': 'hotel-esplanade-crikvenica',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'kvarner',
        'location': 'Crikvenica',
        'short_description': 'A historic seafront hotel in Crikvenica.',
        'description': 'Hotel Esplanade is in Crikvenica, a seaside town on the Kvarner Riviera, '
        'facing the island of Krk.\n'
        '\n'
        'It is a historic seafront hotel in Crikvenica.',
    },
    {
        'name': 'Valamar Koralj Romantic Hotel',
        'slug': 'valamar-koralj-romantic-hotel-krk',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'kvarner',
        'location': 'Krk',
        'short_description': 'A hotel on the waterfront near the old town of Krk.',
        'description': 'Valamar Koralj Romantic Hotel is in Krk, the main town on the island of Krk, '
        'with a walled old centre and a cathedral.\n'
        '\n'
        'It is a hotel on the waterfront near the old town of Krk.',
    },
    {
        'name': 'Hotel Malin',
        'slug': 'hotel-malin-malinska',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'kvarner',
        'location': 'Malinska',
        'short_description': 'A seaside hotel in Malinska.',
        'description': 'Hotel Malin is in Malinska, a village on the north-west coast of the island '
        'of Krk.\n'
        '\n'
        'It is a seaside hotel in Malinska.',
    },
    {
        'name': 'Hotel Imperial Rab',
        'slug': 'hotel-imperial-rab',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Rab',
        'short_description': 'A seafront hotel near the old town of Rab.',
        'description': 'Hotel Imperial Rab is in Rab, the main town on the island of Rab, known for '
        'its four medieval bell towers.\n'
        '\n'
        'It is a seafront hotel near the old town of Rab.',
    },
    {
        'name': 'Valamar Carolina Hotel & Villas',
        'slug': 'valamar-carolina-hotel-villas-rab',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Rab',
        'short_description': 'A hotel on the coast close to Rab old town.',
        'description': 'Valamar Carolina Hotel & Villas is in Rab, the main town on the island of '
        'Rab, known for its four medieval bell towers.\n'
        '\n'
        'It is a hotel on the coast close to Rab old town.',
    },
    {
        'name': 'Hotel Arbiana',
        'slug': 'hotel-arbiana-rab',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Rab',
        'short_description': 'A boutique hotel on the Rab waterfront.',
        'description': 'Hotel Arbiana is in Rab, the main town on the island of Rab, known for its '
        'four medieval bell towers.\n'
        '\n'
        'It is a boutique hotel on the Rab waterfront.',
    },
    {
        'name': 'Hotel Bellevue',
        'slug': 'hotel-bellevue-mali-losinj',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Mali Lošinj',
        'short_description': 'A hotel in the Čikat bay area, among pine woods in Mali Lošinj.',
        'description': 'Hotel Bellevue is in Mali Lošinj, the main town on the island of Lošinj in '
        'the Kvarner archipelago.\n'
        '\n'
        'It is a hotel in the Čikat bay area, among pine woods.',
    },
    {
        'name': 'Hotel Aurora',
        'slug': 'hotel-aurora-mali-losinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Mali Lošinj',
        'short_description': 'A hotel in the Čikat bay area, among pine woods in Mali Lošinj.',
        'description': 'Hotel Aurora is in Mali Lošinj, the main town on the island of Lošinj in the '
        'Kvarner archipelago.\n'
        '\n'
        'It is a hotel in the Čikat bay area, among pine woods.',
    },
    {
        'name': 'Hotel Vespera',
        'slug': 'hotel-vespera-mali-losinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Mali Lošinj',
        'short_description': 'A hotel in the Čikat bay area in Mali Lošinj.',
        'description': 'Hotel Vespera is in Mali Lošinj, the main town on the island of Lošinj in '
        'the Kvarner archipelago.\n'
        '\n'
        'It is a hotel in the Čikat bay area.',
    },
    {
        'name': 'Hotel Alhambra',
        'slug': 'hotel-alhambra-mali-losinj',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Mali Lošinj',
        'short_description': 'A boutique hotel in a historic villa near the harbour in Mali Lošinj.',
        'description': 'Hotel Alhambra is in Mali Lošinj, the main town on the island of Lošinj in '
        'the Kvarner archipelago.\n'
        '\n'
        'It is a boutique hotel in a historic villa near the harbour.',
    },
    {
        'name': 'Hotel Apoksiomen',
        'slug': 'hotel-apoksiomen-mali-losinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Mali Lošinj',
        'short_description': 'A hotel on the waterfront near the town centre in Mali Lošinj.',
        'description': 'Hotel Apoksiomen is in Mali Lošinj, the main town on the island of Lošinj in '
        'the Kvarner archipelago.\n'
        '\n'
        'It is a hotel on the waterfront near the town centre.',
    },
    {
        'name': 'Hotel Punta',
        'slug': 'hotel-punta-veli-losinj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'kvarner',
        'location': 'Veli Lošinj',
        'short_description': 'A hotel by the sea in the village in Veli Lošinj.',
        'description': 'Hotel Punta is in Veli Lošinj, a fishing village on the island of Lošinj in '
        'the Kvarner archipelago.\n'
        '\n'
        'It is a hotel by the sea in the village.',
    },
    {
        'name': 'Hotel Kimen',
        'slug': 'hotel-kimen-cres',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'kvarner',
        'location': 'Cres',
        'short_description': 'A seaside hotel on the edge of the town of Cres.',
        'description': 'Hotel Kimen is in Cres, the main town on the island of Cres in the Kvarner '
        'archipelago.\n'
        '\n'
        'It is a seaside hotel on the edge of the town of Cres.',
    },
    {
        'name': 'Hotel Nehaj',
        'slug': 'hotel-nehaj-senj',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'kvarner',
        'location': 'Senj',
        'short_description': 'A hotel on the coast near the old town of Senj.',
        'description': 'Hotel Nehaj is in Senj, a historic coastal town below the Velebit mountains, '
        'with the Nehaj fortress above it.\n'
        '\n'
        'It is a hotel on the coast near the old town of Senj.',
    },
    {
        'name': 'Hotel Jezero',
        'slug': 'hotel-jezero-plitvice-lakes',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'lika',
        'location': 'Plitvice Lakes',
        'short_description': 'A hotel run within Plitvice Lakes National Park.',
        'description': 'Hotel Jezero is in Plitvice Lakes, the area around Plitvice Lakes National '
        'Park, a UNESCO World Heritage Site in the Lika region.\n'
        '\n'
        'It is a hotel run within Plitvice Lakes National Park.',
    },
    {
        'name': 'Hotel Plitvice',
        'slug': 'hotel-plitvice-plitvice-lakes',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'lika',
        'location': 'Plitvice Lakes',
        'short_description': 'A hotel run within Plitvice Lakes National Park.',
        'description': 'Hotel Plitvice is in Plitvice Lakes, the area around Plitvice Lakes National '
        'Park, a UNESCO World Heritage Site in the Lika region.\n'
        '\n'
        'It is a hotel run within Plitvice Lakes National Park.',
    },
    {
        'name': 'Hotel Bellevue Plitvice',
        'slug': 'hotel-bellevue-plitvice-plitvice-lakes',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'lika',
        'location': 'Plitvice Lakes',
        'short_description': 'A hotel run within Plitvice Lakes National Park.',
        'description': 'Hotel Bellevue Plitvice is in Plitvice Lakes, the area around Plitvice Lakes '
        'National Park, a UNESCO World Heritage Site in the Lika region.\n'
        '\n'
        'It is a hotel run within Plitvice Lakes National Park.',
    },
    {
        'name': 'Hotel Degenija',
        'slug': 'hotel-degenija-plitvice-lakes',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'lika',
        'location': 'Plitvice Lakes',
        'short_description': 'A hotel in the Plitvice Lakes area.',
        'description': 'Hotel Degenija is in Plitvice Lakes, the area around Plitvice Lakes National '
        'Park, a UNESCO World Heritage Site in the Lika region.\n'
        '\n'
        'It is a hotel in the Plitvice Lakes area.',
    },
    {
        'name': 'Hotel Korana Srakovčić',
        'slug': 'hotel-korana-srakovcic-karlovac',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'continental',
        'location': 'Karlovac',
        'short_description': 'A hotel on the bank of the Korana river in Karlovac.',
        'description': (
            'Hotel Korana Srakovčić is in Karlovac, a city founded in 1579 as a star-shaped '
            'fortress where four rivers meet: the Kupa, Korana, Mrežnica and Dobra.\n\n'
            'It is a hotel on the bank of the Korana river, near the town centre.'
        ),
    },
    {
        'name': 'Hotel Bastion',
        'slug': 'hotel-bastion-zadar',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'zadar',
        'location': 'Zadar',
        'short_description': 'A heritage hotel in the old town, set in a former bastion in Zadar.',
        'description': 'Hotel Bastion is in Zadar, a historic coastal city in northern Dalmatia, '
        'with a Roman forum and the Church of St Donatus.\n'
        '\n'
        'It is a heritage hotel in the old town, set in a former bastion.',
    },
    {
        'name': 'Hotel Kolovare',
        'slug': 'hotel-kolovare-zadar',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zadar',
        'location': 'Zadar',
        'short_description': 'A hotel on the Kolovare beach side of the Zadar peninsula.',
        'description': 'Hotel Kolovare is in Zadar, a historic coastal city in northern Dalmatia, '
        'with a Roman forum and the Church of St Donatus.\n'
        '\n'
        'It is a hotel on the Kolovare beach side of the Zadar peninsula.',
    },
    {
        'name': 'Hotel Niko',
        'slug': 'hotel-niko-zadar',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zadar',
        'location': 'Zadar',
        'short_description': 'A hotel in the Borik area of Zadar.',
        'description': 'Hotel Niko is in Zadar, a historic coastal city in northern Dalmatia, with a '
        'Roman forum and the Church of St Donatus.\n'
        '\n'
        'It is a hotel in the Borik area of Zadar.',
    },
    {
        'name': 'Falkensteiner Family Hotel Diadora',
        'slug': 'falkensteiner-family-hotel-diadora-zadar',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'zadar',
        'location': 'Zadar',
        'short_description': 'A family hotel in the Borik area of Zadar.',
        'description': 'Falkensteiner Family Hotel Diadora is in Zadar, a historic coastal city in '
        'northern Dalmatia, with a Roman forum and the Church of St Donatus.\n'
        '\n'
        'It is a family hotel in the Borik area of Zadar.',
    },
    {
        'name': 'Hotel Pinija',
        'slug': 'hotel-pinija-petrcane',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zadar',
        'location': 'Petrčane',
        'short_description': 'A hotel by the sea in the village in Petrčane.',
        'description': 'Hotel Pinija is in Petrčane, a village on the coast a short way north-west '
        'of Zadar.\n'
        '\n'
        'It is a hotel by the sea in the village.',
    },
    {
        'name': 'Hotel Ilirija',
        'slug': 'hotel-ilirija-biograd-na-moru',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'zadar',
        'location': 'Biograd na Moru',
        'short_description': 'A seafront holiday hotel complex in Biograd na Moru.',
        'description': 'Hotel Ilirija is in Biograd na Moru, a coastal town in northern Dalmatia, '
        'facing the island of Pašman.\n'
        '\n'
        'It is a seafront holiday hotel complex.',
    },
    {
        'name': 'Hotel Adriatic',
        'slug': 'hotel-adriatic-biograd-na-moru',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'zadar',
        'location': 'Biograd na Moru',
        'short_description': 'A hotel in Biograd na Moru.',
        'description': 'Hotel Adriatic is in Biograd na Moru, a coastal town in northern Dalmatia, '
        'facing the island of Pašman.\n'
        '\n'
        'It is a hotel in Biograd na Moru.',
    },
    {
        'name': 'Boškinac Boutique Hotel & Winery',
        'slug': 'boskinac-boutique-hotel-winery-novalja',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'zadar',
        'location': 'Novalja',
        'short_description': 'A boutique hotel with its own winery in the Novalja area.',
        'description': 'Boškinac Boutique Hotel & Winery is in Novalja, the main town on the island '
        'of Pag, near the Zrće beach.\n'
        '\n'
        'It is a boutique hotel with its own winery in the Novalja area.',
    },
    {
        'name': 'Hotel Alan',
        'slug': 'hotel-alan-starigrad-paklenica',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'zadar',
        'location': 'Starigrad Paklenica',
        'short_description': 'A hotel by the sea at the foot of Velebit in Starigrad Paklenica.',
        'description': 'Hotel Alan is in Starigrad Paklenica, a coastal village at the foot of the '
        'Velebit mountains, at the entrance to Paklenica National Park.\n'
        '\n'
        'It is a hotel by the sea at the foot of Velebit.',
    },
    {
        'name': 'Hotel Rajna',
        'slug': 'hotel-rajna-starigrad-paklenica',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'zadar',
        'location': 'Starigrad Paklenica',
        'short_description': 'A hotel at the foot of Velebit in Starigrad Paklenica.',
        'description': 'Hotel Rajna is in Starigrad Paklenica, a coastal village at the foot of the '
        'Velebit mountains, at the entrance to Paklenica National Park.\n'
        '\n'
        'It is a hotel at the foot of Velebit.',
    },
    {
        'name': 'Hotel Palace Šibenik',
        'slug': 'hotel-palace-sibenik',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Šibenik',
        'short_description': 'A hotel on the waterfront of the old town in Šibenik.',
        'description': 'Hotel Palace Šibenik is in Šibenik, a coastal city in central Dalmatia, home '
        'to the UNESCO-listed Cathedral of St James.\n'
        '\n'
        'It is a hotel on the waterfront of the old town.',
    },
    {
        'name': 'Hotel Panorama',
        'slug': 'hotel-panorama-sibenik',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'sibenik',
        'location': 'Šibenik',
        'short_description': 'A hotel above the Šibenik channel.',
        'description': 'Hotel Panorama is in Šibenik, a coastal city in central Dalmatia, home to '
        'the UNESCO-listed Cathedral of St James.\n'
        '\n'
        'It is a hotel above the Šibenik channel.',
    },
    {
        'name': 'Hotel Andrija',
        'slug': 'hotel-andrija-sibenik',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Šibenik',
        'short_description': 'A hotel in the Solaris holiday resort, west of the city in Šibenik.',
        'description': 'Hotel Andrija is in Šibenik, a coastal city in central Dalmatia, home to the '
        'UNESCO-listed Cathedral of St James.\n'
        '\n'
        'It is a hotel in the Solaris holiday resort, west of the city.',
    },
    {
        'name': 'Hotel Ivan',
        'slug': 'hotel-ivan-sibenik',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Šibenik',
        'short_description': 'A hotel in the Solaris holiday resort, west of the city in Šibenik.',
        'description': 'Hotel Ivan is in Šibenik, a coastal city in central Dalmatia, home to the '
        'UNESCO-listed Cathedral of St James.\n'
        '\n'
        'It is a hotel in the Solaris holiday resort, west of the city.',
    },
    {
        'name': 'Hotel Jure',
        'slug': 'hotel-jure-sibenik',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Šibenik',
        'short_description': 'A hotel in the Solaris holiday resort, west of the city in Šibenik.',
        'description': 'Hotel Jure is in Šibenik, a coastal city in central Dalmatia, home to the '
        'UNESCO-listed Cathedral of St James.\n'
        '\n'
        'It is a hotel in the Solaris holiday resort, west of the city.',
    },
    {
        'name': 'Hotel Niko Šibenik',
        'slug': 'hotel-niko-sibenik',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Šibenik',
        'short_description': 'A hotel in the Solaris holiday resort, west of the city in Šibenik.',
        'description': 'Hotel Niko Šibenik is in Šibenik, a coastal city in central Dalmatia, home '
        'to the UNESCO-listed Cathedral of St James.\n'
        '\n'
        'It is a hotel in the Solaris holiday resort, west of the city.',
    },
    {
        'name': 'Hotel Olympia',
        'slug': 'hotel-olympia-vodice',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Vodice',
        'short_description': 'A seaside hotel on the Vodice coast.',
        'description': 'Hotel Olympia is in Vodice, a coastal town north of Šibenik.\n'
        '\n'
        'It is a seaside hotel on the Vodice coast.',
    },
    {
        'name': 'Hotel Imperial',
        'slug': 'hotel-imperial-vodice',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Vodice',
        'short_description': 'A seaside hotel on the Vodice coast.',
        'description': 'Hotel Imperial is in Vodice, a coastal town north of Šibenik.\n'
        '\n'
        'It is a seaside hotel on the Vodice coast.',
    },
    {
        'name': 'Hotel Punta',
        'slug': 'hotel-punta-vodice',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'sibenik',
        'location': 'Vodice',
        'short_description': 'A seaside hotel on the Vodice coast.',
        'description': 'Hotel Punta is in Vodice, a coastal town north of Šibenik.\n'
        '\n'
        'It is a seaside hotel on the Vodice coast.',
    },
    {
        'name': 'Hotel Zora',
        'slug': 'hotel-zora-primosten',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'sibenik',
        'location': 'Primošten',
        'short_description': 'A seaside hotel on the Primošten coast.',
        'description': 'Hotel Zora is in Primošten, a town on a small peninsula on the central '
        'Dalmatian coast, south of Šibenik.\n'
        '\n'
        'It is a seaside hotel on the Primošten coast.',
    },
    {
        'name': 'Hotel Colentum',
        'slug': 'hotel-colentum-murter',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'sibenik',
        'location': 'Murter',
        'short_description': 'A hotel by the sea in the town in Murter.',
        'description': 'Hotel Colentum is in Murter, the main town on the island of Murter, a '
        'gateway to the Kornati islands.\n'
        '\n'
        'It is a hotel by the sea in the town.',
    },
    {
        'name': 'Hotel Skradinski Buk',
        'slug': 'hotel-skradinski-buk',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'sibenik',
        'location': 'Skradin',
        'short_description': 'A small hotel in the town, close to the Krka river in Skradin.',
        'description': 'Hotel Skradinski Buk is in Skradin, a small town on the Krka river, the '
        'usual starting point for visits to Krka National Park.\n'
        '\n'
        'It is a small hotel in the town, close to the Krka river.',
    },
    {
        'name': 'Hotel Vestibul Palace',
        'slug': 'hotel-vestibul-palace-split',
        'property_type': 'boutique',
        'star_rating': 5,
        'region': 'split',
        'location': 'Split',
        'short_description': "A heritage hotel inside Diocletian's Palace in Split.",
        'description': "Hotel Vestibul Palace is in Split, Croatia's second-largest city, built "
        'around the Roman palace of Emperor Diocletian.\n'
        '\n'
        "It is a heritage hotel inside Diocletian's Palace.",
    },
    {
        'name': 'Hotel Park',
        'slug': 'hotel-park-split',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Split',
        'short_description': 'A hotel above Bačvice beach, close to the old town in Split.',
        'description': "Hotel Park is in Split, Croatia's second-largest city, built around the "
        'Roman palace of Emperor Diocletian.\n'
        '\n'
        'It is a hotel above Bačvice beach, close to the old town.',
    },
    {
        'name': 'Hotel Marjan',
        'slug': 'hotel-marjan-split',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Split',
        'short_description': 'A hotel on the Split seafront, by the Marjan hill.',
        'description': "Hotel Marjan is in Split, Croatia's second-largest city, built around the "
        'Roman palace of Emperor Diocletian.\n'
        '\n'
        'It is a hotel on the Split seafront, by the Marjan hill.',
    },
    {
        'name': 'Hotel Cornaro',
        'slug': 'hotel-cornaro-split',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Split',
        'short_description': "A hotel a short walk from Diocletian's Palace in Split.",
        'description': "Hotel Cornaro is in Split, Croatia's second-largest city, built around the "
        'Roman palace of Emperor Diocletian.\n'
        '\n'
        "It is a hotel a short walk from Diocletian's Palace.",
    },
    {
        'name': 'Hotel Slavija',
        'slug': 'hotel-slavija-split',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Split',
        'short_description': 'A small hotel in the old part of Split.',
        'description': "Hotel Slavija is in Split, Croatia's second-largest city, built around the "
        'Roman palace of Emperor Diocletian.\n'
        '\n'
        'It is a small hotel in the old part of Split.',
    },
    {
        'name': 'Hotel Luxe',
        'slug': 'hotel-luxe-split',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'split',
        'location': 'Split',
        'short_description': 'A boutique-style hotel in the centre of Split.',
        'description': "Hotel Luxe is in Split, Croatia's second-largest city, built around the "
        'Roman palace of Emperor Diocletian.\n'
        '\n'
        'It is a boutique-style hotel in the centre of Split.',
    },
    {
        'name': 'Radisson Blu Resort & Spa, Split',
        'slug': 'radisson-blu-resort-spa-split',
        'property_type': 'resort',
        'star_rating': 5,
        'region': 'split',
        'location': 'Split',
        'short_description': 'A seafront resort hotel east of the city centre in Split.',
        'description': "Radisson Blu Resort & Spa, Split is in Split, Croatia's second-largest city, "
        'built around the Roman palace of Emperor Diocletian.\n'
        '\n'
        'It is a seafront resort hotel east of the city centre.',
    },
    {
        'name': 'Marmont Heritage Hotel',
        'slug': 'marmont-heritage-hotel-split',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'split',
        'location': 'Split',
        'short_description': 'A heritage hotel in the old centre of Split.',
        'description': "Marmont Heritage Hotel is in Split, Croatia's second-largest city, built "
        'around the Roman palace of Emperor Diocletian.\n'
        '\n'
        'It is a heritage hotel in the old centre of Split.',
    },
    {
        'name': 'Le Méridien Lav Split',
        'slug': 'le-meridien-lav-split-podstrana',
        'property_type': 'resort',
        'star_rating': 5,
        'region': 'split',
        'location': 'Podstrana',
        'short_description': 'A seafront resort hotel on the Lav peninsula in Podstrana.',
        'description': 'Le Méridien Lav Split is in Podstrana, a coastal village a few kilometres '
        'south-east of Split.\n'
        '\n'
        'It is a seafront resort hotel on the Lav peninsula.',
    },
    {
        'name': 'Trogir Palace Hotel',
        'slug': 'trogir-palace-hotel',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'split',
        'location': 'Trogir',
        'short_description': 'A hotel on the Trogir waterfront, by the old town.',
        'description': 'Trogir Palace Hotel is in Trogir, a historic town west of Split whose old '
        'centre on a small island is a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on the Trogir waterfront, by the old town.',
    },
    {
        'name': 'Hotel Pašike',
        'slug': 'hotel-pasike-trogir',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'split',
        'location': 'Trogir',
        'short_description': 'A small hotel in the old centre of Trogir.',
        'description': 'Hotel Pašike is in Trogir, a historic town west of Split whose old centre on '
        'a small island is a UNESCO World Heritage Site.\n'
        '\n'
        'It is a small hotel in the old centre of Trogir.',
    },
    {
        'name': 'Palace Elisabeth Hvar Heritage Hotel',
        'slug': 'palace-elisabeth-hvar-heritage-hotel',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'split',
        'location': 'Hvar',
        'short_description': 'A heritage hotel on the main square, by the harbour in Hvar.',
        'description': 'Palace Elisabeth Hvar Heritage Hotel is in Hvar, the main town on the island '
        'of Hvar, with a fortress above its harbour.\n'
        '\n'
        'It is a heritage hotel on the main square, by the harbour.',
    },
    {
        'name': 'Adriana Hvar Spa Hotel',
        'slug': 'adriana-hvar-spa-hotel',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'split',
        'location': 'Hvar',
        'short_description': 'A spa hotel on the harbour front in Hvar.',
        'description': 'Adriana Hvar Spa Hotel is in Hvar, the main town on the island of Hvar, with '
        'a fortress above its harbour.\n'
        '\n'
        'It is a spa hotel on the harbour front.',
    },
    {
        'name': 'Amfora Hvar Grand Beach Resort',
        'slug': 'amfora-hvar-grand-beach-resort',
        'property_type': 'resort',
        'star_rating': 0,
        'region': 'split',
        'location': 'Hvar',
        'short_description': 'A beachside resort hotel on the coast near the town in Hvar.',
        'description': 'Amfora Hvar Grand Beach Resort is in Hvar, the main town on the island of '
        'Hvar, with a fortress above its harbour.\n'
        '\n'
        'It is a beachside resort hotel on the coast near the town.',
    },
    {
        'name': 'Hotel Riva',
        'slug': 'hotel-riva-hvar',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'split',
        'location': 'Hvar',
        'short_description': 'A boutique hotel on the harbour in Hvar.',
        'description': 'Hotel Riva is in Hvar, the main town on the island of Hvar, with a fortress '
        'above its harbour.\n'
        '\n'
        'It is a boutique hotel on the harbour.',
    },
    {
        'name': 'Hotel Podstine',
        'slug': 'hotel-podstine-hvar',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Hvar',
        'short_description': 'A seaside hotel just outside the town in Hvar.',
        'description': 'Hotel Podstine is in Hvar, the main town on the island of Hvar, with a '
        'fortress above its harbour.\n'
        '\n'
        'It is a seaside hotel just outside the town.',
    },
    {
        'name': 'Bluesun Resort Elaphusa',
        'slug': 'bluesun-resort-elaphusa-bol',
        'property_type': 'resort',
        'star_rating': 0,
        'region': 'split',
        'location': 'Bol',
        'short_description': 'A holiday hotel complex on the Bol coast.',
        'description': 'Bluesun Resort Elaphusa is in Bol, a town on the south coast of the island '
        'of Brač, near the Zlatni Rat beach.\n'
        '\n'
        'It is a holiday hotel complex on the Bol coast.',
    },
    {
        'name': 'Bretanide Sport & Wellness Resort',
        'slug': 'bretanide-sport-wellness-resort-bol',
        'property_type': 'resort',
        'star_rating': 0,
        'region': 'split',
        'location': 'Bol',
        'short_description': 'A sport and wellness resort in the town in Bol.',
        'description': 'Bretanide Sport & Wellness Resort is in Bol, a town on the south coast of '
        'the island of Brač, near the Zlatni Rat beach.\n'
        '\n'
        'It is a sport and wellness resort in the town.',
    },
    {
        'name': 'Hotel Kaštil',
        'slug': 'hotel-kastil-bol',
        'property_type': 'boutique',
        'star_rating': 4,
        'region': 'split',
        'location': 'Bol',
        'short_description': 'A small hotel in a historic building by the sea in Bol.',
        'description': 'Hotel Kaštil is in Bol, a town on the south coast of the island of Brač, '
        'near the Zlatni Rat beach.\n'
        '\n'
        'It is a small hotel in a historic building by the sea.',
    },
    {
        'name': 'Hotel Waterman Svpetrus',
        'slug': 'hotel-waterman-svpetrus-supetar',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Supetar',
        'short_description': 'A seaside hotel by the sea in the town in Supetar.',
        'description': 'Hotel Waterman Svpetrus is in Supetar, the main port of the island of Brač.\n'
        '\n'
        'It is a seaside hotel by the sea in the town.',
    },
    {
        'name': 'Hotel Meteor',
        'slug': 'hotel-meteor-makarska',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Makarska',
        'short_description': 'A seafront hotel in Makarska.',
        'description': 'Hotel Meteor is in Makarska, a coastal town on the Makarska Riviera, below '
        'the Biokovo mountains.\n'
        '\n'
        'It is a seafront hotel in Makarska.',
    },
    {
        'name': 'Hotel Biokovo',
        'slug': 'hotel-biokovo-makarska',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Makarska',
        'short_description': 'A hotel on the Makarska seafront.',
        'description': 'Hotel Biokovo is in Makarska, a coastal town on the Makarska Riviera, below '
        'the Biokovo mountains.\n'
        '\n'
        'It is a hotel on the Makarska seafront.',
    },
    {
        'name': 'Hotel Osejava',
        'slug': 'hotel-osejava-makarska',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'split',
        'location': 'Makarska',
        'short_description': 'A hotel by the sea near the centre of Makarska.',
        'description': 'Hotel Osejava is in Makarska, a coastal town on the Makarska Riviera, below '
        'the Biokovo mountains.\n'
        '\n'
        'It is a hotel by the sea near the centre of Makarska.',
    },
    {
        'name': 'Hotel Dalmacija',
        'slug': 'hotel-dalmacija-makarska',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Makarska',
        'short_description': 'A hotel on the Makarska seafront.',
        'description': 'Hotel Dalmacija is in Makarska, a coastal town on the Makarska Riviera, '
        'below the Biokovo mountains.\n'
        '\n'
        'It is a hotel on the Makarska seafront.',
    },
    {
        'name': 'Bluesun Hotel Alga',
        'slug': 'bluesun-hotel-alga-tucepi',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'split',
        'location': 'Tučepi',
        'short_description': 'A seaside hotel on the Tučepi coast.',
        'description': 'Bluesun Hotel Alga is in Tučepi, a village on the Makarska Riviera, below '
        'the Biokovo mountains.\n'
        '\n'
        'It is a seaside hotel on the Tučepi coast.',
    },
    {
        'name': 'Bluesun Hotel Marina',
        'slug': 'bluesun-hotel-marina-tucepi',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Tučepi',
        'short_description': 'A seaside hotel on the Tučepi coast.',
        'description': 'Bluesun Hotel Marina is in Tučepi, a village on the Makarska Riviera, below '
        'the Biokovo mountains.\n'
        '\n'
        'It is a seaside hotel on the Tučepi coast.',
    },
    {
        'name': 'Bluesun Hotel Soline',
        'slug': 'bluesun-hotel-soline-brela',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Brela',
        'short_description': 'A seaside hotel on the Brela coast.',
        'description': 'Bluesun Hotel Soline is in Brela, a village on the Makarska Riviera, known '
        'for its pebble beaches.\n'
        '\n'
        'It is a seaside hotel on the Brela coast.',
    },
    {
        'name': 'Hotel Horizont',
        'slug': 'hotel-horizont-baska-voda',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Baška Voda',
        'short_description': 'A seaside hotel on the Baška Voda coast.',
        'description': 'Hotel Horizont is in Baška Voda, a village on the Makarska Riviera.\n'
        '\n'
        'It is a seaside hotel on the Baška Voda coast.',
    },
    {
        'name': 'Hotel Issa',
        'slug': 'hotel-issa-vis',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Vis',
        'short_description': 'A hotel on the Vis seafront.',
        'description': 'Hotel Issa is in Vis, the main town on the island of Vis, in the outer '
        'Adriatic.\n'
        '\n'
        'It is a hotel on the Vis seafront.',
    },
    {
        'name': 'Hotel Tamaris',
        'slug': 'hotel-tamaris-vis',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'split',
        'location': 'Vis',
        'short_description': 'A hotel on the Vis seafront.',
        'description': 'Hotel Tamaris is in Vis, the main town on the island of Vis, in the outer '
        'Adriatic.\n'
        '\n'
        'It is a hotel on the Vis seafront.',
    },
    {
        'name': 'Hotel Excelsior Dubrovnik',
        'slug': 'hotel-excelsior-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel on the Ploče seafront, east of the Old Town in Dubrovnik.',
        'description': 'Hotel Excelsior Dubrovnik is in Dubrovnik, a walled city on the southern '
        'Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on the Ploče seafront, east of the Old Town.',
    },
    {
        'name': 'Villa Dubrovnik',
        'slug': 'villa-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel on a cliff by the sea, east of the Old Town in Dubrovnik.',
        'description': 'Villa Dubrovnik is in Dubrovnik, a walled city on the southern Adriatic '
        'coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on a cliff by the sea, east of the Old Town.',
    },
    {
        'name': 'Hotel Bellevue Dubrovnik',
        'slug': 'hotel-bellevue-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel on a cliff above the Miramare bay in Dubrovnik.',
        'description': 'Hotel Bellevue Dubrovnik is in Dubrovnik, a walled city on the southern '
        'Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on a cliff above the Miramare bay.',
    },
    {
        'name': 'Hotel Pucić Palace',
        'slug': 'hotel-pucic-palace-dubrovnik',
        'property_type': 'boutique',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel in a historic palace in the Old Town in Dubrovnik.',
        'description': 'Hotel Pucić Palace is in Dubrovnik, a walled city on the southern Adriatic '
        'coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel in a historic palace in the Old Town.',
    },
    {
        'name': 'Hilton Imperial Dubrovnik',
        'slug': 'hilton-imperial-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel in a historic building just outside the Pile Gate in '
        'Dubrovnik.',
        'description': 'Hilton Imperial Dubrovnik is in Dubrovnik, a walled city on the southern '
        'Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel in a historic building just outside the Pile Gate.',
    },
    {
        'name': 'Hotel Dubrovnik Palace',
        'slug': 'hotel-dubrovnik-palace',
        'property_type': 'resort',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A seaside hotel on the Lapad peninsula in Dubrovnik.',
        'description': 'Hotel Dubrovnik Palace is in Dubrovnik, a walled city on the southern '
        'Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a seaside hotel on the Lapad peninsula.',
    },
    {
        'name': 'Grand Villa Argentina',
        'slug': 'grand-villa-argentina-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel complex on the Ploče seafront, east of the Old Town in '
        'Dubrovnik.',
        'description': 'Grand Villa Argentina is in Dubrovnik, a walled city on the southern '
        'Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel complex on the Ploče seafront, east of the Old Town.',
    },
    {
        'name': 'Hotel Uvala',
        'slug': 'hotel-uvala-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel by the sea in the Lapad bay in Dubrovnik.',
        'description': 'Hotel Uvala is in Dubrovnik, a walled city on the southern Adriatic coast '
        'and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel by the sea in the Lapad bay.',
    },
    {
        'name': 'Hotel Lapad',
        'slug': 'hotel-lapad-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel in the Lapad bay in Dubrovnik.',
        'description': 'Hotel Lapad is in Dubrovnik, a walled city on the southern Adriatic coast '
        'and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel in the Lapad bay.',
    },
    {
        'name': 'Hotel President Valamar Collection',
        'slug': 'hotel-president-valamar-collection-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel by the sea on the Babin Kuk peninsula in Dubrovnik.',
        'description': 'Hotel President Valamar Collection is in Dubrovnik, a walled city on the '
        'southern Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel by the sea on the Babin Kuk peninsula.',
    },
    {
        'name': 'Valamar Lacroma Dubrovnik',
        'slug': 'valamar-lacroma-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel on the Babin Kuk peninsula in Dubrovnik.',
        'description': 'Valamar Lacroma Dubrovnik is in Dubrovnik, a walled city on the southern '
        'Adriatic coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on the Babin Kuk peninsula.',
    },
    {
        'name': 'Valamar Argosy Hotel',
        'slug': 'valamar-argosy-hotel-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel on the Babin Kuk peninsula in Dubrovnik.',
        'description': 'Valamar Argosy Hotel is in Dubrovnik, a walled city on the southern Adriatic '
        'coast and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel on the Babin Kuk peninsula.',
    },
    {
        'name': 'Hotel Lero',
        'slug': 'hotel-lero-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel in the Lapad area in Dubrovnik.',
        'description': 'Hotel Lero is in Dubrovnik, a walled city on the southern Adriatic coast and '
        'a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel in the Lapad area.',
    },
    {
        'name': 'Hotel Petka',
        'slug': 'hotel-petka-dubrovnik',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'dubrovnik',
        'location': 'Dubrovnik',
        'short_description': 'A hotel close to the harbour in the Gruž area in Dubrovnik.',
        'description': 'Hotel Petka is in Dubrovnik, a walled city on the southern Adriatic coast '
        'and a UNESCO World Heritage Site.\n'
        '\n'
        'It is a hotel close to the harbour in the Gruž area.',
    },
    {
        'name': 'Sheraton Dubrovnik Riviera Hotel',
        'slug': 'sheraton-dubrovnik-riviera-hotel-mlini',
        'property_type': 'resort',
        'star_rating': 5,
        'region': 'dubrovnik',
        'location': 'Mlini',
        'short_description': 'A seaside hotel on the coast south-east of Dubrovnik in Mlini.',
        'description': 'Sheraton Dubrovnik Riviera Hotel is in Mlini, a village on the coast '
        'south-east of Dubrovnik.\n'
        '\n'
        'It is a seaside hotel on the coast south-east of Dubrovnik.',
    },
    {
        'name': 'Hotel Astarea',
        'slug': 'hotel-astarea-mlini',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Mlini',
        'short_description': 'A seaside hotel in the village in Mlini.',
        'description': 'Hotel Astarea is in Mlini, a village on the coast south-east of Dubrovnik.\n'
        '\n'
        'It is a seaside hotel in the village.',
    },
    {
        'name': 'Hotel Croatia',
        'slug': 'hotel-croatia-cavtat',
        'property_type': 'resort',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Cavtat',
        'short_description': 'A large seaside hotel in a park above the Cavtat bay.',
        'description': 'Hotel Croatia is in Cavtat, a small coastal town south-east of Dubrovnik, '
        'near the airport.\n'
        '\n'
        'It is a large seaside hotel in a park above the Cavtat bay.',
    },
    {
        'name': 'Hotel Supetar',
        'slug': 'hotel-supetar-cavtat',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Cavtat',
        'short_description': 'A seaside hotel in Cavtat.',
        'description': 'Hotel Supetar is in Cavtat, a small coastal town south-east of Dubrovnik, '
        'near the airport.\n'
        '\n'
        'It is a seaside hotel in Cavtat.',
    },
    {
        'name': 'Lešić Dimitri Palace',
        'slug': 'lesic-dimitri-palace-korcula',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Korčula',
        'short_description': 'A heritage hotel in the walled old town of Korčula.',
        'description': 'Lešić Dimitri Palace is in Korčula, the main town on the island of Korčula, '
        'a walled medieval town on a small peninsula.\n'
        '\n'
        'It is a heritage hotel in the walled old town of Korčula.',
    },
    {
        'name': 'Hotel Marko Polo',
        'slug': 'hotel-marko-polo-korcula',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Korčula',
        'short_description': 'A hotel on the coast near the old town in Korčula.',
        'description': 'Hotel Marko Polo is in Korčula, the main town on the island of Korčula, a '
        'walled medieval town on a small peninsula.\n'
        '\n'
        'It is a hotel on the coast near the old town.',
    },
    {
        'name': 'Hotel Korčula de la Ville',
        'slug': 'hotel-korcula-de-la-ville',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Korčula',
        'short_description': 'A small hotel in Korčula old town.',
        'description': 'Hotel Korčula de la Ville is in Korčula, the main town on the island of '
        'Korčula, a walled medieval town on a small peninsula.\n'
        '\n'
        'It is a small hotel in Korčula old town.',
    },
    {
        'name': 'Lafodia Sea Resort',
        'slug': 'lafodia-sea-resort-lopud',
        'property_type': 'resort',
        'star_rating': 4,
        'region': 'dubrovnik',
        'location': 'Lopud',
        'short_description': 'A seaside resort on the island in Lopud.',
        'description': 'Lafodia Sea Resort is in Lopud, a small island in the Elaphiti archipelago '
        'near Dubrovnik.\n'
        '\n'
        'It is a seaside resort on the island.',
    },
    {
        'name': 'Hotel Odisej',
        'slug': 'hotel-odisej-pomena',
        'property_type': 'hotel',
        'star_rating': 0,
        'region': 'dubrovnik',
        'location': 'Pomena',
        'short_description': 'A hotel on the sea at the entrance to Mljet National Park in Pomena.',
        'description': 'Hotel Odisej is in Pomena, a village at the western end of the island of '
        'Mljet, next to Mljet National Park.\n'
        '\n'
        'It is a hotel on the sea at the entrance to Mljet National Park.',
    },
    {
        'name': 'Hotel Esplanade Zagreb',
        'slug': 'hotel-esplanade-zagreb',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A historic hotel opened in 1925, near the main railway station in '
        'Zagreb.',
        'description': 'Hotel Esplanade Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a historic hotel opened in 1925, near the main railway station.',
    },
    {
        'name': 'Hotel Palace Zagreb',
        'slug': 'hotel-palace-zagreb',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A hotel in a late 19th-century building on Strossmayer Square in '
        'Zagreb.',
        'description': 'Hotel Palace Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a hotel in a late 19th-century building on Strossmayer Square.',
    },
    {
        'name': 'The Westin Zagreb',
        'slug': 'the-westin-zagreb',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A large city hotel in the centre of Zagreb.',
        'description': 'The Westin Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a large city hotel in the centre of Zagreb.',
    },
    {
        'name': 'Sheraton Zagreb Hotel',
        'slug': 'sheraton-zagreb-hotel',
        'property_type': 'hotel',
        'star_rating': 5,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A city hotel in the centre of Zagreb.',
        'description': 'Sheraton Zagreb Hotel is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a city hotel in the centre of Zagreb.',
    },
    {
        'name': 'Hotel Dubrovnik Zagreb',
        'slug': 'hotel-dubrovnik-zagreb',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A hotel on Ban Jelačić Square in Zagreb.',
        'description': 'Hotel Dubrovnik Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a hotel on Ban Jelačić Square.',
    },
    {
        'name': 'Hotel International Zagreb',
        'slug': 'hotel-international-zagreb',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A city hotel in the centre of Zagreb.',
        'description': 'Hotel International Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a city hotel in the centre of Zagreb.',
    },
    {
        'name': 'Hotel Antunović',
        'slug': 'hotel-antunovic-zagreb',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A hotel on the western side of Zagreb.',
        'description': 'Hotel Antunović is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a hotel on the western side of Zagreb.',
    },
    {
        'name': 'Hotel Academia',
        'slug': 'hotel-academia-zagreb',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A city hotel in the centre of Zagreb.',
        'description': 'Hotel Academia is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a city hotel in the centre of Zagreb.',
    },
    {
        'name': 'Arena Hotel Zagreb',
        'slug': 'arena-hotel-zagreb',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A hotel in the south-west of Zagreb.',
        'description': 'Arena Hotel Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a hotel in the south-west of Zagreb.',
    },
    {
        'name': 'Hotel Central Zagreb',
        'slug': 'hotel-central-zagreb',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A small hotel opposite the main railway station in Zagreb.',
        'description': 'Hotel Central Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a small hotel opposite the main railway station.',
    },
    {
        'name': 'Hotel Jägerhorn',
        'slug': 'hotel-jagerhorn-zagreb',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A small hotel in the Ilica street area, near the upper town in Zagreb.',
        'description': 'Hotel Jägerhorn is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a small hotel in the Ilica street area, near the upper town.',
    },
    {
        'name': 'Chillout Hostel Zagreb',
        'slug': 'chillout-hostel-zagreb',
        'property_type': 'hostel',
        'star_rating': 0,
        'region': 'zagreb',
        'location': 'Zagreb',
        'short_description': 'A hostel in the centre of Zagreb.',
        'description': 'Chillout Hostel Zagreb is in Zagreb, the capital of Croatia.\n'
        '\n'
        'It is a hostel in the centre of Zagreb.',
    },
    {
        'name': 'Hotel Osijek',
        'slug': 'hotel-osijek',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Osijek',
        'short_description': 'A hotel on the bank of the Drava river in Osijek.',
        'description': 'Hotel Osijek is in Osijek, the largest city of Slavonia, on the Drava '
        'river.\n'
        '\n'
        'It is a hotel on the bank of the Drava river.',
    },
    {
        'name': 'Waldinger Hotel',
        'slug': 'waldinger-hotel-osijek',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Osijek',
        'short_description': 'A hotel in the Tvrđa and Donji Grad area of Osijek.',
        'description': 'Waldinger Hotel is in Osijek, the largest city of Slavonia, on the Drava '
        'river.\n'
        '\n'
        'It is a hotel in the Tvrđa and Donji Grad area of Osijek.',
    },
    {
        'name': 'Hotel Turist',
        'slug': 'hotel-turist-varazdin',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'continental',
        'location': 'Varaždin',
        'short_description': 'A hotel in the centre of Varaždin.',
        'description': 'Hotel Turist is in Varaždin, a baroque town in the north of Croatia, near '
        'the Drava river.\n'
        '\n'
        'It is a hotel in the centre of Varaždin.',
    },
    {
        'name': 'Hotel Carlstadt',
        'slug': 'hotel-carlstadt-karlovac',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Karlovac',
        'short_description': 'A hotel in the centre of Karlovac.',
        'description': 'Hotel Carlstadt is in Karlovac, a city south-west of Zagreb, built where '
        'four rivers meet.\n'
        '\n'
        'It is a hotel in the centre of Karlovac.',
    },
    {
        'name': 'Hotel Frankopan',
        'slug': 'hotel-frankopan-ogulin',
        'property_type': 'hotel',
        'star_rating': 3,
        'region': 'continental',
        'location': 'Ogulin',
        'short_description': 'A hotel in the centre of Ogulin.',
        'description': 'Hotel Frankopan is in Ogulin, a town between Zagreb and the coast, below the '
        'Klek mountain.\n'
        '\n'
        'It is a hotel in the centre of Ogulin.',
    },
    {
        'name': 'Hotel Livadić',
        'slug': 'hotel-livadic-samobor',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'zagreb',
        'location': 'Samobor',
        'short_description': 'A historic hotel in the centre of Samobor.',
        'description': 'Hotel Livadić is in Samobor, a town west of Zagreb, at the foot of the '
        'Samobor hills.\n'
        '\n'
        'It is a historic hotel in the centre of Samobor.',
    },
    {
        'name': 'Well Hotel Terme Tuhelj',
        'slug': 'well-hotel-terme-tuhelj',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Tuhelj',
        'short_description': 'A thermal spa hotel in Tuhelj.',
        'description': 'Well Hotel Terme Tuhelj is in Tuhelj, a village in the Zagorje region north '
        'of Zagreb.\n'
        '\n'
        'It is a thermal spa hotel.',
    },
    {
        'name': 'Hotel Terme Jezerčica',
        'slug': 'hotel-terme-jezercica-donja-stubica',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Donja Stubica',
        'short_description': 'A thermal spa hotel in Donja Stubica.',
        'description': 'Hotel Terme Jezerčica is in Donja Stubica, a town in the Zagorje region '
        'north of Zagreb.\n'
        '\n'
        'It is a thermal spa hotel.',
    },
    {
        'name': 'Spa Golfer Hotel',
        'slug': 'spa-golfer-hotel-sveti-martin-na-muri',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Sveti Martin na Muri',
        'short_description': 'A thermal spa hotel in Sveti Martin na Muri.',
        'description': 'Spa Golfer Hotel is in Sveti Martin na Muri, a village in Međimurje county, '
        'in northern Croatia.\n'
        '\n'
        'It is a thermal spa hotel.',
    },
    {
        'name': 'Hotel Bizovačke Toplice',
        'slug': 'hotel-bizovacke-toplice',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Bizovac',
        'short_description': 'A thermal spa hotel in Bizovac.',
        'description': 'Hotel Bizovačke Toplice is in Bizovac, a spa village near Osijek in '
        'Slavonia.\n'
        '\n'
        'It is a thermal spa hotel.',
    },
    {
        'name': 'Hotel Lav Vukovar',
        'slug': 'hotel-lav-vukovar',
        'property_type': 'hotel',
        'star_rating': 4,
        'region': 'continental',
        'location': 'Vukovar',
        'short_description': 'A hotel on the bank of the Danube in Vukovar.',
        'description': 'Hotel Lav Vukovar is in Vukovar, a town on the Danube in eastern Croatia.\n'
        '\n'
        'It is a hotel on the bank of the Danube.',
    },
    {
        'name': 'Hotel Principovac',
        'slug': 'hotel-principovac-ilok',
        'property_type': 'boutique',
        'star_rating': 0,
        'region': 'continental',
        'location': 'Ilok',
        'short_description': 'A small hotel set among the vineyards of Ilok.',
        'description': 'Hotel Principovac is in Ilok, a town on the Danube in the far east of '
        'Croatia, known for its wine.\n'
        '\n'
        'It is a small hotel set among the vineyards of Ilok.',
    },
    {
        'name': 'Villa Magdalena',
        'slug': 'villa-magdalena-krapinske-toplice',
        'property_type': 'boutique',
        'star_rating': 5,
        'region': 'continental',
        'location': 'Krapinske Toplice',
        'short_description': 'A spa hotel in Krapinske Toplice.',
        'description': 'Villa Magdalena is in Krapinske Toplice, a spa town in the Zagorje region '
        'north of Zagreb.\n'
        '\n'
        'It is a spa hotel.',
    },
]
