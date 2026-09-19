"""Seed Montenegro destinations (Places) — idempotent.

Editorial town/area guides; each place's detail page lists the experiences that
run there. Reuses the bundled seed_assets images for covers.

    python manage.py seed_places
"""

from __future__ import annotations

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify

SEED_DIR = Path(__file__).resolve().parents[2] / 'seed_assets'

# Each place is a dict of:
#   name, region, place_type, image, featured, summary, description, highlights
#     — the original editorial fields (unchanged).
#   overview      — extended editorial body (700–900 chars), shown below description.
#   faqs          — [{'q': ..., 'a': ...}] answer-first FAQs (FAQPage JSON-LD).
#   quick_facts   — [{'label': ..., 'value': ...}] quick-facts strip.
#   good_for      — short lowercase audience tags.
#   latitude / longitude — real coordinates (floats).
PLACES = [
    {
        'name': 'Podgorica',
        'region': 'podgorica',
        'place_type': 'cities',
        'image': 'culture.jpg',
        'featured': False,
        'summary': 'Montenegro’s riverside capital — modern, green and an easy base for the south.',
        'description': 'Rebuilt after heavy WWII bombing, Montenegro’s capital blends leafy boulevards and riverside cafés with pockets of Ottoman old town, a striking modern cathedral and the landmark Millennium Bridge over the Morača.',
        'highlights': [
            'Cathedral of the Resurrection of Christ',
            'Stara Varoš & the Clock Tower',
            'Millennium Bridge',
            'Gorica hill park',
            'Doclea (Duklja) Roman ruins',
        ],
        'overview': 'Podgorica sits where the Morača and Ribnica rivers meet, at the fertile centre of Montenegro’s Zeta plain. Allied bombing in 1944 levelled most of the historic city, so today’s capital is largely a post-war and modern creation of wide boulevards, parks and river promenades — more a place to live than a set-piece for tourists, which is exactly its appeal. The huge Cathedral of the Resurrection of Christ, completed in 2013, is the standout monument, its interior covered in bold contemporary frescoes. Across town, the Ottoman-era Stara Varoš keeps its narrow lanes, the Osmanagić Mosque and the 18th-century Sahat Kula clock tower. The Calatrava-style Millennium Bridge is the modern symbol, floodlit over the Morača at night. Just outside the city lie the atmospheric ruins of Roman Doclea. Podgorica is also the country’s transport hub — the main airport, bus and rail lines — putting Lake Skadar, Ostrog and the coast all within an easy day trip.',
        'faqs': [
            {
                'q': 'Is Podgorica worth visiting?',
                'a': 'As a relaxed, authentic capital rather than a tourist showpiece — yes. It’s worth a day for its modern cathedral, Ottoman old-town quarter and riverside cafés, and it’s an ideal base for day trips to Lake Skadar, Ostrog and the coast.',
            },
            {
                'q': 'How do I get to Podgorica?',
                'a': 'Podgorica Airport (TGD) is about 12 km south of the centre; the city is also Montenegro’s main rail and bus hub, with direct trains to Bar on the coast and north toward Kolašin.',
            },
            {
                'q': 'What is there to do in Podgorica?',
                'a': 'See the modern Cathedral of the Resurrection, wander the Ottoman Stara Varoš and its clock tower, cross the Millennium Bridge, walk up Gorica hill park, and visit the Roman ruins of Doclea just outside town.',
            },
            {
                'q': 'How long should I spend in Podgorica?',
                'a': 'Half a day to a day covers the city itself; many travellers use it as a one- or two-night base for exploring Lake Skadar and central Montenegro.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'April–June and September–October (hot, dry summers)'},
            {'label': 'Ideal for', 'value': 'City breaks, transport hub, day-trip base'},
            {'label': 'Time needed', 'value': 'Half a day to a day'},
            {
                'label': 'Getting there',
                'value': 'Podgorica Airport (TGD) ~12 km; national rail & bus hub',
            },
            {'label': 'Region', 'value': 'Podgorica'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~12 km'},
        ],
        'good_for': [
            'city breaks',
            'transport connections',
            'day-trip base',
            'budget travellers',
            'authentic local life',
        ],
        'latitude': 42.4304,
        'longitude': 19.2594,
        'sections': [
            {
                'heading': 'A capital rebuilt',
                'body': 'Podgorica has been settled since antiquity — the Romans knew nearby Doclea (Duklja), and the medieval town of Ribnica grew at the river confluence — but its modern face dates from reconstruction after the Second World War, when it was renamed Titograd until 1992. That history explains the open, orderly layout of boulevards and blocks rather than a dense old core. The result is a green, low-key capital where daily Montenegrin life plays out in riverside parks and café terraces rather than around monuments.',
            },
            {
                'heading': 'What to see',
                'body': 'The gleaming Cathedral of the Resurrection of Christ, with its twin bell towers and vivid modern frescoes, is the city’s signature sight. The Ottoman quarter of Stara Varoš, across the Ribnica, preserves the Sahat Kula clock tower and old mosques. The Petrović Palace in Kruševac park houses a contemporary art centre, and the city and natural-history museums fill in the region’s story. For a view, climb the wooded Gorica hill that rises right beside the centre.',
            },
            {
                'heading': 'A base for central Montenegro',
                'body': 'Podgorica’s real value to visitors is its position. Lake Skadar’s gateway village of Virpazar is about 40 minutes south; the cliff monastery of Ostrog is under an hour northwest; the royal old capital of Cetinje and the Lovćen road are half an hour away; and the coast at Bar is reachable by the scenic Bar–Belgrade railway. With the country’s main airport on its doorstep, many trips to Montenegro begin and end here.',
            },
        ],
        'external_links': [
            {'label': 'Podgorica — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Podgorica'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel/',
            },
        ],
    },
    {
        'name': 'Pljevlja',
        'region': 'durmitor',
        'place_type': 'cities',
        'image': 'hiking.jpg',
        'featured': False,
        'summary': 'A historic northern town of monasteries, mosques and mountain cooking.',
        'description': 'One of Montenegro’s oldest towns, high in the far north near the Tara and Durmitor, Pljevlja pairs a frescoed medieval monastery and a landmark Ottoman mosque with hearty mountain food and easy access to the northern wilds.',
        'highlights': [
            'Holy Trinity Monastery',
            'Husein-paša Mosque',
            'Roman Municipium S. ruins',
            'Pljevaljski sir (local cheese)',
            'Gateway to the Tara & Durmitor',
        ],
        'overview': 'Pljevlja spreads across a high plateau in Montenegro’s far north, close to the borders with Serbia and Bosnia and long a crossroads of the region’s trade and faiths. It is one of the country’s oldest continuously settled places — the Romans built the town of Municipium S. here — and its two great monuments reflect that layered history. The Serbian Orthodox Monastery of the Holy Trinity, founded in the 16th century, holds some of the richest frescoes and one of the most important manuscript and treasury collections in Montenegro. A short walk away, the Husein-paša Mosque of 1569 is considered one of the finest Ottoman mosques in the Balkans, its 42-metre minaret among the tallest in the region. Modern Pljevlja is a working town shaped by coal mining and a thermal power station, so it sees few tourists — part of its unvarnished appeal. It is best combined with the northern highlights close by: the Tara Canyon, the Durmitor massif and the monastery-dotted mountains around them.',
        'faqs': [
            {
                'q': 'Why visit Pljevlja?',
                'a': 'For two outstanding monuments — the frescoed 16th-century Holy Trinity Monastery and the landmark Husein-paša Mosque — plus authentic northern mountain cooking and easy access to the Tara Canyon and Durmitor.',
            },
            {
                'q': 'How do I get to Pljevlja?',
                'a': 'Pljevlja lies in the far north, roughly a 2.5–3 hour drive from Podgorica via Mojkovac, and is also linked by bus; there is no rail or airport, so most visitors arrive by car.',
            },
            {
                'q': 'What is Pljevlja known for?',
                'a': 'Its Holy Trinity Monastery and Husein-paša Mosque, its Roman past as Municipium S., and Pljevaljski sir — a prized local cheese — alongside the coal mining that drives the modern town.',
            },
            {
                'q': 'Is Pljevlja worth a detour?',
                'a': 'If you’re exploring the north — the Tara, Durmitor or the Serbian border crossings — yes; its monastery and mosque are among the finest in inland Montenegro and it sees far fewer visitors than the coast.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–September (cold, snowy winters at altitude)'},
            {'label': 'Ideal for', 'value': 'History, religious heritage, off-the-trail travel'},
            {'label': 'Time needed', 'value': 'Half a day, or a stop on a northern tour'},
            {'label': 'Getting there', 'value': '~2.5–3 hr drive from Podgorica; buses, no rail'},
            {'label': 'Region', 'value': 'Durmitor & the North'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~130 km'},
        ],
        'good_for': [
            'history lovers',
            'religious heritage',
            'off-the-beaten-track travellers',
            'northern road trips',
            'food travellers',
        ],
        'latitude': 43.3567,
        'longitude': 19.3583,
        'sections': [
            {
                'heading': 'Two faiths, two masterpieces',
                'body': 'Pljevlja’s standing as a historic trading town is written into its two great monuments. The Monastery of the Holy Trinity, just outside the centre, was founded in the 16th century and is celebrated for its wall paintings, carved iconostasis and a treasury of manuscripts, printed books and liturgical silver — one of the most valuable collections in the country. In the town itself, the Husein-paša Mosque of 1569 is regarded as one of the most beautiful Ottoman mosques in the Balkans; its slender 42-metre minaret and decorated interior repay the trip on their own.',
            },
            {
                'heading': 'Roman roots and mountain cooking',
                'body': 'Long before either, the Romans ran a town here — Municipium S. — whose excavated remains and finds, including fine glass and mosaics, appear in the local heritage museum. Pljevlja’s cool upland climate also gives it a distinctive table: Pljevaljski sir, a crumbly salted cow’s-milk cheese, is prized across Montenegro, and northern staples like heljdopita (buckwheat pie) and slow-cooked lamb suit the mountain air. This is hearty, unfussy food eaten where it is made.',
            },
            {
                'heading': 'Gateway to the north',
                'body': 'Set among the northern mountains near the Tara River, Pljevlja works best as part of a wider northern loop rather than a destination in isolation. The Tara Canyon and the Đurđevića Tara bridge are within reach to the south, the Durmitor National Park and Žabljak beyond them, and the road on toward Serbia passes more of the region’s monasteries. Self-driving is by far the easiest way to string these together.',
            },
        ],
        'external_links': [
            {'label': 'Pljevlja — Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Pljevlja'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel/',
            },
        ],
    },
    {
        'name': 'Kotor',
        'region': 'kotor',
        'place_type': 'coastal',
        'image': 'culture.jpg',
        'featured': True,
        'summary': 'A fortified medieval old town at the head of the bay.',
        'description': 'Wrapped in Venetian walls that climb the mountainside, Kotor’s UNESCO-listed old town is a maze of stone lanes, churches and squares. Climb to the fortress for the classic view over the fjord-like Bay of Kotor.',
        'highlights': [
            'Old Town walking tour',
            'Fortress hike',
            'Bay of Kotor cruise',
            'St. Tryphon Cathedral',
            'Cat Museum',
        ],
        'overview': 'Kotor sits at the innermost point of the Bay of Kotor, a deep limestone inlet often described as the most dramatic fjord-like landscape in southern Europe. UNESCO inscribed the walled old town and its bay setting together in 1979, recognising a street plan and fortifications built up across Illyrian, Roman, Venetian and Austro-Hungarian rule. Romanesque St. Tryphon Cathedral, consecrated in 1166, anchors a tight grid of squares once dedicated to separate trades — arms, flour, milk. Above the rooftops, roughly 1,350 stone steps climb the city walls to the ruined Castle of San Giovanni, a demanding but short hike rewarded with a full sweep of the bay. Kotor is also a major cruise-ship port, so the old town is calmest early morning or after the ships sail at dusk. A resident colony of cats, tied to the town’s seafaring past, gets its own small museum near the cathedral.',
        'faqs': [
            {
                'q': 'How do I get to Kotor?',
                'a': 'Kotor is about 8 km from Tivat Airport and roughly 1 hour from Podgorica Airport by road; regular buses also run along the coast from Budva, Herceg Novi and Dubrovnik.',
            },
            {
                'q': 'Is Kotor worth visiting?',
                'a': 'Yes — its UNESCO-listed old town, encircling fortress walls and dramatic bay setting make it one of the most rewarding stops on the Adriatic coast.',
            },
            {
                'q': 'What’s the best time to visit Kotor?',
                'a': 'Late spring (May–June) and early autumn (September) bring warm weather without the cruise-ship crowds and heat of July–August.',
            },
            {
                'q': 'How long should I spend in Kotor?',
                'a': 'Half a day covers the old town and a walk up the fortress walls; stay a night or two to explore the wider bay, including Perast, at a slower pace.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'May–June and September (warm, fewer cruise crowds)'},
            {'label': 'Ideal for', 'value': 'History lovers, photographers, walkers'},
            {'label': 'Time needed', 'value': 'Half a day (2–4 hours)'},
            {
                'label': 'Getting there',
                'value': 'Coastal bus or 15-min drive from Tivat Airport; ~1 hr from Podgorica Airport',
            },
            {'label': 'Region', 'value': 'Kotor Bay'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~8 km'},
        ],
        'good_for': [
            'history lovers',
            'photographers',
            'cruise-ship day-trippers',
            'walkers',
            'couples',
        ],
        'latitude': 42.4247,
        'longitude': 18.7712,
        'sections': [
            {
                'heading': 'A crossroads of empires',
                'body': 'Kotor first appears in Roman records as Acruvium, but its surviving character is overwhelmingly Venetian: the Republic of Venice governed the city as Cattaro from 1420 to 1797, and the winged lion of St. Mark still watches over its gates. Before Venice came Byzantine, Serbian Nemanjić and briefly independent city-republic rule; afterwards, Napoleonic French, Russian and Austro-Hungarian administrations each added a layer. The defensive walls, running some 4.5 km and rising up to 20 m, were raised and reinforced across those centuries. The Bokeljska Mornarica, the bay’s ancient maritime brotherhood, traces its origins to the ninth century.',
            },
            {
                'heading': 'Through the Sea Gate',
                'body': 'Most visitors enter by the Sea Gate of 1555, above which a socialist-era inscription and the date 21 November 1944 mark the city’s WWII liberation. Inside, the Clock Tower of 1602 rises over the Square of Arms beside a stone pillar of shame once used to punish wrongdoers. St. Tryphon’s Cathedral shows two mismatched baroque bell towers, rebuilt after repeated earthquakes. Tiny St. Luke’s Church of 1195 holds both an Orthodox and a Catholic altar, a mark of the bay’s mixed faith. The Maritime Museum, in the baroque Grgurina Palace, tells the story of Kotor’s sea captains through model ships, portraits and weapons.',
            },
            {
                'heading': 'Climbing the walls and reaching the bay',
                'body': 'Beyond the popular fortress climb, a steeper old caravan trail — the Ladder of Kotor — zigzags up dozens of switchbacks toward Lovćen and the hamlet of Špiljari, offering the same views with a fraction of the crowds. Drivers should note the bay’s geography: the Kamenari–Lepetane ferry shortcuts the long loop around the water, saving the 40-minute drive via Risan. Cruise ships berth right beside the walls, so the old town swells and empties with their schedule; arriving before 9am or after 6pm gives the calmest experience. Tivat Airport lies just 8 km away over the Vrmac ridge.',
            },
            {
                'heading': 'Bay flavours and living traditions',
                'body': 'Kotor’s kitchens lean hard on the water: mussels and oysters farmed off nearby Ljuta, black cuttlefish risotto and grilled Adriatic fish appear on almost every menu, usually paired with a Vranac red or Krstač white from the interior. The patron saint is honoured each February at the Tripundanska feast, when the Maritime Brotherhood performs its centuries-old kolo in historic costume. And then there are the cats: descendants of ships’ mousers, they lounge in every square and have become an unofficial civic emblem, with their own souvenir shops and a small dedicated museum near the cathedral.',
            },
        ],
        'external_links': [
            {
                'label': 'UNESCO World Heritage: Region of Kotor',
                'url': 'https://whc.unesco.org/en/list/125',
            },
            {'label': 'Kotor on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Kotor'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Perast',
        'region': 'kotor',
        'place_type': 'coastal',
        'image': 'dining.jpg',
        'featured': True,
        'summary': 'A tiny baroque town facing two island churches.',
        'description': 'Once home to sea captains, Perast is a single waterfront of baroque palazzos looking out to Our Lady of the Rocks. Slow, photogenic, and famous for sunset dinners by the water.',
        'highlights': [
            'Our Lady of the Rocks boat trip',
            'Baroque waterfront stroll',
            'Sunset dinner by the sea',
        ],
        'overview': 'Perast lines a single curving waterfront beneath St. Nicholas hill, its 17th- and 18th-century baroque palazzos built by the sea captains who once commanded merchant fleets across the Adriatic and Mediterranean. At its peak the town ran its own maritime academy. Just offshore sit two islets: the natural St. George, with its monastery and cemetery, and the artificial Our Lady of the Rocks, said to have grown from rocks and scuttled ships piled up by local sailors since the 15th century after an icon was found on a reef. Its church holds a small museum of votive paintings and an embroidered altar cloth reportedly stitched over 25 years, partly with the maker’s own hair. With under 200 year-round residents, Perast empties out by evening — arrive by boat from Kotor to see the islets, then stay for a quiet dinner on the water.',
        'faqs': [
            {
                'q': 'How do I get to Perast?',
                'a': 'Perast is a 20-minute drive or coastal bus ride from Kotor, and most visitors combine it with a short boat trip to Our Lady of the Rocks.',
            },
            {
                'q': 'Is Perast worth visiting?',
                'a': 'Yes — its baroque waterfront and the two island churches just offshore make it one of the most photogenic stops on the Bay of Kotor.',
            },
            {
                'q': 'What is Our Lady of the Rocks?',
                'a': 'It’s an artificial islet built up since the 15th century by local sailors piling rocks and sunken ships around a reef where an icon was found, now home to a votive-filled church.',
            },
            {
                'q': 'How long should I spend in Perast?',
                'a': 'An hour or two is enough for the waterfront and church, or a half-day with the boat trip to the islets and a seafood lunch.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'April–June and September'},
            {'label': 'Ideal for', 'value': 'Couples, photographers, slow travel'},
            {'label': 'Time needed', 'value': '1–2 hours, or a half-day with a boat trip'},
            {'label': 'Getting there', 'value': '20-min drive or coastal bus from Kotor'},
            {'label': 'Region', 'value': 'Kotor Bay'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~18 km'},
        ],
        'good_for': ['couples', 'photographers', 'boat trips', 'slow travel'],
        'latitude': 42.4881,
        'longitude': 18.7101,
        'sections': [
            {
                'heading': 'Town of sea captains',
                'body': 'For its size Perast produced a remarkable seafaring elite. Under Venetian rule it enjoyed trading privileges and manned galleys against the Ottomans, and in 1698 the captain Marko Martinović opened a nautical school here that trained young Russian noblemen sent west by Tsar Peter the Great to learn navigation. The town packs sixteen palazzi and around seventeen churches into a single seafront. Its landmark is the church of St. Nicholas, whose free-standing baroque campanile — at roughly 55 m the tallest bell tower on the bay — was never finished to its grand original design.',
            },
            {
                'heading': 'The two islets and the Fašinada',
                'body': 'Perast’s fame rests on the pair of islets facing the quay. St. George (Sveti Đorđe) is natural, holding a Benedictine abbey and a dark, cypress-shaded cemetery, and is closed to visitors. Our Lady of the Rocks is man-made, and every 22 July at sunset the townsfolk keep the Fašinada: a procession of boats rows out to drop stones around the island, reinforcing it exactly as their ancestors have for six centuries. Inside its church hang silver votive tablets left by sailors and a 1452 icon of the Madonna and Child attributed to the Kotor painter Lovro Dobričević.',
            },
            {
                'heading': 'When to go and getting around',
                'body': 'Perast is effectively car-free: a barrier keeps traffic out of the narrow waterfront, so drivers park in the lots above the entrance and walk in. Many visitors arrive instead by boat from Kotor, around 12 km along the shore, combining the crossing with a stop at the islets. The town faces roughly east across the bay, so mornings are bright and the palazzi glow at sunset. Spring and September bring the softest light and thinnest crowds; by evening, once the day-trippers leave, its fewer than 200 residents have the stone lanes almost to themselves.',
            },
            {
                'heading': 'Dining on the water',
                'body': 'With almost no beach and no nightlife, Perast’s pleasures are slow: a coffee on a palazzo terrace, a long lunch and a seafood dinner as the light fades over the islets. Restaurants line the water’s edge, serving bay mussels, fresh fish and local Crmnica wines within a few steps of the lapping tide. Because the town is so compact and protected, there is little to do in the conventional sense — the point is to stop moving. Many travellers rate an unhurried evening here, watching boats drift between the two churches, among their fondest memories of the whole coast.',
            },
        ],
        'external_links': [
            {'label': 'Perast on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Perast'},
            {
                'label': 'UNESCO World Heritage: Region of Kotor',
                'url': 'https://whc.unesco.org/en/list/125',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Budva',
        'region': 'budva',
        'place_type': 'coastal',
        'image': 'spa.jpg',
        'featured': True,
        'summary': 'The Riviera’s buzzing beach-and-nightlife hub.',
        'description': 'Budva pairs a walled old town with a long string of beaches and the liveliest nightlife on the coast. A natural base for the central Adriatic.',
        'highlights': ['Walled old town', 'Beach hopping', 'Riviera nightlife'],
        'overview': 'Budva is one of the oldest settlements on the Adriatic, with roots as an Illyrian and later Greek colony reaching back roughly 2,500 years — old enough that a founding myth credits Cadmus of Thebes. Little of that antiquity is visible today: a severe 1979 earthquake flattened much of the old town, and the stone streets, churches and seafront Citadella fortress visitors walk now are careful reconstructions on the original medieval footprint. Budva’s economy shifted hard into tourism from the 1960s onward, and it remains the coast’s busiest resort base, ringed by beaches — Mogren, Ričardova Glava, Jaz — and backed by hills of holiday apartments. The bronze Dancing Girl statue on the eastern promenade, added in 2001, has become the town’s unofficial emblem. Expect the heaviest crowds and liveliest nightlife on the coast here, especially in July and August.',
        'faqs': [
            {
                'q': 'How do I get to Budva?',
                'a': 'Budva is about 25 km from Tivat Airport and well served by coastal buses running along the whole Montenegrin Adriatic.',
            },
            {
                'q': 'Is Budva worth visiting?',
                'a': 'Yes for beaches and nightlife — it’s the coast’s liveliest resort town, though its old town is a post-1979-earthquake reconstruction rather than untouched medieval fabric.',
            },
            {
                'q': 'What’s the best time to visit Budva?',
                'a': 'June and September give warm sea temperatures with fewer crowds than the packed July–August peak.',
            },
            {
                'q': 'How long should I spend in Budva?',
                'a': 'A full day covers the old town and Citadella; most visitors base here 2–3 nights to combine beach time with day trips.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June and September (warm sea, fewer crowds)'},
            {'label': 'Ideal for', 'value': 'Nightlife, beaches, groups'},
            {'label': 'Time needed', 'value': 'A full day, or 2–3 nights as a base'},
            {
                'label': 'Getting there',
                'value': '25-min drive from Tivat Airport; frequent coastal buses',
            },
            {'label': 'Region', 'value': 'Budva Riviera'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~19 km'},
        ],
        'good_for': ['nightlife', 'beach lovers', 'groups', 'first-time visitors'],
        'latitude': 42.2864,
        'longitude': 18.8400,
        'sections': [
            {
                'heading': 'Antiquity beneath the resort',
                'body': 'Budva’s post-earthquake stone lanes sit atop one of the richest archaeological sites on the Adriatic. Excavations have turned up Hellenistic and Roman necropolises whose gold jewellery, helmets and glass now fill the town’s Archaeological Museum. Three small churches cluster at the old town’s seaward tip: the pre-Romanesque Santa Maria in Punta, dated to 840; the Catholic Church of St. John with its tall 19th-century campanile; and the Orthodox Holy Trinity, built in 1804 in banded pink and cream stone. The seafront Citadela fortress, once a military strongpoint, now holds a small maritime library and frames the classic view along the ramparts.',
            },
            {
                'heading': 'Beaches of the Riviera',
                'body': 'The town beach is cramped, so most visitors head out along the coast. A cliff path west of the old town reaches Mogren, a pair of small coves beneath the rocks, in about ten minutes. South stretch the Riviera’s longer sands: Bečići, a broad blue-flag beach, then Kamenovo, Pržno and the fishing coves of Rafailovići. North lies Jaz, an open sweep that has hosted stadium concerts by the Rolling Stones and Madonna. Just offshore floats Sveti Nikola, the largest island on the Montenegrin coast, nicknamed ‘Hawaii’ and reachable by taxi boat from the old harbour through the summer.',
            },
            {
                'heading': 'Nightlife and moving around',
                'body': 'Budva earns its reputation as the coast’s party capital after dark. Top Hill, a vast open-air club on the ridge above town, draws international DJs through July and August, while bars and lounges line the marina and the Slovenska plaža promenade. By day that same promenade is the easy spine of the resort, running past the hotels toward Bečići. Frequent coastal buses link Budva to Kotor, Tivat and Bar, but summer traffic and scarce parking make a car more burden than help in the centre — many visitors simply leave it at the hotel and walk.',
            },
            {
                'heading': 'Festivals and day trips',
                'body': 'There is culture between the beach sessions. Each summer since 1987 the Grad Teatar (Theatre City) festival stages open-air plays, concerts and readings within the old town walls, and the coast around Budva has hosted the regional Sea Dance electronic festival. The town also makes a natural touring base: Sveti Stefan’s famous islet is barely 5 km south, the old royal capital of Cetinje and the Lovćen heights lie less than an hour inland, and the cliff-hung Ostrog Monastery is an easy day trip. For many travellers Budva is less a destination in itself than the busy hub from which the region unfolds.',
            },
        ],
        'external_links': [
            {'label': 'Budva on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Budva'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Sveti Stefan',
        'region': 'budva',
        'place_type': 'coastal',
        'image': 'sailing.jpg',
        'featured': True,
        'summary': 'An iconic islet of terracotta roofs.',
        'description': 'The postcard of Montenegro: a fortified islet of pink-stone villas linked to the shore by a causeway, fringed by pebble beaches.',
        'highlights': ['Iconic islet viewpoint', 'Pebble beaches', 'Coastal walks'],
        'overview': 'Sveti Stefan began in the 15th century as a fortified fishing village of the Paštrović clan, built on a small tidal islet for defence against pirates. Its population was resettled in the 1950s and the entire islet — stone houses, chapel and all — was converted into a single luxury hotel that opened in 1960, drawing a jet-set guest list that reportedly included Sophia Loren and Elizabeth Taylor through the Yugoslav era. After a long closure, it reopened as the Aman Sveti Stefan resort, and the islet is now accessible only to hotel guests. Everyone else views it from the mainland: a pebble beach and short coastal path give the classic photograph of terracotta roofs linked to shore by a narrow causeway. The adjacent Villa Miločer beach and gardens, once the royal family’s summer residence, sit on the same protected stretch of coast.',
        'faqs': [
            {
                'q': 'Can you visit the island of Sveti Stefan?',
                'a': 'Not freely — the islet is a private resort (Aman Sveti Stefan) accessible only to hotel guests, but the classic view is free from the mainland beach and coastal path.',
            },
            {
                'q': 'Is Sveti Stefan worth visiting?',
                'a': 'Yes for the view alone — it’s one of the most photographed spots in Montenegro, especially at sunset from the beach just north of the causeway.',
            },
            {
                'q': 'What’s the best time to visit Sveti Stefan?',
                'a': 'Late afternoon light works best for photos; May, June and September avoid the biggest midday beach crowds.',
            },
            {
                'q': 'How long should I spend at Sveti Stefan?',
                'a': 'An hour or two for the viewpoint and beach is typical unless you’re staying as a resort guest.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late afternoon/sunset; May, June, September for fewer crowds',
            },
            {'label': 'Ideal for', 'value': 'Photographers, couples, honeymooners'},
            {'label': 'Time needed', 'value': '1–2 hours at the viewpoint'},
            {
                'label': 'Getting there',
                'value': '25-min drive from Tivat Airport, between Budva and Petrovac',
            },
            {'label': 'Region', 'value': 'Budva Riviera'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~24 km'},
        ],
        'good_for': ['photographers', 'couples', 'luxury travelers', 'honeymooners'],
        'latitude': 42.2569,
        'longitude': 18.8917,
        'sections': [
            {
                'heading': 'From fortress village to jet-set island',
                'body': 'The islet was settled in the 15th century by the Paštrovići, a self-governing coastal clan who fortified the rock against Ottoman and pirate raids and packed it with stone cottages linked by lanes barely wide enough to pass. In the 1950s the Yugoslav state relocated the fishing families and reinvented the whole island as a single ‘town-hotel’, among the first of its kind, opening in 1960. Through the socialist decades it hosted film stars, writers and royalty. Since 2009 it has run as the Aman Sveti Stefan resort, though it has seen repeated closures amid a long-running dispute over its lease.',
            },
            {
                'heading': 'The Miločer coast',
                'body': 'Immediately north, the Miločer estate wraps the shore in a park of old pines, cypresses and olive trees. At its heart stands Villa Miločer, a 1930s summer residence of the Karađorđević royal family, and below it lie two of Montenegro’s prettiest strands: Kraljičina plaža (Queen’s Beach) and Kraljeva plaža (King’s Beach), sheltered pink-tinged pebble coves backed by greenery. The beaches are managed as part of the resort, with sunbeds for hire, but the coastal footpath threading through the park stays open to all and gives some of the finest angles on the islet.',
            },
            {
                'heading': 'The classic view and getting there',
                'body': 'For non-guests the islet is purely a thing to photograph, and the light matters. A signed pull-off on the Adriatic highway above town frames the postcard shot; down at sea level, the free public beach just north of the causeway gives the iconic head-on view, best in late-afternoon and sunset light. Sveti Stefan sits about 5 km south of Budva and a similar distance north of Petrovac, roughly 25 minutes from Tivat Airport. Drivers park in the lots along the main road and walk down; there is no through traffic on the causeway itself, which is gated at the resort.',
            },
            {
                'heading': 'Where to eat and explore nearby',
                'body': 'Because the island is closed, the life around it happens on the mainland. Neighbouring Pržno, a tiny old fishing cove a short walk north, keeps a public beach and a cluster of konobas grilling the day’s catch. Further south, Petrovac offers a longer beach and a relaxed promenade, while inland the small medieval monasteries of Reževići and Praskvica sit just off the coast road. Most visitors treat Sveti Stefan as a memorable hour on a longer Riviera drive — a viewpoint and a swim — rather than a base, pairing it with Budva or Petrovac for food and a bed.',
            },
        ],
        'external_links': [
            {
                'label': 'Sveti Stefan on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Sveti_Stefan',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Tivat',
        'region': 'tivat',
        'place_type': 'coastal',
        'image': 'sailing.jpg',
        'featured': False,
        'summary': 'Superyacht marina and the Luštica peninsula.',
        'description': 'Once a sleepy naval town, Tivat is now home to Porto Montenegro — a glossy marina of restaurants and boutiques — and the gateway to the Luštica peninsula.',
        'highlights': ['Porto Montenegro marina', 'Luštica peninsula', 'Waterfront dining'],
        'overview': 'Tivat was a modest Austro-Hungarian and later Yugoslav naval town, built around the Arsenal shipyard that serviced the Yugoslav navy for most of the 20th century. That military waterfront was redeveloped from 2007 into Porto Montenegro, a deep-water marina now rated among the best-equipped superyacht harbours in the Mediterranean, ringed by restaurants, a maritime museum inside the old Arsenal buildings, and apartments. Tivat International Airport, just outside town, is Montenegro’s second airport and the main gateway for the whole bay. West of town, the largely undeveloped Luštica peninsula offers quiet coves, the walled village of Rose, and the Luštica Bay resort and golf development. Tivat itself has little historic old town — its appeal is the marina promenade, easy access to Kotor and Herceg Novi, and a noticeably more laid-back, moneyed pace than Budva.',
        'faqs': [
            {
                'q': 'How do I get to Tivat?',
                'a': 'Tivat has its own international airport, and the town centre and Porto Montenegro marina are a short walk or taxi ride from arrivals.',
            },
            {
                'q': 'Is Tivat worth visiting?',
                'a': 'Yes if you enjoy marina life and waterfront dining — it has little historic old town, but Porto Montenegro is the coast’s most polished stretch of restaurants and boutiques.',
            },
            {
                'q': 'What’s the best time to visit Tivat?',
                'a': 'Late spring through early autumn suits the marina and Luštica peninsula best; summer evenings are the liveliest.',
            },
            {
                'q': 'How long should I spend in Tivat?',
                'a': 'A couple of hours covers the marina; add a half-day to explore the quieter Luštica peninsula beyond town.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'Sailors, foodies, couples'},
            {'label': 'Time needed', 'value': '2–3 hours at the marina'},
            {'label': 'Getting there', 'value': 'Tivat International Airport is in town'},
            {'label': 'Region', 'value': 'Tivat & Luštica'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), in town'},
        ],
        'good_for': ['sailors', 'foodies', 'couples', 'luxury travelers'],
        'latitude': 42.4356,
        'longitude': 18.6961,
        'sections': [
            {
                'heading': 'The Arsenal and Porto Montenegro',
                'body': 'Tivat’s waterfront was shaped by the Austro-Hungarian navy, which built the Arsenal shipyard here from 1889; it later serviced Yugoslav warships and submarines, and rock-cut submarine pens still scar the surrounding coast. From 2007 a consortium led by Canadian financier Peter Munk transformed the yard into Porto Montenegro, a marina with berths for some of the largest yachts afloat. Its Naval Heritage Collection, in the old Arsenal buildings, displays the retired submarine Hero and a pair of midget subs on the quay. Boutiques, a naval-themed hotel and waterfront restaurants complete what is now the coast’s most polished promenade.',
            },
            {
                'heading': 'The Luštica peninsula',
                'body': 'West of town the Luštica peninsula stays refreshingly wild. A road runs out to Rose, a stone hamlet at the tip facing Herceg Novi, while boats reach the pebble beaches of Žanjice and Mirišta and the cobalt Blue Grotto sea cave. Just offshore lies Mamula, a 19th-century Austro-Hungarian island fortress controversially converted into a hotel. Above Tivat, the restored hillside village of Gornja Lastva rewards a short climb with old stone houses and bay views, and on the peninsula’s Adriatic side the Luštica Bay development has added a marina, the Chedi hotel and a championship golf course.',
            },
            {
                'heading': 'Getting there and around',
                'body': 'Tivat is the bay’s transport linchpin. Its international airport sits barely 3 km from the marina, making it the closest gateway for Kotor, Budva and Herceg Novi alike. The Kamenari–Lepetane ferry, a 15-minute hop across the bay’s narrowest neck, saves the long drive around the water toward Herceg Novi. Kotor is only about 8 km away and Budva roughly 20 km. In summer, taxi boats fan out from the marina to Luštica’s coves and across to Perast. Late spring to early autumn is the season; outside it, much of the marina’s dining and nightlife winds down.',
            },
            {
                'heading': 'Salt pans, gardens and the marina scene',
                'body': 'For all its yacht-set gloss, Tivat keeps quieter corners. On the town’s edge the Tivatska Solila, a former salt works turned protected wetland, draws herons, egrets and occasional flamingos, with easy birdwatching paths along the old pans. The town park and palm-lined seafront make for gentle strolls, while Porto Montenegro’s restaurants range from casual pizza to fine dining, busiest at aperitivo hour as crews and visitors gather along the quay. The overall mood is calmer and more moneyed than Budva — less a place to sightsee than to settle in for a slow waterfront evening.',
            },
        ],
        'external_links': [
            {'label': 'Tivat on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Tivat'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Žabljak',
        'region': 'durmitor',
        'place_type': 'mountains',
        'image': 'hiking.jpg',
        'featured': True,
        'summary': 'The gateway to Durmitor National Park.',
        'description': 'Montenegro’s highest town and the base for Durmitor — glacial lakes, the Tara Canyon, hiking in summer and skiing in winter.',
        'highlights': ['Durmitor hiking trails', 'Black Lake', 'Tara Canyon', 'Winter skiing'],
        'overview': 'At around 1,450 metres above sea level, Žabljak is the highest town in the Balkans and the only real base for exploring Durmitor National Park. It grew from a small mountain settlement into a modest alpine resort through the 20th century, and its wide, low-rise streets still feel more like a ski village than a historic town — the appeal is entirely what surrounds it. The Black Lake sits an easy 3 km walk away, the Tara Canyon’s rim is a short drive, and the Savin Kuk centre runs lifts in winter and a chairlift with mountain views in summer. Expect a short high season: snow can linger into May, summer hiking runs roughly June to September, and winter sports from December to March. Nights are cold even in summer, so pack layers regardless of when you visit — this is Montenegro’s coldest inhabited town.',
        'faqs': [
            {
                'q': 'How do I get to Žabljak?',
                'a': 'It’s roughly a 2.5–3 hour drive from Podgorica Airport on mountain roads, with no direct flights or rail access — a car, transfer or seasonal bus is essential.',
            },
            {
                'q': 'Is Žabljak worth visiting?',
                'a': 'Yes for access to Durmitor National Park — the town itself is modest, but it’s the only real base for the Black Lake, Tara Canyon and the park’s hiking and skiing.',
            },
            {
                'q': 'What’s the best time to visit Žabljak?',
                'a': 'June to September for hiking, December to March for skiing; snow can linger on higher trails into May.',
            },
            {
                'q': 'How long should I spend in Žabljak?',
                'a': 'Two to four nights lets you cover the Black Lake, at least one longer hike, and a side trip to the Tara Canyon without rushing.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June–September (hiking); December–March (skiing)'},
            {'label': 'Ideal for', 'value': 'Hikers, skiers, nature lovers'},
            {'label': 'Time needed', 'value': '2–4 nights'},
            {
                'label': 'Getting there',
                'value': '~2.5–3 hr drive from Podgorica Airport; no rail or direct flights',
            },
            {'label': 'Region', 'value': 'Durmitor & the North'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~130 km'},
        ],
        'good_for': ['hikers', 'skiers', 'nature lovers', 'adventure travelers'],
        'latitude': 43.1547,
        'longitude': 19.1226,
        'sections': [
            {
                'heading': 'A young town in an old landscape',
                'body': 'Žabljak is barely more than a century old as a town. Its core grew around a mountain trading post and a spring once called Varezina Voda before it took the name Žabljak, and it was repeatedly burned during the World Wars, when the Durmitor highlands were a stubborn partisan stronghold. As a result it holds little historic fabric — a small Orthodox church and a scatter of older houses aside — and its grid of guesthouses, ski shops and pizzerias reads unmistakably as a modern resort. The reason to come stands all around it rather than within it: the peaks, lakes and canyon of Durmitor.',
            },
            {
                'heading': 'Trails from the town',
                'body': 'The gentle 3.6 km loop around the Black Lake is only the beginning. From its shore, marked paths climb to the Ice Cave (Ledena pećina) high on Obla Glava, where ice pillars persist through summer, and toward the red-tinged cliffs of Crvena Greda. Serious hikers set out for Bobotov Kuk, at 2,523 m long considered Durmitor’s highest, a full-day scramble usually begun from the Sedlo pass or Lokvice. Elsewhere the massif hides eighteen glacial lakes and the remote Škrka tarns beneath the Prutaš ridge. The Sedlo road itself, switchbacking over a high saddle, ranks among the most spectacular drives in the country.',
            },
            {
                'heading': 'Winter and the seasons',
                'body': 'In winter Žabljak becomes Montenegro’s main ski town. The Savin Kuk centre rises to around 2,010 m with runs dropping back toward the plateau, while the gentler Javorovača slopes suit beginners and families; the season runs roughly December to March. Summer flips the same lifts into sightseeing chairlifts and the trailheads fill with walkers from June to September. At around 1,450 m this is the coldest inhabited place in the country, and nights stay chilly even in July, so warm layers are essential whatever the calendar says — snow can dust the higher trails well into May.',
            },
            {
                'heading': 'Mountain food and reaching the town',
                'body': 'Northern cooking is hearty and dairy-rich: cicvara and kačamak (cornmeal whipped with cheese and cream), priganice fritters, and lamb or veal slow-cooked ispod sača under an iron bell, often alongside Durmitor-smoked trout or wild blueberries. In the surrounding meadows, seasonal katun shepherd settlements still make cheese the old way. Getting here takes commitment: the drive from Podgorica runs about 2.5–3 hours via Nikšić or the dramatic Tara bridge road, seasonal buses are infrequent, and there is no rail. Most visitors self-drive and base for several nights in a guesthouse or eco-lodge.',
            },
        ],
        'external_links': [
            {
                'label': 'UNESCO World Heritage: Durmitor National Park',
                'url': 'https://whc.unesco.org/en/list/100',
            },
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
            {'label': 'Žabljak on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Žabljak'},
        ],
    },
    {
        'name': 'Lake Skadar',
        'region': 'skadar',
        'place_type': 'lakes',
        'image': 'wine.jpg',
        'featured': False,
        'summary': 'The Balkans’ largest lake and wine country.',
        'description': 'A national park of lily-covered water, island monasteries and birdlife, ringed by the family vineyards of the Crmnica region.',
        'highlights': ['Lake boat safari', 'Island monasteries', 'Crmnica wine tasting'],
        'overview': 'Lake Skadar is the largest lake in Southern Europe, shared between Montenegro and Albania, and protected on the Montenegrin side as a national park since 1983. Its shallow, reed-fringed waters — fed by the Morača river and drained via the Bojana to the Adriatic — support one of Europe’s most important bird habitats, with over 280 recorded species including the Dalmatian pelican, Montenegro’s national bird. Small stone villages and abandoned Venetian-era fortifications ring the shore, and several island monasteries, among them Moračnik and Starčevo, still hold Orthodox relics and frescoes. Virpazar, on the lake’s western edge, is the main gateway for boat safaris. Inland, the Crmnica hills produce Vranac, Montenegro’s signature red grape, in family-run wineries that pre-date the national park by generations.',
        'faqs': [
            {
                'q': 'How do I get to Lake Skadar?',
                'a': 'Virpazar, the main gateway village, is about 35 km and a 40-minute drive from Podgorica Airport, with boat tours departing from its small harbour.',
            },
            {
                'q': 'Is Lake Skadar worth visiting?',
                'a': 'Yes, especially for birdwatchers and anyone wanting a slower, greener contrast to the coast — it’s the Balkans’ largest lake and a major wetland habitat.',
            },
            {
                'q': 'What’s the best time to visit Lake Skadar?',
                'a': 'Spring (April–June) brings the most birdlife and blooming water lilies; summer is best for swimming off the boats.',
            },
            {
                'q': 'How long should I spend at Lake Skadar?',
                'a': 'A half-day boat safari from Virpazar is the standard visit; wine-tasting in Crmnica can extend it to a full day.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'April–June for birdlife and blooms; summer for swimming',
            },
            {'label': 'Ideal for', 'value': 'Birdwatchers, wine lovers, families'},
            {'label': 'Time needed', 'value': 'Half a day for a boat safari'},
            {'label': 'Getting there', 'value': '40-min drive from Podgorica Airport to Virpazar'},
            {'label': 'Region', 'value': 'Lake Skadar'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~35 km'},
        ],
        'good_for': ['birdwatchers', 'wine lovers', 'nature lovers', 'photographers', 'families'],
        'latitude': 42.2461,
        'longitude': 19.0967,
        'sections': [
            {
                'heading': 'A lake that breathes with the seasons',
                'body': 'Skadar is a karst cryptodepression: much of its floor lies below sea level, and deep underwater springs known as oka (‘eyes’) plunge tens of metres down, feeding the lake alongside the Morača river. Its surface swells and shrinks dramatically with the seasons, spreading across low fields in the wet months and drawing back in high summer, when broad rafts of white and yellow water lilies carpet the shallows. Those reed beds and lilies shelter carp, eel and the small bleak (ukljeva) that have sustained local fishermen for centuries, and underpin the extraordinary birdlife the national park was created to protect.',
            },
            {
                'heading': 'Monasteries, fortresses and villages',
                'body': 'History studs the shoreline. Tiny island monasteries — Beška with its two medieval churches, plus Moračnik, Starčevo and Kom — kept Orthodox learning alive under Ottoman pressure. Ringing them are fortresses: Ottoman Besac above Virpazar, the ruined Lesendro on its causeway, and Grmožur, a prison-island once dubbed Montenegro’s Alcatraz. On the northern shore stand the walls of Žabljak Crnojevića, a 15th-century capital of the Crnojević dynasty. Ashore, the old wine village of Godinje is a warren of interconnected stone houses and vaulted cellars, while Karuč and Dodoši keep the rhythm of lakeside fishing life.',
            },
            {
                'heading': 'Wine country and the table',
                'body': 'South of the water rise the Crmnica hills, Montenegro’s most storied wine district, where family cellars around Virpazar, Limljani and Godinje press the deep-red Vranac and its lighter cousin Kratošija from vines worked for generations. Tastings are informal and generous, often paired with home-cured ham, sheep’s cheese and honey. The lake’s own kitchen leans on its catch: carp baked with prunes, smoked bleak, and eel from the Bojana channel. A long lunch of lake fish and Crmnica red, taken on a vine-shaded terrace, is as much the point of a visit as the boat trip that precedes it.',
            },
            {
                'heading': 'Getting there, boats and birds',
                'body': 'Virpazar, the main gateway, sits right beside the Bar–Podgorica highway and railway, so it is reachable even without a car — trains stop at its little station. From the harbour, small boats run half-day safaris deep into the reed channels; kayaks offer a quieter alternative. For birdwatchers the reward is one of Europe’s largest colonies of Dalmatian pelicans, along with pygmy cormorants and herons, best seen in spring around the Pančeva oka wetlands. April to June brings peak birdlife and blooming lilies; midsummer is warmest for swimming straight off the boat into the cool, clear water.',
            },
        ],
        'external_links': [
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
            {
                'label': 'Lake Skadar on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Lake_Skadar',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Ulcinj',
        'region': 'ulcinj',
        'place_type': 'coastal',
        'image': 'kayak.jpg',
        'featured': False,
        'summary': 'The south coast’s long sandy beaches.',
        'description': 'The most southerly town, with an atmospheric old town above the sea and Velika Plaža — a 12 km sweep of sand — just beyond.',
        'highlights': ['Velika Plaža beach', 'Old town above the sea', 'Long sandy coast'],
        'overview': 'Ulcinj is the oldest town on the Montenegrin coast, founded as an Illyrian settlement before becoming the Greek and then Roman colony of Ulcinium. Its fortunes turned darkest under nearly two centuries of Ottoman rule from the 1500s, when the town was a notorious base for Adriatic pirates and, for a time, a slave market — a history still traced in the old town’s narrow, defensible lanes above the sea. Today Ulcinj is the centre of Montenegro’s Albanian and Bosniak Muslim communities, visible in its mosques, language and cuisine, a cultural mix distinct from the rest of the coast. Its draw beyond the old town is scale of sand: Velika Plaža stretches roughly 12 km east toward Ada Bojana, a river island once famed for naturist tourism, giving Ulcinj the softest, widest beaches in a country otherwise dominated by pebbles and rock.',
        'faqs': [
            {
                'q': 'How do I get to Ulcinj?',
                'a': 'Ulcinj is about 70 km south of Podgorica Airport, roughly an hour’s drive, and also reachable by coastal bus from Bar and Podgorica.',
            },
            {
                'q': 'Is Ulcinj worth visiting?',
                'a': 'Yes — it combines Montenegro’s oldest old town with its longest beach, Velika Plaža, and a distinct Albanian-influenced culture unlike the rest of the coast.',
            },
            {
                'q': 'What’s the best time to visit Ulcinj?',
                'a': 'June and September give warm water and quieter beaches; July–August is hottest and busiest.',
            },
            {
                'q': 'How long should I spend in Ulcinj?',
                'a': 'A full day for the old town, with an extra night or two to properly enjoy Velika Plaža and Ada Bojana.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June and September'},
            {'label': 'Ideal for', 'value': 'Beach lovers, families, culture seekers'},
            {'label': 'Time needed', 'value': '1–2 nights'},
            {'label': 'Getting there', 'value': '~1 hr drive from Podgorica Airport'},
            {'label': 'Region', 'value': 'Ulcinj & the south coast'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~70 km'},
        ],
        'good_for': ['beach lovers', 'families', 'budget travelers', 'culture seekers'],
        'latitude': 41.9297,
        'longitude': 19.2003,
        'sections': [
            {
                'heading': 'Corsairs and the citadel',
                'body': 'Ulcinj’s Kalaja, the walled old town on a rocky spur above the sea, carries a darker past than most Adriatic citadels. After the Ottomans took it in 1571 it became a notorious corsair haven, and North African pirates settled here, running a slave market whose legacy included a small community of African descent — the ‘Ulcinj Blacks’ — recorded in the town into the 20th century. Within the walls stand the medieval Balšić Tower, a former church turned mosque, and a museum in the old bishop’s palace. The 1979 earthquake scarred the citadel, but its lanes still tumble atmospherically toward the water.',
            },
            {
                'heading': 'Velika Plaža and Ada Bojana',
                'body': 'South of town the coast changes utterly. Velika Plaža — the Big Beach — runs some 12 km of fine grey sand in a shallow, warm arc, so gently shelving that it draws families and, thanks to steady thermal winds, one of the Adriatic’s liveliest kitesurfing scenes. At its far end lies Ada Bojana, a triangular island formed around a shipwreck where the Bojana river meets the sea; a naturist resort since the 1970s, it is ringed by wooden restaurants on stilts serving some of the freshest fish and eel in the country. Inland, reed-fringed Lake Šas adds more quiet birdwatching.',
            },
            {
                'heading': 'The salt pans and the birds',
                'body': 'Between the town and the beach spreads the Ulcinj Salina, a vast former saltworks now recognised as one of the most important bird habitats on the whole Adriatic flyway. Its shallow, briny pools host greater flamingos, avocets, herons and, at migration peaks, tens of thousands of birds staging between Africa and Europe. After years of neglect the pans have been given protected status, and rough tracks along the dikes make for rewarding, uncrowded birdwatching. For anyone interested in wildlife it is as compelling a reason to visit Ulcinj as the sand itself.',
            },
            {
                'heading': 'A different culture, and when to visit',
                'body': 'Ulcinj feels distinct from the rest of the coast. Albanian is widely spoken alongside Montenegrin, minarets punctuate the skyline, and the call to prayer marks the day; the food carries an Ottoman accent, from grilled fish and ćevapi to syrup-soaked sweets like baklava and tulumba. The festivals of Bajram bring a particular buzz. The town lies about an hour from Podgorica Airport and close to the Albanian border, an easy hop to Shkodër. June and September offer warm sea and thinner crowds; July and August are hottest, busiest and most vividly Mediterranean.',
            },
        ],
        'external_links': [
            {'label': 'Ulcinj on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Ulcinj'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Cetinje',
        'region': 'cetinje',
        'place_type': 'cultural',
        'image': 'culture.jpg',
        'featured': False,
        'summary': 'The historic Old Royal Capital.',
        'description': 'Montenegro’s cultural heart: former royal capital, home to museums, the old court and monastery, tucked in a high karst plain below Mount Lovćen.',
        'highlights': ['Royal court & museums', 'Cetinje Monastery', 'Mount Lovćen'],
        'overview': 'Cetinje was founded in 1482 by Ivan Crnojević as the seat of Zeta, moving his court to this high, defensible plain below Mount Lovćen — a deliberate retreat from the coast as Ottoman power advanced. It served as capital of the independent Kingdom of Montenegro until unification with Serbia in 1918, and its modest scale still shows: grand for its era, it never grew into a conventional city, and former foreign legation buildings from a dozen countries sit among low stone houses. Cetinje Monastery, rebuilt several times, holds relics venerated across the Orthodox world, including a hand of John the Baptist. The Biljarda, once home to the poet-prince-bishop Njegoš, and King Nikola’s palace now form part of the National Museum of Montenegro — a quieter, more scholarly counterpoint to the coast.',
        'faqs': [
            {
                'q': 'How do I get to Cetinje?',
                'a': 'Cetinje is about 35 km from Podgorica Airport and a similar distance inland from Budva, an easy half-day round trip by car or bus from either the coast or the capital.',
            },
            {
                'q': 'Is Cetinje worth visiting?',
                'a': 'Yes for history and culture — as Montenegro’s former royal capital it holds the country’s key museums, monastery and royal palaces in a compact, walkable centre.',
            },
            {
                'q': 'What’s the best time to visit Cetinje?',
                'a': 'Spring and autumn are pleasant for walking; being inland and elevated, it’s cooler than the coast in summer.',
            },
            {
                'q': 'How long should I spend in Cetinje?',
                'a': 'Half a day comfortably covers the monastery, Biljarda and National Museum.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn'},
            {'label': 'Ideal for', 'value': 'History lovers, culture seekers, museum-goers'},
            {'label': 'Time needed', 'value': 'Half a day'},
            {'label': 'Getting there', 'value': '35-min drive from Podgorica Airport or Budva'},
            {'label': 'Region', 'value': 'Cetinje & the Old Royal Capital'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~35 km'},
        ],
        'good_for': ['history lovers', 'culture seekers', 'museum-goers', 'day-trippers'],
        'latitude': 42.3911,
        'longitude': 18.9238,
        'sections': [
            {
                'heading': 'The birth of a capital',
                'body': 'Ivan Crnojević moved his court to this hidden karst plain in 1482, building a palace and, two years later, the first Cetinje Monastery. His son Đurađ set up the Crnojević printing house here around 1493, one of the earliest presses among the South Slavs, which produced the Oktoih liturgical book in Cyrillic. For the next three centuries the town endured a brutal cycle — sacked and burned by the Ottomans, then rebuilt by its prince-bishops — until Njegoš and his successors in the 19th century finally raised it into a settled capital, laying out the squares and stone streets visitors walk today.',
            },
            {
                'heading': 'Palaces and museums',
                'body': 'Cetinje is really an open-air museum of the Montenegrin state. The National Museum spans several landmark buildings: King Nikola’s Palace, kept much as the royal family left it, with thrones, weapons and portraits; the History and Art museums in the former Government House; and the Biljarda, Njegoš’s fortified residence, named for the billiard table hauled up from the coast, beside a pavilion holding a great relief map of Montenegro. The Ethnographic Museum rounds out the group. Nearby, Cetinje Monastery guards its famous relics, said to include the right hand of St. John the Baptist and a fragment of the True Cross.',
            },
            {
                'heading': 'The little diplomatic capital',
                'body': 'When the 1878 Congress of Berlin recognised Montenegro’s independence, the great powers opened legations in its tiny capital, and their embassies still line the centre. The grandest is the former French Embassy, an Art Nouveau confection of coloured tiles utterly unlike its stone neighbours; others, built for Russia, Britain, Italy and Austria-Hungary, now serve as schools, ministries and academies. This belle-époque flourish, wildly outsized for so small a town, gives Cetinje a faintly surreal grandeur — a capital that dressed for a role far larger than its handful of streets could ever fill.',
            },
            {
                'heading': 'Lovćen, caves and getting there',
                'body': 'Cetinje sits about 35 km from both Podgorica and Budva and makes an easy half-day trip from either, though its cool, elevated air is a relief from the summer coast. Above it looms Lovćen, whose summit mausoleum of Njegoš is a short, scenic drive away, and the old serpentine road down to Kotor begins just beyond the town. Other outings cluster close: the show caverns of Lipa Cave on the outskirts, and the coiling river viewpoint at Rijeka Crnojevića a few minutes further. Spring and autumn are ideal for wandering its museums and quiet, walkable streets on foot.',
            },
        ],
        'external_links': [
            {'label': 'Cetinje on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Cetinje'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Herceg Novi',
        'region': 'kotor',
        'place_type': 'coastal',
        'image': 'culture.jpg',
        'featured': True,
        'summary': 'The sunny “city of stairs” at the mouth of the bay.',
        'description': 'Guarding the entrance to the Bay of Kotor, Herceg Novi tumbles down the hillside in a maze of stairways, seaside forts and flowering terraces, with the sunniest weather on the coast.',
        'highlights': ['Forte Mare fortress', 'The famous stairways', 'Mimosa-lined promenade'],
        'overview': 'Herceg Novi was founded in 1382 by the Bosnian king Tvrtko I at the mouth of the Bay of Kotor, then passed in turn through Ottoman, Venetian, Habsburg, French and Austro-Hungarian hands — each leaving fortifications behind, including the Ottoman-built Kanli Kula ("Bloody Tower") and the seafront Forte Mare. That layered history is compressed into a compact old town connected by hundreds of stone stairways climbing the hillside, which locals call being a "city of stairs." Herceg Novi also claims Montenegro’s sunniest, mildest microclimate, supporting palm-lined promenades and a botanical park with subtropical species rarely found elsewhere on the coast. Each February the town holds the Mimosa Festival, a tradition marking the flower’s bloom. Savina Monastery, a short walk along the coast, adds a quieter Orthodox pilgrimage site nearby.',
        'faqs': [
            {
                'q': 'How do I get to Herceg Novi?',
                'a': 'It sits right at the entrance to the Bay of Kotor, about 35 km from Dubrovnik Airport across the Croatian border, or reachable via the Kamenari–Lepetane ferry from the Tivat side.',
            },
            {
                'q': 'Is Herceg Novi worth visiting?',
                'a': 'Yes — its stacked fortresses, stairway streets and mild, sunny microclimate make it a quieter, less touristed alternative to Kotor with real depth of history.',
            },
            {
                'q': 'What’s the best time to visit Herceg Novi?',
                'a': 'Its mild climate makes it pleasant nearly year-round; February’s Mimosa Festival is a distinctive time to visit.',
            },
            {
                'q': 'How long should I spend in Herceg Novi?',
                'a': 'Half a day covers the main fortresses and old town stairways; a full day allows time for the botanical park and Savina Monastery too.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Year-round mild climate; February for the Mimosa Festival',
            },
            {'label': 'Ideal for', 'value': 'History lovers, walkers, garden lovers'},
            {'label': 'Time needed', 'value': 'Half a day to a full day'},
            {
                'label': 'Getting there',
                'value': 'Kamenari–Lepetane ferry from the Tivat side, or via Dubrovnik Airport',
            },
            {'label': 'Region', 'value': 'Kotor Bay'},
            {'label': 'Nearest airport', 'value': 'Dubrovnik Airport (Croatia), ~35 km'},
        ],
        'good_for': ['history lovers', 'walkers', 'off-the-beaten-path travelers', 'garden lovers'],
        'latitude': 42.4531,
        'longitude': 18.5375,
        'sections': [
            {
                'heading': 'Six flags over a fortress town',
                'body': 'Few towns have changed hands so often. Founded in 1382 by the Bosnian king Tvrtko I as Sveti Stefan, Herceg Novi fell to the Ottomans in 1482, was briefly held by a Spanish garrison in 1538 — who left the hilltop Španjola fortress — then passed to Venice in 1687 and later through French, Russian and Austro-Hungarian rule before joining Montenegro in 1918. Each ruler fortified the heights, so the town is crowned by three castles: the seafront Forte Mare, the squat Ottoman Kanli Kula (‘Bloody Tower’) with its open-air stage, and the Španjola on the ridge above, all laced together by the maze of stairways that gives the town its nickname.',
            },
            {
                'heading': 'Stairways and a subtropical garden',
                'body': 'At the heart of the old town, the Belavista square opens beneath the Orthodox Archangel Michael church of 1905, entered through the Ottoman-era Sahat Kula clock-tower gate of 1667. From there stone stairs climb and fall in every direction. Herceg Novi’s returning sea captains planted the exotic species they carried home — mimosa, eucalyptus, agave, palms and cacti — until the whole town became a kind of botanical garden basking in the coast’s mildest climate. That heritage is celebrated each February at the Mimosa Festival, running since 1969, when the yellow blooms fill the promenades in the depths of winter.',
            },
            {
                'heading': 'The seafront and healing waters of Igalo',
                'body': 'The Pet Danica promenade threads several kilometres along the water past small bathing coves and cafés. West lies Igalo, long famous for its peloid — a mineral-rich sea mud drawn from the bay — and the Igalo Institute, a large thalassotherapy spa where the therapeutic mud and mineral springs draw wellness visitors; Tito kept a seaside villa here. Across the bay’s mouth, easily reached by taxi boat, sit the swimming coves of Žanjice and Mirišta, the stone village of Rose, and the glowing Blue Grotto sea cave on the Luštica shore, making Herceg Novi a natural launch point for the outer bay.',
            },
            {
                'heading': 'Getting there and the seasons',
                'body': 'Herceg Novi guards the very entrance to the Bay of Kotor, closer to Dubrovnik than to Podgorica: Dubrovnik Airport is about 35 km away over the Croatian border, and the Kamenari–Lepetane ferry shortcuts the drive toward Tivat and Budva. Its sheltered, sunny microclimate makes it a rare year-round destination on a coast that otherwise sleeps in winter. Beyond the forts and gardens, the hillside Savina Monastery — three Orthodox churches among cypresses above the sea — is a short, peaceful walk from the centre and well worth the detour.',
            },
        ],
        'external_links': [
            {
                'label': 'Herceg Novi on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Herceg_Novi',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Bar',
        'region': 'ulcinj',
        'place_type': 'coastal',
        'image': 'spa.jpg',
        'featured': False,
        'summary': 'Port city and the haunting ruins of Stari Bar.',
        'description': 'Modern Bar is Montenegro’s main port, but just inland the abandoned stone town of Stari Bar climbs a hillside beneath the mountains — ringed by some of the oldest olive groves on earth.',
        'highlights': ['Stari Bar old town', '2,000-year-old olive tree', 'King Nikola’s palace'],
        'overview': 'Modern Bar is a working port town — the country’s main commercial harbour and the ferry link to Bari, Italy — with little to detain visitors on its own. The reason to come is Stari Bar, the abandoned hilltop town 4 km inland, inhabited from Illyrian and Byzantine times through Venetian and Ottoman rule until it was devastated in the 1878 war that brought Montenegro’s independence, after which residents resettled below and the old town was left to ruin. Its stone walls, cisterns, and the shell of a hammam and clock tower still stand open to the sky. Nearby, the Stara Maslina olive tree, estimated by some counts at around 2,000 years old, is still alive and reputedly among the oldest cultivated olive trees on Earth. King Nikola’s summer palace and botanical park sit on Bar’s seafront, a lower-key echo of his main residence in Cetinje.',
        'faqs': [
            {
                'q': 'How do I get to Bar?',
                'a': 'Bar is about 65 km from Podgorica Airport, an hour’s drive, and also has a rail link to Podgorica and a ferry connection to Bari, Italy.',
            },
            {
                'q': 'Is Bar worth visiting?',
                'a': 'The modern town itself is mainly practical, but Stari Bar, the ruined hilltop old town nearby, is genuinely worth the detour.',
            },
            {
                'q': 'What’s the best time to visit Bar?',
                'a': 'Spring and autumn are best for exploring Stari Bar’s exposed ruins without summer heat.',
            },
            {
                'q': 'How long should I spend in Bar?',
                'a': 'Two to three hours covers Stari Bar and the olive tree; modern Bar itself rarely needs more than a stop.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring and autumn'},
            {'label': 'Ideal for', 'value': 'History lovers, day-trippers, ferry travelers'},
            {'label': 'Time needed', 'value': '2–3 hours for Stari Bar'},
            {'label': 'Getting there', 'value': '1 hr drive or rail link from Podgorica Airport'},
            {'label': 'Region', 'value': 'Ulcinj & the south coast'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~65 km'},
        ],
        'good_for': ['history lovers', 'day-trippers', 'ferry travelers'],
        'latitude': 42.0937,
        'longitude': 19.0904,
        'sections': [
            {
                'heading': 'Stari Bar, the ghost town on the hill',
                'body': 'Stari Bar is one of the great ruined cities of the Balkans. Spread over walled terraces on a rocky shelf beneath Mount Rumija, it held more than 200 buildings and was continuously inhabited from early medieval times through Venetian and Ottoman rule. Its decline was sudden: during the siege of 1878, as Montenegro won the town, a powder magazine exploded and much of the upper city was wrecked, never to be rebuilt. Today you wander open ruins of churches, a Turkish bath, cisterns and a clock tower, while a well-preserved Ottoman aqueduct still stalks across the approach. Below the walls, an old bazaar lane and Ottoman bridge survive in the living village.',
            },
            {
                'heading': 'The oldest olives in Europe',
                'body': 'Bar sits amid one of Europe’s densest and oldest olive landscapes — reputedly more than 100,000 trees blanket the coastal slopes. The most famous, the Stara Maslina at Mirovica, is estimated at over 2,000 years old, still bearing fruit within its low protective fence, and ranks among the oldest cultivated olive trees on Earth. Olive oil has anchored the local economy and table for centuries, celebrated at the autumn Maslinijada festival. A visit pairs naturally with a tasting of local oil, cured olives and honey, often at small family groves that welcome curious travellers between the harvest months.',
            },
            {
                'heading': 'The port, the palace and the great railway',
                'body': 'Modern Bar is a purposeful town, rebuilt after WWII around Montenegro’s main port, with car ferries crossing to Bari and Ancona in Italy. It is also the sea terminus of the Belgrade–Bar railway, a 1976 feat of engineering that threads hundreds of tunnels and the soaring Mala Rijeka viaduct through the Dinaric mountains — one of Europe’s most scenic train rides. On the palm-fringed seafront, King Nikola’s Palace of 1885 now houses a local museum and a small botanical garden of exotics the king collected. Above it all rises Mount Rumija, a pilgrimage peak dividing the sea from Lake Skadar.',
            },
            {
                'heading': 'Getting there and when to go',
                'body': 'Bar is about an hour’s drive from Podgorica Airport and doubly connected — by rail north to Podgorica and Belgrade, and by ferry west to Italy — making it a common entry or exit point for the country. Spring and autumn are the best times to explore Stari Bar, whose exposed ruins bake under the midsummer sun. The coast nearby rewards a slower look too: the twin-castle Haj-Nehaj fortress guards the road toward Sutomore, and the vineyards of Crmnica and the shores of Lake Skadar lie just over the hills inland, within an easy half-day’s reach.',
            },
        ],
        'external_links': [
            {'label': 'Bar on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Bar,_Montenegro'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Durmitor National Park',
        'region': 'durmitor',
        'place_type': 'national_parks',
        'image': 'hiking.jpg',
        'featured': True,
        'summary': 'UNESCO peaks, glacial lakes and the Black Lake.',
        'description': 'A UNESCO-listed massif of 48 peaks above 2,000 m, cradling eighteen glacial “mountain eyes”. The Black Lake below Žabljak is its serene, forest-ringed centrepiece.',
        'highlights': [
            'The Black Lake (Crno jezero)',
            '48 peaks over 2,000 m',
            'Hiking & winter skiing',
        ],
        'overview': 'Durmitor was inscribed on the UNESCO World Heritage list in 1980, one of the first natural sites in the former Yugoslavia to be recognised, valued for its glacially carved limestone massif of 48 peaks over 2,000 metres, crowned by Bobotov Kuk at 2,523 m. Eighteen glacial lakes, locally called "gorske oči" or mountain eyes, sit in cirques across the massif; the Black Lake near Žabljak, actually two joined lakes in a forested bowl, is by far the most visited and has an easy 3.6 km circular path. The Tara River canyon forms the park’s dramatic northern edge. Trails range from that gentle lakeside loop to multi-day treks toward Bobotov Kuk and the Prutaš ridge, with the main hiking season running roughly June to September. In winter, Savin Kuk becomes Montenegro’s principal ski centre.',
        'faqs': [
            {
                'q': 'How do I get to Durmitor National Park?',
                'a': 'Žabljak, on the park’s edge, is about a 2.5–3 hour drive from Podgorica Airport; the park itself has no public transport, so a car or organised tour is needed.',
            },
            {
                'q': 'Is Durmitor worth visiting?',
                'a': 'Yes — it’s Montenegro’s premier mountain destination, a UNESCO World Heritage site with glacial lakes, 48 peaks over 2,000 m and some of the Balkans’ best hiking.',
            },
            {
                'q': 'What’s the best time to visit Durmitor?',
                'a': 'June to September for hiking; December to March for skiing at Savin Kuk.',
            },
            {
                'q': 'How long should I spend in Durmitor?',
                'a': 'A full day minimum for the Black Lake and viewpoints; two or more nights if you plan to hike further into the massif.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June–September (hiking); December–March (skiing)'},
            {'label': 'Ideal for', 'value': 'Hikers, skiers, nature lovers'},
            {'label': 'Time needed', 'value': 'Full day minimum; 2+ nights for hiking'},
            {
                'label': 'Getting there',
                'value': 'Base at Žabljak, ~2.5–3 hr drive from Podgorica Airport',
            },
            {'label': 'Region', 'value': 'Durmitor & the North'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~130 km'},
        ],
        'good_for': ['hikers', 'nature lovers', 'skiers', 'adventure travelers', 'photographers'],
        'latitude': 43.1500,
        'longitude': 19.0486,
        'sections': [
            {
                'heading': 'Ice-carved geology and the mountain eyes',
                'body': 'Durmitor is a textbook glacial landscape: an uplifted limestone plateau that Ice Age glaciers gouged into cirques, ridges and 48 summits above 2,000 m, the highest being Bobotov Kuk at 2,523 m. Meltwater filled the hollows to form eighteen glacial lakes, the ‘gorske oči’ or mountain eyes, among them Black, Snake (Zmijsko), Jablan, Modro and the remote Škrka tarns. Three great river canyons — the Tara, Piva and Komarnica — knife around the massif’s edges. Along the Tara survives Crna Poda, a reserve of black pines several centuries old, some among the tallest and oldest in Europe.',
            },
            {
                'heading': 'Hiking the massif',
                'body': 'Trails suit every ambition. The easy Black Lake loop and the climb to the summer Ice Cave are the classics; stronger walkers tackle the flower-strewn Prutaš ridge or the long, exposed scramble up Bobotov Kuk, usually launched from the Sedlo pass or the Lokvice shepherd huts. Multi-day routes push into the wild Škrka basin, sleeping at a mountain hut between two tarns. Drivers can trace the Durmitor Ring, roughly 80 km of scenic road looping past Sedlo, remote katun hamlets and dizzying viewpoints. At the massif’s northern foot, the Tara offers Montenegro’s premier white-water rafting.',
            },
            {
                'heading': 'Winter and wildlife',
                'body': 'Snow transforms the park from December into a quiet white wilderness. Savin Kuk, rising to around 2,010 m, is the country’s principal ski centre, with gentler learner slopes at Javorovača nearby, and snowshoe routes fan out from Žabljak across the plateau. The forests and crags shelter serious wildlife — brown bear, wolf, wild boar and chamois — with golden eagles and other raptors overhead, though sightings demand patience and distance. Rare and endemic plants flourish in the meadows once the snow retreats, making late June and July as rewarding for botanists as for peak-baggers.',
            },
            {
                'heading': 'Practicalities: base, entry and seasons',
                'body': 'Almost everyone bases in Žabljak, on the park’s eastern edge, where guesthouses, gear shops and trailheads cluster; a modest entry fee applies at the Black Lake. The main hiking window is June to September, once the snow clears the higher passes; the spectacular Sedlo road is often blocked by snow in winter. For Bobotov Kuk and the Škrka lakes a local guide is wise, as the weather turns fast at altitude. Reaching the park means driving — about 2.5–3 hours from Podgorica — and it pairs naturally with the Tara Canyon and a raft trip on the same visit.',
            },
        ],
        'external_links': [
            {
                'label': 'UNESCO World Heritage: Durmitor National Park',
                'url': 'https://whc.unesco.org/en/list/100',
            },
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
            {'label': 'Durmitor on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Durmitor'},
        ],
    },
    {
        'name': 'Tara Canyon',
        'region': 'durmitor',
        'place_type': 'national_parks',
        'image': 'hiking.jpg',
        'featured': True,
        'summary': 'Europe’s deepest river canyon.',
        'description': 'Carved 1,300 m deep by the emerald Tara, this is the deepest canyon in Europe and the second deepest on earth — best seen from the Đurđevića Tara bridge or from a raft on the water.',
        'highlights': ['Đurđevića Tara bridge', 'White-water rafting', 'Emerald river & cliffs'],
        'overview': 'The Tara River has cut a canyon roughly 82 km long and up to 1,300 metres deep, long marketed as Europe’s deepest and, by some measures, the world’s second-deepest after the Grand Canyon — a comparison tourism boards repeat more confidently than geographers do, but the scale is real regardless. The Đurđevića Tara Bridge, a five-arch concrete span completed in 1940 and rising 172 metres above the water, carries the main Žabljak road and doubles as the canyon’s best free viewpoint, with a small zipline now strung across the gorge beside it. The bridge has its own wartime story: in 1942 its engineer helped destroy one of its own spans to block occupying Italian forces, and was executed there soon after. Below, the emerald-green Tara is Montenegro’s main white-water rafting river, with trips running roughly April to October.',
        'faqs': [
            {
                'q': 'How do I get to Tara Canyon?',
                'a': 'The Đurđevića Tara Bridge, the main viewpoint, sits on the Žabljak–Mojkovac road, about a 2.5-hour drive from Podgorica Airport.',
            },
            {
                'q': 'Is Tara Canyon worth visiting?',
                'a': 'Yes — it’s one of the deepest river canyons in the world, with the bridge viewpoint alone worth the drive, and rafting is a highlight for active travellers.',
            },
            {
                'q': 'What’s the best time to visit Tara Canyon?',
                'a': 'April to October for rafting, when water levels and weather suit trips; the viewpoint and bridge are accessible year-round, snow permitting.',
            },
            {
                'q': 'How long should I spend at Tara Canyon?',
                'a': 'An hour or two for the bridge and viewpoints; a full day if you add white-water rafting.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'April–October for rafting'},
            {'label': 'Ideal for', 'value': 'Adventure travelers, rafters, photographers'},
            {'label': 'Time needed', 'value': 'Half a day (viewpoint); a full day for rafting'},
            {
                'label': 'Getting there',
                'value': '~2.5 hr drive from Podgorica Airport to the Đurđevića Tara bridge',
            },
            {'label': 'Region', 'value': 'Durmitor & the North'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~140 km'},
        ],
        'good_for': ['adventure travelers', 'rafters', 'photographers', 'road-trippers'],
        'latitude': 43.2661,
        'longitude': 19.0328,
        'sections': [
            {
                'heading': 'The Tear of Europe',
                'body': 'Montenegrins call the Tara the ‘Suza Evrope’, the Tear of Europe, for water so clean it is drinkable straight from the river along much of its course. Rising in the Durmitor highlands, it runs about 140 km north before joining the Piva at Šćepan Polje to form the Drina on the Bosnian border. The whole basin was declared a UNESCO Biosphere Reserve in 1976 and folded into the Durmitor World Heritage site, protecting cliffs up to 1,300 m high, hanging side-waterfalls, and dense forests of beech and black pine that cloak the canyon walls far below the rim.',
            },
            {
                'heading': 'Rafting the emerald water',
                'body': 'Rafting is the definitive Tara experience. The classic run drops through the wildest lower gorge from Brštanovica down to Šćepan Polje, roughly 18 km of some fifty named rapids threaded between sheer walls and side-streams spilling from the cliffs. Spring snowmelt in April and May pushes the water highest and fastest; by high summer it calms to a gentler, family-friendly float. Trips launch from riverside camps, with wetsuits, helmets and guides provided, and range from a half-day taster to a full day on the water. It remains the most exhilarating way to grasp the canyon’s true scale.',
            },
            {
                'heading': 'The bridge, the ziplines and the viewpoints',
                'body': 'The Đurđevića Tara Bridge is the canyon’s stage. Beside it stands a memorial to Lazar Jauković, the engineer who, having helped build the span, blew up its central arch in 1942 to slow occupying forces and was executed on the bridge soon after; the arch was rebuilt after the war. Today ziplines streak across the gorge from the bridge, the longest running several hundred metres to the far bank. For a loftier perspective, the Ćurevac viewpoint inside Durmitor National Park perches around 1,000 m directly above the river, taking in a vast sweep of the canyon at a glance.',
            },
            {
                'heading': 'Getting there and when to go',
                'body': 'The bridge sits on the main road between Žabljak and Mojkovac, about 2.5 hours from Podgorica Airport, and slots easily into any Durmitor itinerary. The rafting season runs roughly April to October; many operators base at Šćepan Polje, right on the Bosnian frontier, where the Tara meets the Piva. The viewpoint and bridge stay accessible year-round, snow permitting. Nearby, the little Dobrilovina Monastery guards the canyon’s eastern approach. For the fullest picture, come in late spring, when high water, green forests and thundering side-falls show the gorge at its most dramatic.',
            },
        ],
        'external_links': [
            {
                'label': 'UNESCO World Heritage: Durmitor National Park',
                'url': 'https://whc.unesco.org/en/list/100',
            },
            {
                'label': 'Tara River Canyon on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Tara_River_Canyon',
            },
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
        ],
    },
    {
        'name': 'Ostrog Monastery',
        'region': 'podgorica',
        'place_type': 'cultural',
        'image': 'culture.jpg',
        'featured': True,
        'summary': 'A white monastery set into a sheer cliff.',
        'description': 'Montenegro’s most revered pilgrimage site, the upper monastery of Ostrog is carved directly into a vertical rock face, drawing visitors of every faith to the shrine of St. Basil.',
        'highlights': [
            'Cliff-carved upper monastery',
            'Shrine of St. Basil',
            'Sweeping valley views',
        ],
        'overview': 'Ostrog Monastery was founded in the mid-17th century by Vasilije (Basil) of Ostrog, a Metropolitan of Herzegovina later canonised as St. Basil of Ostrog, who chose to build directly into a sheer cliff face of the Ostroška Greda around 900 metres above the valley floor. The Upper Monastery, cut partly into the rock itself, holds his relics and a small chapel with frescoes painted straight onto the stone; a separate Lower Monastery, completed in the 1870s, serves as the parish church and pilgrim reception point further down the access road. Ostrog draws pilgrims of every faith — Orthodox, Catholic and Muslim alike — in numbers that swell into the hundreds of thousands around major feast days, making it Montenegro’s single most-visited religious site. Cars can drive most of the way up; the final approach is on foot along a path cut into the cliff.',
        'faqs': [
            {
                'q': 'How do I get to Ostrog Monastery?',
                'a': 'It’s about 50 km, roughly an hour’s drive, from Podgorica Airport; a paved road climbs most of the way, with the final stretch to the Upper Monastery on foot or by shuttle.',
            },
            {
                'q': 'Is Ostrog Monastery worth visiting?',
                'a': 'Yes — its cliff-face setting is genuinely striking, and it’s Montenegro’s most important pilgrimage site regardless of faith.',
            },
            {
                'q': 'What’s the best time to visit Ostrog?',
                'a': 'Weekday mornings outside major Orthodox feast days are quietest; the site can draw very large crowds on religious holidays.',
            },
            {
                'q': 'How long should I spend at Ostrog Monastery?',
                'a': 'Two to three hours covers the Upper and Lower Monasteries and the drive up.',
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Weekday mornings; avoid major Orthodox feast days for crowds',
            },
            {'label': 'Ideal for', 'value': 'Pilgrims, history lovers, day-trippers'},
            {'label': 'Time needed', 'value': '2–3 hours'},
            {'label': 'Getting there', 'value': '~1 hr drive from Podgorica Airport'},
            {'label': 'Region', 'value': 'Podgorica'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~50 km'},
        ],
        'good_for': ['pilgrims', 'history lovers', 'day-trippers', 'photographers'],
        'latitude': 42.8508,
        'longitude': 18.9539,
        'sections': [
            {
                'heading': 'St. Basil and the cliff churches',
                'body': 'The monastery grew around Vasilije Jovanović (1610–1671), Metropolitan of Herzegovina, who withdrew to this cliff as Ottoman pressure mounted and gathered a small community in the rock. The Upper Monastery holds two tiny cave churches built into the stone: the Church of the Presentation, whose late-17th-century frescoes were painted directly onto the rough rock by the master Radul, and, higher up, the Church of the Holy Cross. Canonised as St. Basil of Ostrog, Vasilije’s incorrupt relics still lie in a reliquary here, tended by monks and venerated by the stream of pilgrims who come seeking healing.',
            },
            {
                'heading': 'A pilgrimage for every faith',
                'body': 'Ostrog’s pull crosses religious lines: Orthodox, Catholic and Muslim visitors alike come to pray and ask for help, an unusual shared devotion. The great feast is Pentecost (Trojičindan), when tens of thousands converge and the most fervent climb the final approach barefoot, some sleeping overnight on the stone terrace before the shrine. Pilgrims leave votive gifts, and a gnarled grapevine, said to have sprung from the bare rock where the saint died, is pointed out as one of the site’s miracles. Even on ordinary days the atmosphere is hushed and intense, quite unlike anywhere else in the country.',
            },
            {
                'heading': 'The setting and the approach',
                'body': 'The shrine’s drama lies in its position: a dazzling white façade pressed into the grey Ostroška Greda cliff, roughly 900 m above the green Bjelopavlići plain, so that from below it seems to hang in the rock. Most visitors first reach the Lower Monastery, built in the 1820s around the Holy Trinity church and a spring, with a guesthouse and small museum. From there a narrow road switchbacks about 3 km up to the Upper Monastery; the very last stretch is covered on foot along a path cut into the cliff. The views back over the valley widen with every hairpin of the climb.',
            },
            {
                'heading': 'Getting there, etiquette and timing',
                'body': 'Ostrog lies about 50 km from Podgorica Airport, an hour’s drive, signed off the Podgorica–Nikšić road near Danilovgrad. Entry is free, but it is a working monastery: modest dress covering shoulders and knees is expected, and photography is restricted inside the shrine. Weekday mornings are calmest; major Orthodox feast days bring immense crowds and slow traffic on the access road. It is easily combined with Nikšić or the wider Ostrog region on a day trip, and simple overnight lodging in the Lower Monastery’s konak lets early risers reach the upper shrine before the coaches arrive.',
            },
        ],
        'external_links': [
            {
                'label': 'Ostrog Monastery on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Ostrog_Monastery',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Lovćen National Park',
        'region': 'budva',
        'place_type': 'national_parks',
        'image': 'hiking.jpg',
        'featured': False,
        'summary': 'The black mountain that named the country.',
        'description': 'The twin peaks of Lovćen loom over the coast; the higher is crowned by the Njegoš Mausoleum, reached up 461 steps, with a panorama that on a clear day spans most of Montenegro.',
        'highlights': [
            'Njegoš Mausoleum',
            '461 steps to the summit',
            'Coast-to-mountains panorama',
        ],
        'overview': 'Lovćen gives Montenegro its name — "Crna Gora," black mountain — from the dark pine forest that once cloaked its slopes as seen from the sea. The national park, one of Montenegro’s oldest, centres on twin limestone peaks, Štirovnik (1,749 m) and Jezerski vrh (1,657 m), the latter capped by the mausoleum of Petar II Petrović-Njegoš, the 19th-century prince-bishop and poet who remains the country’s most revered literary figure. Designed by Croatian sculptor Ivan Meštrović and completed in 1974, the mausoleum is reached via a tunnel and a stair of 461 steps cut into the rock, opening onto a panorama that on a clear day takes in the Bay of Kotor, much of the coast, and the mountains beyond. The park’s lower slopes, crossed by the old carriage road via Njeguši, were the historic route between the coast and the former royal capital, Cetinje.',
        'faqs': [
            {
                'q': 'How do I get to Lovćen National Park?',
                'a': 'It’s about a 40-minute drive from Kotor via the old serpentine road through Njeguši, or roughly 35 km from Tivat Airport.',
            },
            {
                'q': 'Is Lovćen worth visiting?',
                'a': 'Yes — the drive alone offers some of Montenegro’s best coastal panoramas, and the Njegoš Mausoleum at the summit is a short, worthwhile climb.',
            },
            {
                'q': 'What’s the best time to visit Lovćen?',
                'a': 'Late spring through early autumn; the summit road can be affected by snow, fog or high winds in winter.',
            },
            {
                'q': 'How long should I spend at Lovćen National Park?',
                'a': 'Half a day, including the drive up from the coast and the climb to the mausoleum.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late spring to early autumn'},
            {'label': 'Ideal for', 'value': 'Hikers, photographers, road-trippers'},
            {'label': 'Time needed', 'value': 'Half a day'},
            {
                'label': 'Getting there',
                'value': '40-min drive from Kotor via the old serpentine road',
            },
            {'label': 'Region', 'value': 'Budva Riviera'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~35 km'},
        ],
        'good_for': ['hikers', 'photographers', 'road-trippers', 'history lovers'],
        'latitude': 42.3986,
        'longitude': 18.8344,
        'sections': [
            {
                'heading': 'Njegoš and his mountain tomb',
                'body': 'Lovćen is inseparable from Petar II Petrović-Njegoš (1813–1851), the prince-bishop whose epic poem The Mountain Wreath made him the national poet. He asked to be buried high on the mountain, and a chapel was raised on Jezerski vrh in 1855. Shattered by shelling in the First World War and later rebuilt, it was controversially replaced by the Yugoslav state in 1974 with a monumental granite mausoleum designed by the sculptor Ivan Meštrović. Reached through a tunnel and 461 steps, it shelters a huge black statue of Njegoš beneath a gold-mosaic canopy, guarded by two giant caryatids in national dress; his sarcophagus rests in the crypt below.',
            },
            {
                'heading': 'The park, peaks and Ivanova korita',
                'body': 'Beyond the mausoleum spreads one of Montenegro’s oldest national parks, protected since 1952, a karst world of sinkholes, beech and black-pine forest and hardy endemic wildflowers, with rich birdlife overhead. Its true summit is Štirovnik at 1,749 m, slightly higher than the mausoleum’s Jezerski vrh at 1,657 m. At the park’s heart lies Ivanova korita, a green upland meadow with mountain lodges, an information centre and a web of walking and cycling trails, plus a small adventure park — a cool, pine-scented base for a day’s exploring high above the summer heat of the coast.',
            },
            {
                'heading': 'The old road and Njeguši',
                'body': 'Half the pleasure of Lovćen is the journey up. The historic Kotor–Cetinje road corkscrews out of the bay in some twenty-five tight hairpins — the old ‘Ladder of Cattaro’ — each bend opening a wider view over Kotor and its fjord-like inlet. The road threads through Njeguši, the ancestral village of the Petrović dynasty and the home of Montenegro’s celebrated smoked ham and cheese, an almost obligatory tasting stop. This was for centuries the main link between the coast and the royal capital at Cetinje, and it remains one of the most scenic drives anywhere in the Balkans.',
            },
            {
                'heading': 'Getting there and when to go',
                'body': 'Lovćen is about a 40-minute drive from Kotor up the serpentine, or a short hop from Cetinje on the inland side; both the park and the mausoleum charge a small entry fee. The summit and its 461 steps are best tackled from late spring to early autumn, as snow, fog or high wind can close the road and mausoleum in winter. Aim for a clear morning: from the top the panorama can reach across the Bay of Kotor, much of the coast and, on rare cloudless days, far out over the Adriatic. It pairs naturally with Cetinje and Njeguši on a single loop.',
            },
        ],
        'external_links': [
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
            {'label': 'Lovćen on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Lovćen'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Biogradska Gora',
        'region': 'durmitor',
        'place_type': 'national_parks',
        'image': 'hiking.jpg',
        'featured': False,
        'summary': 'One of Europe’s last primeval forests.',
        'description': 'A pocket of virgin forest — one of only three left in Europe — wrapped around a glacial lake, with 500-year-old trees, gentle trails and clear mountain air.',
        'highlights': ['Biograd glacial lake', '500-year-old trees', 'Easy lakeside trails'],
        'overview': 'Biogradska Gora protects one of Europe’s last three remaining primeval forests, roughly 1,600 hectares of old-growth beech, fir and spruce that has never been commercially logged. King Nikola I set the area aside as a royal hunting reserve in 1878 after a dispute with local villagers over logging rights, inadvertently preserving it; it became a national park in 1952, one of Montenegro’s first. Some trees exceed 500 years old and 50–60 metres in height. At the forest’s centre lies Biogradsko jezero, a glacial lake at around 1,094 metres elevation, ringed by an easy, mostly flat 3.5 km path suited to families. The park sits within the wider Bjelasica mountain range on the route linking Kolašin to Žabljak; rowing boats can be hired on the lake in summer, and marked trails climb into quieter alpine meadows beyond it.',
        'faqs': [
            {
                'q': 'How do I get to Biogradska Gora?',
                'a': 'It’s about 85 km, roughly a 2-hour drive, from Podgorica Airport, near the town of Kolašin in central Montenegro.',
            },
            {
                'q': 'Is Biogradska Gora worth visiting?',
                'a': 'Yes for nature lovers — it protects one of Europe’s last three primeval forests, and the lakeside trail is gentle enough for most fitness levels.',
            },
            {
                'q': 'What’s the best time to visit Biogradska Gora?',
                'a': 'June to September for full access and warm weather; the beech forest also colours well in early autumn.',
            },
            {
                'q': 'How long should I spend at Biogradska Gora?',
                'a': 'Half a day for the lake loop; a full day if you continue onto the longer trails into the surrounding mountains.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June–September'},
            {'label': 'Ideal for', 'value': 'Hikers, nature lovers, families'},
            {
                'label': 'Time needed',
                'value': 'Half a day (lake loop); a full day for longer trails',
            },
            {'label': 'Getting there', 'value': '~2 hr drive from Podgorica Airport, near Kolašin'},
            {'label': 'Region', 'value': 'Durmitor & the North'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~85 km'},
        ],
        'good_for': ['hikers', 'nature lovers', 'families', 'photographers'],
        'latitude': 42.8994,
        'longitude': 19.6103,
        'sections': [
            {
                'heading': 'A gift that saved a forest',
                'body': 'The forest owes its survival to a single 19th-century gesture. In 1878, the story goes, people of the surrounding region presented the mountain of Biograd to Prince Nikola to shield it from the axes then clearing so much of the Balkans; he declared it protected, and the core has never been commercially logged since. That makes it one of Europe’s oldest conservation areas as well as one of only a handful of true primeval forests left on the continent. Within its strictly guarded heart, towering beech, fir, spruce, maple and elm grow tangled with fallen deadwood, an ecosystem left entirely to its own slow rhythms.',
            },
            {
                'heading': 'A green mountain of lakes',
                'body': 'Biogradska Gora sits within the Bjelasica, a massif unusual in Montenegro for its volcanic, water-holding rock rather than dry limestone — which is why it feels so lush, threaded with streams, meadows and no fewer than six glacial lakes. The largest, Biogradsko jezero at about 1,094 m, mirrors the forest around its shore. Higher up lie smaller tarns such as Pešića and Ursulovačko, reached on longer trails, while the range crests at Crna glava, 2,139 m. The rounded, grassy uplands blaze with wildflowers in early summer and turn to gold as the beech forest colours in autumn.',
            },
            {
                'heading': 'Trails, wildlife and shepherd huts',
                'body': 'An easy educational trail rings the main lake in about an hour, level enough for families and often walked alongside a rowing boat hired at the shore. Beyond it, marked paths climb through the old-growth forest toward the high lakes and peaks like Zekova glava and Crna glava, longer outings for stronger walkers. The forest shelters red deer, brown bear, wolf and wild boar, with trout in the cold lake and more than 200 bird species overhead. On the surrounding slopes, seasonal katun settlements still graze livestock and make cheese through the summer, much as they have for generations.',
            },
            {
                'heading': 'Getting there and when to go',
                'body': 'The park lies near Kolašin in central Montenegro, roughly 85 km — about two hours — from Podgorica Airport, though the new Bar–Boljare motorway has cut the drive from Podgorica to Kolašin to well under an hour. A small entry fee applies at the gate on the lake road. June to September brings the warmest, greenest conditions and full access to the higher trails, while late September and October set the beech woods ablaze. Kolašin itself makes a handy base, doubling as a modest ski resort in winter, and the Tara Canyon lies within easy reach for a combined northern trip.',
            },
        ],
        'external_links': [
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
            {
                'label': 'Biogradska Gora on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Biogradska_Gora',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Rijeka Crnojevića',
        'region': 'skadar',
        'place_type': 'lakes',
        'image': 'wine.jpg',
        'featured': False,
        'summary': 'A serpentine river village on Lake Skadar.',
        'description': 'Where the Crnojević river coils through green hills into Lake Skadar, this tiny village with its old stone bridge is one of Montenegro’s most photographed views — and a gateway for lake cruises.',
        'highlights': ['The famous river bend', 'Old stone bridge', 'Lake Skadar cruises'],
        'overview': 'Rijeka Crnojevića takes its name from Ivan Crnojević, the 15th-century ruler who briefly kept his court here before relocating it to Cetinje, and the village served for a time as a river port trading with Lake Shkodër towns before Cetinje eclipsed it. The Crnojević River, a short but historically navigable tributary of Lake Skadar, loops through green karst hills in tight bends directly below the village; the view from the hillside road above — the river coiling through the valley — is one of the most reproduced images of inland Montenegro. An arched stone bridge, built in 1853 under Prince Danilo I, still carries foot traffic across the river in the village centre. Rijeka Crnojevića is one of the main departure points for boat trips into Lake Skadar National Park’s quieter northern reaches, away from the busier Virpazar docks.',
        'faqs': [
            {
                'q': 'How do I get to Rijeka Crnojevića?',
                'a': 'It’s about 30 km, a 30–40 minute drive, from Podgorica Airport, and a common stop on boat tours or drives around Lake Skadar.',
            },
            {
                'q': 'Is Rijeka Crnojevića worth visiting?',
                'a': 'Yes — the hillside viewpoint over the river’s bends is one of Montenegro’s most photographed inland views, and the village itself is a peaceful stop.',
            },
            {
                'q': 'What’s the best time to visit Rijeka Crnojevića?',
                'a': 'Spring gives the greenest scenery and highest water levels for boat trips.',
            },
            {
                'q': 'How long should I spend in Rijeka Crnojevića?',
                'a': 'An hour for the viewpoint and bridge, or a half-day if combined with a Lake Skadar boat trip.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring for greenery and water levels'},
            {'label': 'Ideal for', 'value': 'Photographers, nature lovers, slow travel'},
            {'label': 'Time needed', 'value': '1–2 hours, or a half-day with a boat trip'},
            {'label': 'Getting there', 'value': '30–40 min drive from Podgorica Airport'},
            {'label': 'Region', 'value': 'Lake Skadar'},
            {'label': 'Nearest airport', 'value': 'Podgorica Airport (TGD), ~30 km'},
        ],
        'good_for': ['photographers', 'nature lovers', 'slow travel', 'boat trips'],
        'latitude': 42.3181,
        'longitude': 19.0364,
        'sections': [
            {
                'heading': 'A river capital in miniature',
                'body': 'Ivan Crnojević briefly seated his court on this river in the late 15th century before moving inland to Cetinje, and the settlement kept a role out of proportion to its size. Under the Petrović princes in the 19th century it revived as Montenegro’s busiest inland port: fish — above all the prized bleak and eel of Lake Skadar — grain and goods were loaded here for the run down to Shkodër and the Adriatic, and a customs house and warehouses lined the quay. The graceful single-arch Danilov Bridge, built in 1853 under Prince Danilo I, still spans the water in the village centre, a relic of that trading heyday.',
            },
            {
                'heading': 'The famous bend at Pavlova Strana',
                'body': 'The image that draws most visitors is not in the village but on the hillside above it. From the Pavlova Strana viewpoint, the Crnojević River coils into a near-perfect horseshoe bend, wrapping around a green spur before straightening toward Lake Skadar — one of the most photographed scenes in the country. Early morning, when mist often hangs over the water, is the moment photographers wait for. The river itself is short and spring-fed, welling up from the Obodska cave nearby, and its glassy, slow-moving surface mirrors the surrounding karst hills along much of its course.',
            },
            {
                'heading': 'Boats into the quiet northern lake',
                'body': 'Rijeka Crnojevića is the main launch point for exploring the calmer northern reaches of Lake Skadar, away from the busier docks at Virpazar. Small boats glide out through reed channels and rafts of water lilies toward the island monastery of Kom and hidden inlets thick with birdlife — pelicans, herons and cormorants among them — while kayaks let you drift the river at an even gentler pace. Because far fewer visitors start here, the trips feel more private, and the slow water and overhanging greenery give the whole excursion a serene, almost dreamlike quality on a still day.',
            },
            {
                'heading': 'Food, and getting there',
                'body': 'The village is renowned for its fish. A cluster of riverside konobas serves the lake’s classics — carp, eel and smoked bleak, often with a local Crmnica wine — and a leisurely lunch by the old bridge is central to the appeal. Rijeka Crnojevića sits about 30 km from Podgorica Airport and a similar distance from Cetinje, reached by a scenic back road, so it slots neatly into a day linking the old royal capital with Lake Skadar. Spring brings the greenest hills and highest water for boat trips; autumn offers soft light and quiet, with the summer day-trippers long gone.',
            },
        ],
        'external_links': [
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me/en'},
            {
                'label': 'Rijeka Crnojevića on Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Rijeka_Crnojevića',
            },
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Njeguši',
        'region': 'kotor',
        'place_type': 'mountains',
        'image': 'dining.jpg',
        'featured': False,
        'summary': 'The mountain village of pršut and cheese.',
        'description': 'High on the Lovćen road above Kotor, Njeguši is the birthplace of the Petrović dynasty and the home of Montenegro’s famous smoked ham and cheese, cured in the mountain wind.',
        'highlights': [
            'Njeguši pršut & cheese',
            'Birthplace of the Petrovićs',
            'Lovćen serpentine views',
        ],
        'overview': 'Njeguši is a scattered mountain village around 900 metres up the old Kotor–Cetinje road, on the same historic route that switchbacks up from the bay through dozens of hairpin bends known as the Kotor Serpentine. It is the ancestral home of the Petrović-Njegoš dynasty, which ruled Montenegro as prince-bishops and later princes from the 17th century until 1918, and the birthplace in 1813 of Petar II Petrović-Njegoš, the philosopher-poet-ruler still considered the national poet; his modest birth house is preserved as a small museum. The village’s cool, dry mountain air has for generations been used to cure njeguški pršut, a smoke-dried ham, and njeguški sir, a hard sheep’s-milk cheese, both sold from small family smokehouses and konobas along the road.',
        'faqs': [
            {
                'q': 'How do I get to Njeguši?',
                'a': 'It’s on the old Kotor–Cetinje road, about a 30-minute drive up the serpentine from Kotor, or roughly 30 km from Tivat Airport.',
            },
            {
                'q': 'Is Njeguši worth visiting?',
                'a': 'Yes if you like food and history — it’s the birthplace of the Petrović-Njegoš dynasty and the source of Montenegro’s best-known smoked ham and cheese.',
            },
            {
                'q': 'What’s the best time to visit Njeguši?',
                'a': 'Spring through autumn, ideally combined with a clear day for the mountain road’s views.',
            },
            {
                'q': 'How long should I spend in Njeguši?',
                'a': 'An hour is enough for a tasting stop and the Njegoš birth house, usually en route between Kotor, Lovćen and Cetinje.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Spring through autumn'},
            {'label': 'Ideal for', 'value': 'Foodies, road-trippers, history lovers'},
            {'label': 'Time needed', 'value': '1 hour stop en route'},
            {'label': 'Getting there', 'value': '30-min drive up the serpentine road from Kotor'},
            {'label': 'Region', 'value': 'Kotor Bay'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~30 km'},
        ],
        'good_for': ['foodies', 'road-trippers', 'history lovers'],
        'latitude': 42.4297,
        'longitude': 18.8283,
        'sections': [
            {
                'heading': 'Cradle of a dynasty',
                'body': 'Njeguši gave Montenegro its rulers. It was here in 1697 that Danilo Petrović became prince-bishop, founding the Petrović-Njegoš dynasty that would govern the country for more than two centuries, until 1918. The village’s two most famous sons bookend that story: Petar II Petrović-Njegoš, the poet and prince-bishop, born here in 1813, and Nikola I, Montenegro’s only king, born in the village in 1841. Njegoš’s modest birth house is preserved as a small museum, and the surrounding hamlets, scattered across a high green plateau, still carry the family and clan names that shaped the nation’s history.',
            },
            {
                'heading': 'The art of pršut and cheese',
                'body': 'Njeguši’s fame today rests on its larder. The village sits at a meteorological sweet spot where cold air spilling off Lovćen meets milder currents rising from the bay, creating conditions perfect for curing. Njeguški pršut, the local prosciutto, is lightly smoked over beech and then wind-dried for many months, developing a delicate, faintly smoky flavour; njeguški sir, a firm cow-and-sheep cheese, is matured and often kept in oil. The two are served together on wooden boards with olives, bread, honey and a shot of rakija at family konobas, where you can watch the hams hanging in the smokehouse and buy direct.',
            },
            {
                'heading': 'The serpentine and the views',
                'body': 'Reaching Njeguši is an event in itself. From Kotor, the old Austro-Hungarian road climbs the mountain wall in around twenty-five numbered hairpins, gaining some 900 m of altitude in a dizzying series of switchbacks, with laybys at almost every bend framing the entire Bay of Kotor spread out below. A favourite with cyclists and motorcyclists, the route continues past Njeguši up into Lovćen National Park and on to Cetinje. The parallel old caravan trail, the stepped ‘Ladder of Kotor’, once carried this same traffic on foot and mule before the carriage road was blasted into the cliff.',
            },
            {
                'heading': 'Visiting Njeguši',
                'body': 'Most travellers pause in Njeguši for an hour or so, midway through the classic Kotor–Lovćen–Cetinje loop. The essentials are simple: a tasting platter of ham and cheese at a village konoba — the long-running Kod Pera na Bukovicu is a local institution — a look at Njegoš’s birth house, and a stroll past the old stone church and cottages. Late spring through autumn is the ideal window, as snow and ice can make the serpentine slow going in winter. Pairing the stop with the Njegoš Mausoleum on Lovćen, just up the road, makes for one of the most rewarding half-days in the country.',
            },
        ],
        'external_links': [
            {'label': 'Njeguši on Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Njeguši'},
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    # ── Second wave: inland, northern and southern destinations ──────────────
    # The first twenty covered the coast and the headline national parks. These
    # fill the gaps a traveller actually searches for — the mountain towns, the
    # lake gateways, the monasteries and the far south.
    {
        'name': 'Kolašin',
        'region': 'durmitor',
        'place_type': 'mountains',
        'image': 'hiking.jpg',
        'featured': True,
        'summary': 'Montenegro’s mountain town — skiing in winter, rafting and forest walks in summer.',
        'description': 'At 954 m in the lap of Bjelasica, Kolašin is the country’s year-round mountain base: two ski centres above the town, Biogradska Gora’s rainforest on its doorstep, and the Tara and Morača canyons within an easy drive.',
        'highlights': [
            'Kolašin 1600 & 1450 ski centres',
            'Biogradska Gora old-growth forest',
            'Tara canyon rafting',
            'Katun dining on Bjelasica',
        ],
        'overview': 'Kolašin sits in a bowl between Bjelasica, Sinjajevina and the Morača massif, high enough that the air changes noticeably as you climb out of the Morača canyon to reach it. It grew as an Ottoman garrison town and later as a mountain-air resort, and today it works as the north’s most practical base: you can ski in the morning and be at a river put-in an hour later. Two lift systems serve it — Kolašin 1450 above the town and the newer Kolašin 1600 on the far side of the ridge — while summer brings hikers to Biogradska Gora, one of the last three old-growth forests left in Europe, wrapped around a glacial lake. The town itself is small and unpolished rather than resort-slick, which is much of its appeal; the eating is mountain food, and the shoulder seasons are quiet.',
        'faqs': [
            {
                'q': 'Is Kolašin worth visiting in summer?',
                'a': 'Yes — summer is arguably better than winter, with hiking on Bjelasica, the Biogradska Gora forest and lake, and Tara canyon rafting all within reach of the town.',
            },
            {
                'q': 'How far is Kolašin from Podgorica?',
                'a': 'About 70 km, roughly an hour and a quarter by car through the Morača canyon, and it is also on the Belgrade–Bar railway line.',
            },
            {
                'q': 'When can you ski in Kolašin?',
                'a': 'The season usually runs from December to March, with the most reliable snow in January and February at the higher Kolašin 1600 centre.',
            },
            {
                'q': 'What is Biogradska Gora?',
                'a': 'A national park just east of Kolašin protecting one of Europe’s last old-growth forests, centred on Biograd Lake, with easy lakeside walking and longer routes up Bjelasica.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'January–February for snow, June–September for hiking'},
            {'label': 'Ideal for', 'value': 'Skiers, hikers, families, rafting trips'},
            {'label': 'Time needed', 'value': '2–3 days'},
            {'label': 'Getting there', 'value': '~1h15 by car from Podgorica; also on the railway'},
            {'label': 'Region', 'value': 'Durmitor & the North'},
            {'label': 'Altitude', 'value': '954 m'},
        ],
        'good_for': ['skiing', 'hiking', 'families', 'rafting'],
        'latitude': 42.8222,
        'longitude': 19.5164,
        'sections': [
            {
                'heading': 'Two mountains, two seasons',
                'body': 'Bjelasica is a rounded, grassy range rather than a jagged one, which is why it works for both skiing and walking. Kolašin 1450 rises directly above the town and is the older, gentler of the two centres; Kolašin 1600, opened on the northern slopes, added modern gondola access and longer descents. In summer the same slopes turn into meadow walking dotted with katuns — the seasonal shepherds’ huts where families still move livestock up for the warm months, and where some now serve visitors cheese, kajmak, lamb and homemade rakija.',
            },
            {
                'heading': 'A base for the canyons',
                'body': 'Kolašin’s position makes it a launching point rather than a destination you never leave. The Tara — Europe’s deepest river canyon — is about an hour north, where rafting operators run half-day trips through the Đurđevića Tara section from spring meltwater into late summer. South, the road back to Podgorica threads the Morača canyon past the 13th-century Morača Monastery. Durmitor and Žabljak lie roughly two hours west over the Sinjajevina plateau.',
            },
        ],
        'external_links': [
            {'label': 'Biogradska Gora National Park', 'url': 'https://www.nparkovi.me'},
        ],
    },
    {
        'name': 'Virpazar',
        'region': 'skadar',
        'place_type': 'lakes',
        'image': 'kayak.jpg',
        'featured': True,
        'summary': 'The little stone gateway to Lake Skadar — boat trips, birds and Crmnica wine.',
        'description': 'A handful of bridges, a square and a few konobas sitting where the Crmnica river meets Lake Skadar. Virpazar is where almost every boat trip onto the largest lake in the Balkans begins.',
        'highlights': [
            'Boat trip onto Lake Skadar',
            'Pelican and heron birdwatching',
            'Crmnica wine tasting',
            'Lesendro fortress by the causeway',
        ],
        'overview': 'Virpazar is tiny — you can cross it in five minutes — but it is the hinge of the whole Lake Skadar experience. Boats leave from the quay all day for the lily-covered bays, drowned villages and island monasteries that make the lake worth the detour, and the surrounding Crmnica valley is Montenegro’s oldest wine district, planted overwhelmingly with the native Vranac grape. The lake itself straddles the Albanian border and is one of Europe’s most important bird reserves, with over 250 recorded species and one of the continent’s last nesting colonies of the Dalmatian pelican. The village makes an easy day trip from Podgorica or Budva, though staying a night lets you get onto the water at dawn, when the birds are active and the surface is glass.',
        'faqs': [
            {
                'q': 'What is there to do in Virpazar?',
                'a': 'Take a boat trip onto Lake Skadar, taste Vranac wine in the surrounding Crmnica villages, walk or cycle the lakeside tracks, and eat fresh lake fish in the village konobas.',
            },
            {
                'q': 'How long is a Lake Skadar boat trip?',
                'a': 'Most trips run two to three hours, taking in the water-lily bays and a monastery island; longer half-day options add swimming stops and quieter arms of the lake.',
            },
            {
                'q': 'When is the best time to see pelicans?',
                'a': 'Spring and early summer are best for birdlife generally; pelicans are most reliably seen on early-morning trips into the quieter northern reaches.',
            },
            {
                'q': 'How far is Virpazar from Podgorica?',
                'a': 'About 35 km, roughly 35–40 minutes by car, and it also has a stop on the Podgorica–Bar railway.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'April–June for birds and blossom, September for wine'},
            {'label': 'Ideal for', 'value': 'Boat trips, birdwatchers, wine tasting, kayaking'},
            {'label': 'Time needed', 'value': 'Half a day, or a night to catch dawn on the lake'},
            {'label': 'Getting there', 'value': '~35 min by car from Podgorica; train stop'},
            {'label': 'Region', 'value': 'Lake Skadar'},
            {'label': 'Lake', 'value': 'Largest in the Balkans; shared with Albania'},
        ],
        'good_for': ['birdwatching', 'boat trips', 'wine tasting', 'kayaking'],
        'latitude': 42.2422,
        'longitude': 19.0928,
        'sections': [
            {
                'heading': 'On the water',
                'body': 'The lake shifts character with the seasons. In late spring the shallow bays fill with white and yellow water lilies thick enough to slow a boat; by late summer the water drops and the channels narrow. Standard trips visit the lily fields, pass fishing hamlets and stop at one of the island monasteries — Kom, Beška or Starčevo — small Orthodox foundations that survived on islets when the mainland was unsafe. Kayaks are the quieter alternative and can be rented in the village for self-guided paddling along the shoreline.',
            },
            {
                'heading': 'Crmnica: Montenegro’s wine valley',
                'body': 'The slopes behind Virpazar form Crmnica, the country’s historic wine region and the heartland of Vranac — a dark, tannic native red that is Montenegro’s signature grape. Family cellars in villages such as Godinje and Boljevići still press small quantities and will pour for visitors, usually alongside smoked ham, cheese and olives. Godinje’s old stone houses were built with interconnected cellars and passages, a defensive quirk that makes wandering the village worth an hour on its own.',
            },
        ],
        'external_links': [
            {'label': 'Lake Skadar National Park', 'url': 'https://www.nparkovi.me'},
        ],
    },
    {
        'name': 'Petrovac',
        'region': 'budva',
        'place_type': 'coastal',
        'image': 'sailing.jpg',
        'featured': False,
        'summary': 'A calm, family-sized resort town with red-sand beaches and a Venetian fort.',
        'description': 'Smaller and gentler than Budva down the coast, Petrovac keeps a pine-backed promenade, two islets offshore, a compact Venetian fortress and some of the most swimmable beaches on the riviera.',
        'highlights': [
            'Petrovac town beach and promenade',
            'Lučice and Buljarica beaches',
            'Kastio fortress at sunset',
            'Boat trip to Katič and Sveta Nedjelja islets',
        ],
        'overview': 'Petrovac occupies a sheltered bay at the southern end of the Budva Riviera, where the hills come down to a reddish-pink shingle beach backed by pines and oleander. The Venetians fortified the bay in the 16th century to watch for pirates, and their small Kastio fort still sits on the southern headland with the best view over the water at dusk. The town has stayed low-rise and family-oriented, with an evening promenade rather than a club strip, which is precisely why many returning visitors prefer it to its louder neighbours. Two islets — Katič and the chapel-topped Sveta Nedjelja — sit just offshore, and a short walk south brings you to Lučice, a small cove many consider the prettiest beach on this stretch, and to the long undeveloped sweep of Buljarica.',
        'faqs': [
            {
                'q': 'Is Petrovac good for families?',
                'a': 'Yes — the bay is sheltered and shelves gently, the promenade is car-free in the evenings, and the town stays quieter than Budva or Bečići.',
            },
            {
                'q': 'What are the beaches like in Petrovac?',
                'a': 'The town beach is fine reddish shingle and sand backed by pines; Lučice is a small cove ten minutes south, and Buljarica is a long, largely undeveloped stretch beyond it.',
            },
            {
                'q': 'How far is Petrovac from Budva?',
                'a': 'About 17 km, roughly 20–25 minutes by car or a short ride on the coastal bus.',
            },
            {
                'q': 'What is the fortress in Petrovac?',
                'a': 'Kastio, a compact 16th-century Venetian fort on the southern headland, built to guard the bay against pirates and now a viewpoint with a summer bar.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June and September for warm sea without the crowds'},
            {'label': 'Ideal for', 'value': 'Families, couples, quieter beach days'},
            {'label': 'Time needed', 'value': '2–4 days'},
            {'label': 'Getting there', 'value': '~25 min by car from Budva; coastal bus'},
            {'label': 'Region', 'value': 'Budva Riviera'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~40 km'},
        ],
        'good_for': ['families', 'beaches', 'couples', 'swimming'],
        'latitude': 42.2058,
        'longitude': 18.9436,
        'sections': [
            {
                'heading': 'Three beaches, three moods',
                'body': 'Petrovac’s own beach is the sociable one — loungers, cafés and the promenade at its back. Lučice, over the headland to the south, is a compact horseshoe cove with clear water and a single restaurant, reachable on foot in about fifteen minutes along a coastal path. Buljarica, further on, is the opposite: a kilometre and a half of shingle with a marshy nature area behind it, almost entirely undeveloped, and the place locals go when the resorts fill up in August.',
            },
            {
                'heading': 'Roman floors and island chapels',
                'body': 'Petrovac was Lastva in Roman times, and two 3rd- and 4th-century mosaic floors survive near the centre, protected under cover. Offshore, the twin islets are a fixture of every photograph of the bay: Katič is bare rock, while Sveta Nedjelja carries a tiny chapel that local sailors are said to have built in thanks for surviving a wreck. Small boats run out to them in summer, and the swim from shore is a serious one best left to strong swimmers.',
            },
        ],
        'external_links': [
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Luštica Peninsula',
        'region': 'tivat',
        'place_type': 'coastal',
        'image': 'sailing.jpg',
        'featured': True,
        'summary': 'The bay’s wild edge — the Blue Cave, empty coves and olive terraces.',
        'description': 'The headland closing the Bay of Kotor keeps the coastline the resorts never reached: the Blue Cave, the pebble coves of Žanjic and Mirište, the fishing hamlet of Rose, and Mamula island offshore.',
        'highlights': [
            'Blue Cave swim stop',
            'Žanjic and Mirište beaches',
            'Rose village by boat from Herceg Novi',
            'Olive groves and stone hamlets inland',
        ],
        'overview': 'Luštica is the long limestone peninsula separating the Bay of Kotor from the open Adriatic, and it has stayed noticeably emptier than the coast on either side. Its interior is a plateau of olive terraces, drystone walls and small stone villages where the population thins to almost nothing in winter; its shoreline is a run of coves hard to reach by road and easy to reach by boat, which is why nearly every visitor arrives on the water. The headline stop is the Blue Cave, a sea cavern where light refracts to an intense blue and boats pause so passengers can swim. Around the point sit Žanjic and Mirište, shingle beaches with a handful of konobas, and the abandoned Austro-Hungarian fortress on Mamula island at the mouth of the bay.',
        'faqs': [
            {
                'q': 'How do you get to the Blue Cave in Montenegro?',
                'a': 'By boat — trips run from Herceg Novi, Kotor, Tivat and Budva, usually as a half-day taking in the cave, Mamula island and a beach stop.',
            },
            {
                'q': 'Can you drive around Luštica?',
                'a': 'Yes, a road crosses the peninsula to Rose and Radovići, but the best coves are steep or trackless to reach, so boats remain the easier way in.',
            },
            {
                'q': 'What is Mamula island?',
                'a': 'A 19th-century Austro-Hungarian island fortress at the mouth of the bay, used as a prison camp in the Second World War and since converted into a hotel.',
            },
            {
                'q': 'Are Luštica beaches sandy?',
                'a': 'Mostly pebble and shingle with very clear water — Žanjic and Mirište are the best known, and both have places to eat behind the beach.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'June–September, when the boats run'},
            {'label': 'Ideal for', 'value': 'Boat trips, swimming, quiet coves, sailing'},
            {'label': 'Time needed', 'value': 'A half-day by boat, longer if you stay'},
            {
                'label': 'Getting there',
                'value': 'Boat from Herceg Novi, Kotor or Tivat; road via Radovići',
            },
            {'label': 'Region', 'value': 'Tivat & Luštica'},
            {'label': 'Nearest airport', 'value': 'Tivat Airport (TIV), ~15 km'},
        ],
        'good_for': ['boat trips', 'swimming', 'sailing', 'quiet beaches'],
        'latitude': 42.3931,
        'longitude': 18.6417,
        'sections': [
            {
                'heading': 'The Blue Cave',
                'body': 'The cave sits on the peninsula’s open-sea flank, a wide-mouthed cavern where sunlight enters underwater and reflects off the pale floor, turning the pool an electric blue. Boats nose in and cut engines so people can swim; the effect is strongest in the middle of the day when the sun is high, and weakest under cloud. It is a short stop rather than a destination, which is why it is nearly always sold as part of a circuit with Mamula, Rose and a beach.',
            },
            {
                'heading': 'Rose and the inland hamlets',
                'body': 'Rose, at the peninsula’s northern tip, is a former fishing village facing Herceg Novi across the strait, reached by a short boat hop and lined with a few waterfront restaurants. Inland, villages such as Radovići, Krašići and Gošići preserve the old Luštica pattern of stone houses, cisterns and olive presses, with groves that still produce oil. A newer resort development at Luštica Bay has added marina and golf infrastructure on the eastern shore.',
            },
        ],
        'external_links': [
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Morača Monastery',
        'region': 'other',
        'place_type': 'cultural',
        'image': 'culture.jpg',
        'featured': False,
        'summary': 'A 13th-century monastery on the canyon road north, famous for its frescoes.',
        'description': 'Founded in 1252 on a terrace above the Morača river, this is one of the most important medieval Orthodox monuments in Montenegro — and the natural stop on the drive between Podgorica and the mountains.',
        'highlights': [
            'The Elijah fresco cycle',
            'Walled monastery courtyard and gardens',
            'Morača canyon viewpoints',
            'Easy stop on the Podgorica–Kolašin road',
        ],
        'overview': 'Morača Monastery was founded in 1252 by Stefan Vukanović Nemanjić, a prince of the Nemanjić dynasty, where the Morača canyon briefly widens into a green terrace. Its main church, dedicated to the Dormition of the Virgin, is a solid single-nave Raška-style building whose interior holds work from several centuries: fragments of the original 13th-century painting survive alongside a celebrated cycle of the prophet Elijah, and a major 16th- and 17th-century repainting carried out after the monastery was abandoned and stripped under Ottoman pressure. The complex — church, small chapel, cells and gardens inside a low wall — is still active, and because it sits directly on the main road north it is the one piece of medieval Montenegro most visitors actually see.',
        'faqs': [
            {
                'q': 'Where is Morača Monastery?',
                'a': 'On the main road between Podgorica and Kolašin, about 45 minutes north of Podgorica, on a terrace above the Morača river canyon.',
            },
            {
                'q': 'Can you visit Morača Monastery?',
                'a': 'Yes, it is an active monastery open to visitors during daylight hours, free to enter, with modest dress expected — shoulders and knees covered.',
            },
            {
                'q': 'What are the Morača frescoes?',
                'a': 'The most famous is a 13th-century cycle depicting the prophet Elijah, among the oldest surviving medieval wall paintings in the region, alongside later 16th–17th-century repainting.',
            },
            {
                'q': 'How long do you need at Morača?',
                'a': 'Thirty to forty-five minutes covers the church, chapel and gardens — most people fold it into a drive north to Kolašin or Žabljak.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'April–October; the road can be slow in winter'},
            {'label': 'Ideal for', 'value': 'History, architecture, road trips'},
            {'label': 'Time needed', 'value': '30–45 minutes'},
            {'label': 'Getting there', 'value': '~45 min by car north of Podgorica'},
            {'label': 'Region', 'value': 'Elsewhere in Montenegro'},
            {'label': 'Founded', 'value': '1252'},
        ],
        'good_for': ['history', 'architecture', 'road trips', 'photography'],
        'latitude': 42.7686,
        'longitude': 19.3936,
        'sections': [
            {
                'heading': 'What survives, and what was lost',
                'body': 'Morača’s history is a cycle of damage and repair. The monastery was plundered in the late 16th century and its lead roof stripped, after which it stood abandoned long enough for weather to destroy much of the original interior. Restoration in the 1570s brought new painters, and further campaigns followed in the 17th century, so the walls now read as layers rather than a single scheme. The Elijah cycle — the prophet fed by ravens, the ascent in the fiery chariot — is the work art historians travel for.',
            },
            {
                'heading': 'The canyon around it',
                'body': 'The Morača canyon is the corridor between Podgorica and the northern mountains, and the drive is a large part of the appeal: the road clings to the rock, tunnels through spurs and crosses the river repeatedly. Pull-offs give views down to the water, and in spring the flow is strong with snowmelt. Continuing north the road climbs to Kolašin and on toward Biogradska Gora, making the monastery a natural first stop on a day heading into the mountains.',
            },
        ],
        'external_links': [
            {
                'label': 'National Tourism Organisation of Montenegro',
                'url': 'https://www.montenegro.travel',
            },
        ],
    },
    {
        'name': 'Prokletije National Park',
        'region': 'other',
        'place_type': 'national_parks',
        'image': 'hiking.jpg',
        'featured': True,
        'summary': 'The Accursed Mountains — Montenegro’s highest, wildest and least-walked range.',
        'description': 'Alpine valleys, glacial springs and the country’s highest summits on the Albanian border. Grebaje and Ropojana are the two great valleys, and the Peaks of the Balkans trail runs through.',
        'highlights': [
            'Grebaje valley walls',
            'Ropojana valley and Oko Skakavice spring',
            'Zla Kolata, Montenegro’s highest peak',
            'Peaks of the Balkans long-distance trail',
        ],
        'overview': 'Prokletije — the Accursed Mountains — is the most alpine landscape in Montenegro and the least developed of its national parks, declared only in 2009. The range straddles the Albanian and Kosovan borders and contains the country’s highest ground, Zla Kolata at 2,534 m. Two valleys carry almost all the visitors: Grebaje, a short drive from Gusinje, ringed by near-vertical limestone walls that draw climbers, and Ropojana, which runs north toward the border past the Oko Skakavice spring, where water rises cold and startlingly clear. The base towns are Plav and Gusinje, both quiet, both with a strong Bosniak and Albanian cultural presence. The cross-border Peaks of the Balkans trail passes through, and infrastructure is genuinely limited — this is a place for people who want mountains rather than facilities.',
        'faqs': [
            {
                'q': 'Where is Prokletije National Park?',
                'a': 'In the far east of Montenegro on the Albanian border, reached through the towns of Plav and Gusinje, about three hours from Podgorica.',
            },
            {
                'q': 'What is the highest mountain in Montenegro?',
                'a': 'Zla Kolata, at 2,534 m, on the Albanian border within Prokletije.',
            },
            {
                'q': 'Do you need a guide to hike in Prokletije?',
                'a': 'For the valley walks no, but for high routes and border crossings a local guide is strongly advised — waymarking is patchy and weather changes fast.',
            },
            {
                'q': 'When can you hike Prokletije?',
                'a': 'Roughly late June to early October; snow lingers high into summer and huts operate only in season.',
            },
        ],
        'quick_facts': [
            {'label': 'Best time', 'value': 'Late June–early October'},
            {'label': 'Ideal for', 'value': 'Hikers, climbers, wild landscapes'},
            {'label': 'Time needed', 'value': '2–4 days'},
            {
                'label': 'Getting there',
                'value': '~3h by car from Podgorica via Andrijevica and Plav',
            },
            {'label': 'Region', 'value': 'Elsewhere in Montenegro'},
            {'label': 'Highest point', 'value': 'Zla Kolata, 2,534 m'},
        ],
        'good_for': ['hiking', 'climbing', 'photography', 'wild nature'],
        'latitude': 42.5064,
        'longitude': 19.8072,
        'sections': [
            {
                'heading': 'Grebaje and Ropojana',
                'body': 'Grebaje is the postcard valley: a flat meadow floor with a couple of small guesthouses, closed in by grey walls that rise more than a thousand metres and attract serious rock climbers. Ropojana is longer and emptier, running north from Gusinje toward the Albanian frontier past the Oko Skakavice — the “eye” — a spring pool fed from beneath the mountain. Both are drivable to their trailheads, which makes them unusually accessible entry points into otherwise demanding terrain.',
            },
            {
                'heading': 'Plav, Gusinje and the trail',
                'body': 'Plav sits on its own glacial lake below the range and, with Gusinje, forms the cultural gateway to the park — a corner of Montenegro with its own food, dialects and a long emigration history. The Peaks of the Balkans, a roughly 190 km circuit linking Montenegro, Albania and Kosovo, passes through here and has done more than anything to bring walkers back. Border-crossing permits are required for some sections and are arranged locally.',
            },
        ],
        'external_links': [
            {'label': 'National Parks of Montenegro', 'url': 'https://www.nparkovi.me'},
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed Montenegro destinations (Places). Idempotent.'

    def handle(self, *args, **opts):  # noqa: PLR0912 — flat per-field backfill
        from plugins.installed.booking_marketplace.models import Place

        created = existing = 0
        for i, p in enumerate(PLACES):
            slug = slugify(p['name'])
            place, was_created = Place.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': p['name'],
                    'region': p['region'],
                    'place_type': p['place_type'],
                    'summary': p['summary'],
                    'description': p['description'],
                    'highlights': p['highlights'],
                    'overview': p['overview'],
                    'faqs': p['faqs'],
                    'quick_facts': p['quick_facts'],
                    'good_for': p['good_for'],
                    'sections': p['sections'],
                    'external_links': p['external_links'],
                    'latitude': p['latitude'],
                    'longitude': p['longitude'],
                    'is_featured': p['featured'],
                    'sort_order': i,
                    'is_active': True,
                },
            )
            # Backfill fields on rows seeded before they existed. Never clobber
            # an existing (possibly admin-edited) value — only fill if empty.
            dirty = []
            if not place.place_type:
                place.place_type = p['place_type']
                dirty.append('place_type')
            if not place.highlights:
                place.highlights = p['highlights']
                dirty.append('highlights')
            if not place.overview:
                place.overview = p['overview']
                dirty.append('overview')
            if not place.faqs:
                place.faqs = p['faqs']
                dirty.append('faqs')
            if not place.quick_facts:
                place.quick_facts = p['quick_facts']
                dirty.append('quick_facts')
            if not place.good_for:
                place.good_for = p['good_for']
                dirty.append('good_for')
            if place.latitude is None:
                place.latitude = p['latitude']
                dirty.append('latitude')
            if place.longitude is None:
                place.longitude = p['longitude']
                dirty.append('longitude')
            if not place.sections:
                place.sections = p['sections']
                dirty.append('sections')
            if not place.external_links:
                place.external_links = p['external_links']
                dirty.append('external_links')
            if dirty:
                place.save(update_fields=dirty)
            if not place.image:
                src = SEED_DIR / p['image']
                if src.exists():
                    with src.open('rb') as fh:
                        place.image.save(f'{slug}.jpg', File(fh), save=True)
            created += was_created
            existing += not was_created
        self.stdout.write(
            self.style.SUCCESS(
                f'Places seeded: {created} created, {existing} already present '
                f'({Place.objects.count()} total).'
            )
        )
