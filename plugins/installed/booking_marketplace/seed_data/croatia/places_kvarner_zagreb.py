"""Croatia seed data: places of Kvarner and Zagreb.

Eighteen destination guides for `seed_croatia`: Rijeka, Opatija, Lovran, Učka, Risnjak,
the islands of Krk, Cres, Lošinj and Rab, the Kvarner coast, and Zagreb with its
surroundings. Facts only: no prices, opening hours or ratings.
"""

from __future__ import annotations

PLACES: list[dict] = [
    {
        'name': 'Rijeka',
        'slug': 'rijeka',
        'region': 'kvarner',
        'place_type': 'cities',
        'featured': False,
        'summary': (
            'Croatia’s main port city on the Kvarner Bay, with a lively Korzo, Trsat '
            'Castle and a carnival tradition.'
        ),
        'description': (
            'Rijeka is a working port and Croatia’s third-largest city, set between '
            'the Kvarner Bay and the hills behind it. Its centre has a pedestrian '
            'Korzo, a City Clock Tower and a covered market, while Trsat Castle '
            'looks down over the Rječina canyon. Rijeka shared the European Capital '
            'of Culture title in 2020.'
        ),
        'highlights': [
            'The Korzo and the City Clock Tower',
            'Trsat Castle and the Our Lady of Trsat shrine',
            'Cathedral of St Vitus',
            'Museum of Modern and Contemporary Art (MMSU)',
            'Rijeka Carnival',
        ],
        'overview': (
            'Rijeka grew around its harbour, and the port still shapes the city: '
            'cranes, shipyards and ferries sit beside a centre of Austro-Hungarian-era '
            'façades. The Korzo, a pedestrian promenade, runs through the middle of '
            'town and ends near the City Clock Tower, a landmark of the old centre. A '
            'short climb above the city, Trsat Castle and the Our Lady of Trsat shrine '
            'give a view over the Rječina canyon and the Bay of Kvarner. Rijeka is '
            'better known for working life than for resort tourism, which suits '
            'visitors who like markets, museums, cafés and a local feel. The city '
            'holds a large carnival each year before Lent, and in 2020 it was a '
            'European Capital of Culture. It is also a practical hub: ferries and '
            'buses run from here to the Kvarner islands, Istria and the coast.'
        ),
        'faqs': [
            {
                'q': 'Is Rijeka worth visiting?',
                'a': (
                    'Yes, for travellers who like a working port city with a walkable centre, '
                    'Trsat Castle, museums and a local atmosphere. It is also a convenient '
                    'base for Opatija, the Kvarner islands and Risnjak National Park.'
                ),
            },
            {
                'q': 'How do I get to Rijeka?',
                'a': (
                    'Rijeka Airport (RJK) is on the island of Krk and is linked to the '
                    'mainland by the Krk Bridge. The city also has road and bus connections '
                    'to Zagreb and Istria, and ferry links to the islands.'
                ),
            },
            {
                'q': 'What is there to do in Rijeka?',
                'a': (
                    'Walk the Korzo to the City Clock Tower, climb to Trsat Castle, visit the '
                    'cathedral and the museums, and browse the central market. Day trips to '
                    'Opatija and the islands are easy to arrange.'
                ),
            },
            {
                'q': 'How long should I spend in Rijeka?',
                'a': (
                    'One full day covers the centre and Trsat. Many travellers stay two or '
                    'three nights and use the city as a base for the Kvarner coast.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and autumn for city walking; Carnival season before Lent',
            },
            {
                'label': 'Ideal for',
                'value': 'City breaks, culture, ferry connections',
            },
            {
                'label': 'Time needed',
                'value': 'One day to a weekend',
            },
            {
                'label': 'Getting there',
                'value': 'Road and bus links to Zagreb and Istria; ferries to the islands',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'city breaks',
            'culture lovers',
            'ferry connections',
            'foodies',
            'day-trip base',
        ],
        'sections': [
            {
                'heading': 'A port city',
                'body': (
                    'Rijeka has been a port for centuries, and under Habsburg rule it '
                    'became the main outlet to the sea for much of Central Europe. That '
                    'history is visible in the grand façades around the Korzo and in the '
                    'harbour that still works today. The city’s industrial past is also '
                    'part of its identity: the first self-propelled torpedo was developed '
                    'here in the 1860s, and the former torpedo launch station can still be '
                    'seen on the waterfront.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'Start on the Korzo and the City Clock Tower, then visit the Cathedral '
                    'of St Vitus and the central market hall. Above the centre, Trsat '
                    'Castle and the Our Lady of Trsat shrine are reached by a long flight '
                    'of steps or by road, and they overlook the Rječina canyon and the '
                    'bay. The Museum of Modern and Contemporary Art (MMSU) and the city’s '
                    'theatre and galleries add a cultural side to a visit.'
                ),
            },
            {
                'heading': 'A base for Kvarner',
                'body': (
                    'Rijeka is the main transport centre of the Kvarner region. Opatija '
                    'and Lovran lie along the coast to the west, Crikvenica and Senj to '
                    'the south-east, and the islands of Krk, Cres, Lošinj and Rab are '
                    'reached by road and ferry. Risnjak National Park in Gorski kotar is a '
                    'day trip inland, and Učka Nature Park rises behind the coast to the '
                    'west.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Rijeka — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Rijeka',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.3271,
        'longitude': 14.4422,
    },
    {
        'name': 'Opatija',
        'slug': 'opatija',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': True,
        'summary': (
            'A Habsburg-era seaside resort on the Kvarner Bay, known for its villas, '
            'parks and the Lungomare promenade.'
        ),
        'description': (
            'Opatija became a fashionable seaside resort in the 19th century, and '
            'the villas, hotels and parks from that period still line its shore. '
            'The Lungomare, a coastal promenade, links the town with Volosko to the '
            'north-west and Lovran to the south-east, with Učka mountain rising '
            'behind.'
        ),
        'highlights': [
            'The Lungomare coastal promenade',
            'Villa Angiolina and its park',
            'The Maiden with the Seagull statue',
            'Church of St James',
            'Volosko harbour',
        ],
        'overview': (
            'Opatija began its rise as a resort in the 1840s, when the Rijeka merchant '
            'Iginio Scarpa built Villa Angiolina and planted its gardens. Later the '
            'Southern Railway and Habsburg court society brought visitors, and the '
            'town filled with villas and hotels in a mix of historicist and Secession '
            'styles. Many of them still stand along the shore and in the parks behind '
            'it. The Lungomare, a seaside path that follows the coast for about twelve '
            'kilometres from Volosko to Lovran, is the natural way to see the town on '
            'foot, with small coves, rocks and swimming spots along the way. The '
            'statue of the Maiden with the Seagull on a rock by the shore is a local '
            'emblem. Behind Opatija, the wooded slopes of Učka Nature Park offer '
            'hiking and views over the bay.'
        ),
        'faqs': [
            {
                'q': 'Is Opatija worth visiting?',
                'a': (
                    'Yes, if you enjoy a seaside walk, historic villas and parks and a calmer '
                    'resort than the busiest parts of the coast. It also works well as a base '
                    'for Rijeka, Učka and the Kvarner islands.'
                ),
            },
            {
                'q': 'How do I get to Opatija?',
                'a': (
                    'Opatija is a short drive from Rijeka, and local buses connect the two. '
                    'The nearest airport is Rijeka Airport (RJK) on the island of Krk, '
                    'reached over the Krk Bridge. Zagreb is a few hours away by road.'
                ),
            },
            {
                'q': 'What is there to do in Opatija?',
                'a': (
                    'Walk the Lungomare, visit Villa Angiolina and its park, see the Maiden '
                    'with the Seagull statue, swim from the rocks and coves along the shore, '
                    'and take a day trip into Učka Nature Park.'
                ),
            },
            {
                'q': 'How long should I spend in Opatija?',
                'a': (
                    'A day is enough for the promenade and the main sights. Two to four '
                    'nights suit travellers who want to swim, hike on Učka and visit Rijeka '
                    'and the islands.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn for swimming; shoulder seasons for walking',
            },
            {
                'label': 'Ideal for',
                'value': 'Seaside walks, villas and parks, calm holidays',
            },
            {
                'label': 'Time needed',
                'value': '1–3 days',
            },
            {
                'label': 'Getting there',
                'value': 'Short drive or bus from Rijeka; Zagreb a few hours by road',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'seaside walks',
            'architecture lovers',
            'couples',
            'hikers',
            'relaxed holidays',
        ],
        'sections': [
            {
                'heading': 'The birth of a resort',
                'body': (
                    'Villa Angiolina, built in the 1840s for the Rijeka merchant Iginio '
                    'Scarpa, is usually named as the start of Opatija’s tourism. Once the '
                    'railway reached the region, the town grew quickly and attracted '
                    'visitors from across the Habsburg lands. The villas, hotels and '
                    'landscaped parks of that era give the town its character, and the '
                    'Church of St James, part of the old abbey that gave the town its '
                    'name, stands in the centre.'
                ),
            },
            {
                'heading': 'The Lungomare',
                'body': (
                    'The Lungomare is a seaside path of about twelve kilometres that runs '
                    'from Volosko through Opatija to Lovran. It is mostly flat, passes '
                    'small beaches, rocky bathing places and villas, and can be walked in '
                    'sections. Volosko, at the northern end, is a small fishing harbour '
                    'with a village feel, and Lovran at the southern end has a well-kept '
                    'old town.'
                ),
            },
            {
                'heading': 'Beyond the shore',
                'body': (
                    'Behind Opatija, the slopes of Učka rise steeply, and Učka Nature Park '
                    'has marked hiking trails and viewpoints. Rijeka is close enough for a '
                    'day trip to Trsat Castle and the museums, and the Kvarner islands of '
                    'Krk, Cres and Lošinj are reached by road and ferry. Many visitors '
                    'combine the resort with trips along the coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Opatija — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Opatija',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.3377,
        'longitude': 14.305,
    },
    {
        'name': 'Lovran',
        'slug': 'lovran',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small seaside town at the foot of Učka, with a walled old town, a pebble '
            'shore and the Lungomare path to Opatija.'
        ),
        'description': (
            'Lovran is a small town on the Kvarner Bay at the foot of Mount Učka, '
            'at the south-eastern end of the Lungomare path from Opatija. Its old '
            'town has narrow lanes, a medieval church and parts of the town walls, '
            'and it is known for its chestnuts, celebrated each autumn.'
        ),
        'highlights': [
            'The old town and its lanes',
            'Church of St George',
            'The Lungomare path to Opatija',
            'Seaside villas and parks',
            'The Marunada chestnut festival',
        ],
        'overview': (
            'Lovran lies on a narrow strip of coast between the sea and the steep, '
            'forested slopes of Učka. The old town keeps its medieval layout of narrow '
            'stepped lanes, small squares and parts of the town walls, with the parish '
            'Church of St George among its main sights. Along the shore, 19th-century '
            'villas and landscaped parks reflect the same resort era as nearby '
            'Opatija, and the Lungomare path links the two towns along the water. The '
            'surrounding hills are known for chestnuts, and Lovran holds an autumn '
            'festival called the Marunada in their honour. Lovran is quieter than '
            'Opatija and suits visitors who want a small town with a harbour, a pebble '
            'shore and easy access to walking trails on Učka.'
        ),
        'faqs': [
            {
                'q': 'Is Lovran worth visiting?',
                'a': (
                    'Yes, for a quiet seaside town with a compact old town and easy walks. It '
                    'is a calmer alternative to Opatija, which is a short walk or drive along '
                    'the coast.'
                ),
            },
            {
                'q': 'How do I get to Lovran?',
                'a': (
                    'Lovran is on the coastal road south-east of Opatija, and buses link it '
                    'with Opatija and Rijeka. The nearest airport is Rijeka Airport (RJK) on '
                    'Krk, reached over the Krk Bridge.'
                ),
            },
            {
                'q': 'What is there to do in Lovran?',
                'a': (
                    'Explore the old town, walk the Lungomare towards Opatija, swim from the '
                    'town’s beaches, and hike on Učka. In autumn the Marunada festival '
                    'celebrates local chestnuts.'
                ),
            },
            {
                'q': 'How long should I spend in Lovran?',
                'a': (
                    'A half day covers the old town and a stretch of the Lungomare. Staying a '
                    'night or two works well if you want to hike on Učka as well.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; October for the Marunada festival',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet seaside stays, walking, small-town atmosphere',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to 2 days',
            },
            {
                'label': 'Getting there',
                'value': 'Coastal road and bus from Opatija and Rijeka',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'quiet holidays',
            'walkers',
            'couples',
            'history lovers',
            'autumn visits',
        ],
        'sections': [
            {
                'heading': 'The old town',
                'body': (
                    'Lovran’s old town sits just above the sea, with narrow lanes that '
                    'climb in steps and small squares between old stone houses. Parts of '
                    'the medieval town walls remain, and the Church of St George is one of '
                    'the main landmarks. The compact size makes it easy to see on a short '
                    'walk, and the sea is always close, with the harbour and the shore '
                    'only a few minutes away.'
                ),
            },
            {
                'heading': 'Villas and the shore',
                'body': (
                    'Like Opatija, Lovran grew as a resort in the late 19th century, and '
                    'villas with gardens and parks line the shoreline. A paved path runs '
                    'along the water, and the Lungomare continues north-west to Opatija. '
                    'The beaches here are mostly pebble and rock, with steps and platforms '
                    'into the sea, which is typical for this stretch of the Kvarner coast.'
                ),
            },
            {
                'heading': 'Chestnuts and Učka',
                'body': (
                    'The slopes above Lovran are known for sweet chestnuts, called marun '
                    'in the local dialect. Each autumn the town hosts the Marunada, a '
                    'festival built around them. Behind the town, Učka Nature Park has '
                    'marked trails to viewpoints with long views over the bay, and the old '
                    'villages on its slopes are a pleasant drive or walk from the coast.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Lovran — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Lovran',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.2917,
        'longitude': 14.2731,
    },
    {
        'name': 'Učka Nature Park',
        'slug': 'ucka-nature-park',
        'region': 'kvarner',
        'place_type': 'mountains',
        'featured': False,
        'summary': (
            'A mountain range behind the Kvarner coast with marked trails, Vojak peak '
            'and wide views over the bay and Istria.'
        ),
        'description': (
            'Učka Nature Park covers the mountain range that rises between Istria '
            'and the Kvarner Bay. Its highest peak, Vojak, reaches about 1,400 '
            'metres and gives views over the bay, the islands and the Istrian '
            'interior. Marked trails and old villages on the slopes make it a '
            'popular day out from Opatija and Lovran.'
        ),
        'highlights': [
            'Vojak, the highest peak',
            'Viewpoints over the Kvarner Bay',
            'Marked hiking trails',
            'Beech and chestnut forests',
            'Villages on the slopes',
        ],
        'overview': (
            'Učka is a long limestone ridge that separates the Kvarner coast from the '
            'Istrian interior. It was declared a nature park in 1999. The highest '
            'point, Vojak at 1,401 metres, has a lookout tower and a view that covers '
            'the Kvarner Bay and its islands, and on clear days reaches across Istria. '
            'The lower slopes carry chestnut and oak woods, while beech forest grows '
            'higher up, and above the tree line there are open meadows and rocky '
            'ground. Marked hiking and cycling routes start from villages on the '
            'slopes and from the coastal towns of Lovran, Mošćenice and Opatija. The '
            'park is reached by road over the Učka pass, and the long tunnel under the '
            'ridge carries the main road between Rijeka and Istria.'
        ),
        'faqs': [
            {
                'q': 'Is Učka Nature Park worth visiting?',
                'a': (
                    'Yes, if you enjoy hiking, forest and wide views. The summit area is an '
                    'easy half-day trip from Opatija or Lovran, and longer routes climb from '
                    'the coast.'
                ),
            },
            {
                'q': 'How do I get to Učka Nature Park?',
                'a': (
                    'The easiest way is by car on the road up to the Vojak area from the Učka '
                    'pass or from the coastal side. Trails also climb from Lovran, Mošćenice '
                    'and other villages. Rijeka Airport (RJK) on Krk is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Učka Nature Park?',
                'a': (
                    'Hike the marked trails, walk to the lookout on Vojak, cycle the mountain '
                    'roads, and visit the old villages on the slopes. Views over the bay are '
                    'the main reward.'
                ),
            },
            {
                'q': 'How long should I spend in Učka Nature Park?',
                'a': (
                    'A few hours cover the summit area by car. A full day suits a hike up '
                    'from the coast. The weather can change quickly, so bring layers.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'May to October for hiking; clear days for views',
            },
            {
                'label': 'Ideal for',
                'value': 'Hiking, cycling, viewpoints, forest walks',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a full day',
            },
            {
                'label': 'Getting there',
                'value': 'By car over the Učka pass or from Lovran and Opatija',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'hikers',
            'cyclists',
            'nature lovers',
            'photographers',
            'families with older children',
        ],
        'sections': [
            {
                'heading': 'The mountain',
                'body': (
                    'Učka is a long ridge that drops steeply on its seaward side. The park '
                    'was declared in 1999 and includes the main ridge and parts of its '
                    'slopes. Vojak, at 1,401 metres, is the highest point. The ridge forms '
                    'a clear divide between the green Istrian interior and the Kvarner '
                    'Bay, and the climate and vegetation change quickly with altitude, '
                    'from coastal woodland to mountain beech forest.'
                ),
            },
            {
                'heading': 'Trails and views',
                'body': (
                    'Marked trails climb to Vojak and other viewpoints, some starting from '
                    'Lovran, Mošćenice and the villages below the ridge. The lookout tower '
                    'on Vojak gives a wide view of the bay and its islands, and on clear '
                    'days across Istria. Weather on the ridge is often cooler and windier '
                    'than on the coast, so bring a layer even in summer.'
                ),
            },
            {
                'heading': 'Villages on the slopes',
                'body': (
                    'Old villages sit on the slopes of Učka, with stone houses and small '
                    'churches reached by narrow roads. Mošćenice is a hilltop village '
                    'above the coast, and Lovran lies at the foot of the mountain. '
                    'Combining a hike or a drive on Učka with a swim and a meal on the '
                    'coast is a typical day in this part of Kvarner.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Učka — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/U%C4%8Dka',
            },
            {
                'label': 'Učka Nature Park',
                'url': 'https://pp-ucka.hr/',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.2833,
        'longitude': 14.2,
    },
    {
        'name': 'Risnjak National Park',
        'slug': 'risnjak-national-park',
        'region': 'kvarner',
        'place_type': 'national_parks',
        'featured': False,
        'summary': (
            'A forested national park in Gorski kotar, with the source of the Kupa '
            'river, karst peaks and lynx country.'
        ),
        'description': (
            'Risnjak National Park protects forested mountains in Gorski kotar, '
            'inland from Rijeka. It is named after the lynx (ris) and the peak of '
            'Veliki Risnjak, at about 1,500 metres, and it holds the spring of the '
            'Kupa river. Trails range from short educational walks to a long '
            'mountain climb.'
        ),
        'highlights': [
            'The source of the Kupa river',
            'Veliki Risnjak peak',
            'The Leska educational trail',
            'Dense beech and fir forest',
            'Wildlife including lynx, bears and wolves',
        ],
        'overview': (
            'Risnjak lies in Gorski kotar, the wooded highland between the Kvarner '
            'coast and continental Croatia. It was declared a national park in 1953 '
            'and is dominated by karst limestone, deep forest of beech and fir, and a '
            'few high peaks. The best-known of these, Veliki Risnjak at 1,528 metres, '
            'gives the park its name, which comes from the Croatian word for lynx, '
            'ris. The Kupa river rises here, at a spring in a rocky basin near the '
            'village of Razloge, and flows on towards the Sava. The park visitor '
            'centre is in Crni Lug, and from there trails lead to the Kupa spring, the '
            'Leska educational trail and the climb to Veliki Risnjak. The park is a '
            'quieter, cooler counterpart to the nearby coast and is best visited in '
            'the warmer months.'
        ),
        'faqs': [
            {
                'q': 'Is Risnjak National Park worth visiting?',
                'a': (
                    'Yes, if you want forest, mountain walking and quiet. It contrasts with '
                    'the Kvarner coast, and can be reached from Rijeka in a day trip.'
                ),
            },
            {
                'q': 'How do I get to Risnjak National Park?',
                'a': (
                    'The visitor centre is in Crni Lug in Gorski kotar and is reached by road '
                    'from Rijeka, Delnice or Zagreb. The nearest airport is Rijeka Airport '
                    '(RJK) on Krk. A car is the simplest way to arrive.'
                ),
            },
            {
                'q': 'What is there to do in Risnjak National Park?',
                'a': (
                    'Walk to the source of the Kupa, follow the Leska educational trail, '
                    'climb Veliki Risnjak if you are an experienced hiker, and look for '
                    'wildlife signs in the forest.'
                ),
            },
            {
                'q': 'How long should I spend in Risnjak National Park?',
                'a': (
                    'A few hours cover the short trails near Crni Lug. The climb to Veliki '
                    'Risnjak takes most of a day, so start early and check the weather.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; snow can close high trails in winter',
            },
            {
                'label': 'Ideal for',
                'value': 'Forest walks, hiking, wildlife, quiet nature',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a full day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Rijeka, Delnice or Zagreb; a car is the easiest way',
            },
            {
                'label': 'Region',
                'value': 'Kvarner (Gorski kotar)',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'hikers',
            'nature lovers',
            'families',
            'photographers',
            'quiet getaways',
        ],
        'sections': [
            {
                'heading': 'Forest and karst',
                'body': (
                    'Risnjak National Park was declared in 1953 and covers the forested '
                    'mountains of Gorski kotar. The ground is karst limestone, so water '
                    'often vanishes underground and reappears at springs. Beech and fir '
                    'forest covers much of the park, with meadows and rocky ground higher '
                    'up. The area is cooler and wetter than the nearby coast, and winters '
                    'bring snow, which can close the high trails.'
                ),
            },
            {
                'heading': 'The Kupa spring',
                'body': (
                    'The Kupa river rises in the park, from a spring in a rocky basin near '
                    'Razloge, and then flows out of the mountains towards the Sava. The '
                    'spring can be reached on foot from the Crni Lug area, along a signed '
                    'route through the forest. The Leska educational trail, a shorter '
                    'loop, introduces the park’s forest, rocks and wildlife with '
                    'information boards along the way.'
                ),
            },
            {
                'heading': 'Veliki Risnjak',
                'body': (
                    'Veliki Risnjak, at 1,528 metres, is the park’s main peak, and the '
                    'climb is a demanding full-day walk on marked trails. The park is home '
                    'to large animals such as brown bears, wolves and lynx, which are shy '
                    'and rarely seen. Visitors should keep to marked trails, carry water '
                    'and layers, and check weather conditions before setting out on the '
                    'higher routes.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Risnjak National Park — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Risnjak%20National%20Park',
            },
            {
                'label': 'Risnjak National Park',
                'url': 'https://np-risnjak.hr/',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.415,
        'longitude': 14.71,
    },
    {
        'name': 'Krk',
        'slug': 'krk',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'The walled town of Krk on the island of the same name, connected to the '
            'mainland by a bridge.'
        ),
        'description': (
            'Krk is the main town of the island of the same name, one of the '
            'largest in the Adriatic and linked to the mainland by the Krk Bridge. '
            'The walled old town has a Romanesque cathedral, the Frankopan Castle '
            'and a harbour front, and beaches and villages lie around the island.'
        ),
        'highlights': [
            'The Cathedral of the Assumption',
            'Frankopan Castle',
            'The old town walls and gates',
            'The harbour promenade',
            'Beaches and villages around the island',
        ],
        'overview': (
            'The island of Krk lies in the northern Adriatic and is joined to the '
            'mainland by the Krk Bridge, so it can be reached by road without a ferry. '
            'Krk town, on the island’s western side, has been a settlement since Roman '
            'times. Its old centre is enclosed by walls and keeps the Cathedral of the '
            'Assumption, a Romanesque church with later additions, and the Frankopan '
            'Castle by the sea, named for the noble family that ruled the island in '
            'the Middle Ages. Narrow lanes, small squares and a harbour front give it '
            'a compact, walkable feel. Elsewhere on the island you find Baška, a long '
            'beach resort at the southern end, the hill town of Vrbnik, and several '
            'smaller coastal villages. Rijeka Airport, the main airport for the '
            'Kvarner region, is on the island.'
        ),
        'faqs': [
            {
                'q': 'Is Krk worth visiting?',
                'a': (
                    'Yes, for a walkable old town by the sea combined with beaches and '
                    'villages across the island. It is easy to reach by road from Rijeka and '
                    'does not need a ferry.'
                ),
            },
            {
                'q': 'How do I get to Krk?',
                'a': (
                    'Krk is connected to the mainland by the Krk Bridge. Rijeka Airport (RJK) '
                    'is on the island, and buses and cars come over the bridge from Rijeka. '
                    'Zagreb is a few hours away by road.'
                ),
            },
            {
                'q': 'What is there to do in Krk?',
                'a': (
                    'Walk the old town and its walls, visit the cathedral and Frankopan '
                    'Castle, sit on the harbour front, swim at the town beaches, and explore '
                    'Baška and Vrbnik by car.'
                ),
            },
            {
                'q': 'How long should I spend in Krk?',
                'a': (
                    'A half day covers the town. Staying several days lets you add Baška, '
                    'Vrbnik and the island’s beaches.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Old-town walks, beaches, island driving',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to several days',
            },
            {
                'label': 'Getting there',
                'value': 'Road over the Krk Bridge; Rijeka Airport is on the island',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), on the island of Krk',
            },
        ],
        'good_for': [
            'old-town lovers',
            'beach holidays',
            'road trips',
            'families',
            'couples',
        ],
        'sections': [
            {
                'heading': 'An island town',
                'body': (
                    'Krk is the main town of the island of Krk, whose Latin name was '
                    'Curicta. The island was a Roman settlement and later passed to the '
                    'Frankopan counts and then to Venice, and traces of all these periods '
                    'remain in the town. The old centre sits on a small rise by the sea, '
                    'and walls and gates still mark its outline. The island itself is '
                    'reached by the Krk Bridge, which opened in 1980.'
                ),
            },
            {
                'heading': 'What to see',
                'body': (
                    'The Cathedral of the Assumption is the main landmark, a Romanesque '
                    'church that has been added to over the centuries. Beside the sea, the '
                    'Frankopan Castle faces the harbour and is used for events and '
                    'exhibitions. The town walls, gates and narrow lanes can be seen on a '
                    'short walk, and the harbour front has cafés and restaurants. Town '
                    'beaches lie within a few minutes of the centre.'
                ),
            },
            {
                'heading': 'Around the island',
                'body': (
                    'Baška, with its long pebble beach, lies at the southern end of Krk, '
                    'and Vrbnik, a hill town known for wine, sits on the eastern coast. '
                    'The island has many smaller villages, coves and viewpoints that are '
                    'easiest to see by car. Rijeka and the Kvarner coast are close, and '
                    'ferries from Valbiska on the island reach Cres.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Krk island — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Krk',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.0273,
        'longitude': 14.5753,
    },
    {
        'name': 'Baška',
        'slug': 'baska',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A beach resort at the southern end of Krk, with a long pebble beach below '
            'the hills and a Glagolitic heritage.'
        ),
        'description': (
            'Baška lies at the southern end of the island of Krk, in a bay beneath '
            'bare limestone hills. Its long pebble beach, Vela plaža, is its main '
            'draw, and the village is also known for the Baška tablet, an early '
            'Glagolitic inscription found nearby in the church at Jurandvor.'
        ),
        'highlights': [
            'Vela plaža, the main beach',
            'The old village lanes',
            'Walks in the hills above the bay',
            'The Baška tablet at Jurandvor',
            'Views towards the island of Prvić',
        ],
        'overview': (
            'Baška sits in a wide bay at the southern tip of Krk, sheltered by stony '
            'hills. Its main beach, Vela plaža, is a long curve of pebbles along the '
            'bay, with a promenade behind it and the hill of Obzova rising to one '
            'side. Behind the seafront, the old part of the village has narrow lanes '
            'and stone houses. Baška is closely tied to Croatian written culture: the '
            'Baška tablet, an inscription carved in the Glagolitic script around the '
            'year 1100, was found at the church of St Lucy in nearby Jurandvor. The '
            'original is kept in Zagreb, and a copy is shown in the church. The bay is '
            'popular for swimming and walking, and the village is easy to combine with '
            'a visit to Krk town and Vrbnik.'
        ),
        'faqs': [
            {
                'q': 'Is Baška worth visiting?',
                'a': (
                    'Yes, if you want a long pebble beach, a simple seaside village and '
                    'walking in the hills. It is also a good place to learn about early '
                    'Croatian writing.'
                ),
            },
            {
                'q': 'How do I get to Baška?',
                'a': (
                    'Baška is at the southern end of Krk, reached by road over the Krk Bridge '
                    'and across the island. Rijeka Airport (RJK) is on the island. Buses link '
                    'Baška with Krk town and Rijeka.'
                ),
            },
            {
                'q': 'What is there to do in Baška?',
                'a': (
                    'Swim and walk along Vela plaža, explore the old village, hike in the '
                    'hills, and visit Jurandvor to see the Baška tablet replica in the Church '
                    'of St Lucy.'
                ),
            },
            {
                'q': 'How long should I spend in Baška?',
                'a': (
                    'A day suits a beach visit with a walk. A stay of several days works for '
                    'a seaside holiday with trips to Krk town and Vrbnik.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Beach holidays, walking, island trips',
            },
            {
                'label': 'Time needed',
                'value': 'A day to a week',
            },
            {
                'label': 'Getting there',
                'value': 'By road across Krk; buses from Krk town and Rijeka',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), on the island of Krk',
            },
        ],
        'good_for': [
            'beach holidays',
            'families',
            'walkers',
            'history lovers',
            'seaside stays',
        ],
        'sections': [
            {
                'heading': 'The bay and its beach',
                'body': (
                    'Baška lies at the end of a long bay, with the village at one side and '
                    'bare limestone hills behind it. Vela plaža, the main beach, is a long '
                    'pebble shore with a promenade, cafés and sea access along its length. '
                    'The water is clear and the setting is open, with views across the sea '
                    'towards the island of Prvić. Smaller beaches and coves lie further '
                    'along the coast.'
                ),
            },
            {
                'heading': 'The Baška tablet',
                'body': (
                    'The Baška tablet is a stone slab carved in the Glagolitic script, '
                    'dated to about the year 1100, and is one of the earliest known '
                    'inscriptions in the Croatian language. It was found in the church of '
                    'St Lucy at Jurandvor, just outside Baška. The original is kept in the '
                    'Croatian Academy of Sciences and Arts in Zagreb, and a replica is '
                    'displayed in the church, where visitors can learn about the script.'
                ),
            },
            {
                'heading': 'Walks and day trips',
                'body': (
                    'The hills behind Baška have walking paths with views over the bay, '
                    'and the old village is pleasant to walk through in the evening. Krk '
                    'town is a drive away across the island, and Vrbnik, a hill town known '
                    'for its wine, lies on the east coast. Ferries and boats link the area '
                    'with neighbouring islands in season.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.9667,
        'longitude': 14.75,
    },
    {
        'name': 'Vrbnik',
        'slug': 'vrbnik',
        'region': 'kvarner',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A small town on a cliff above the sea on Krk, known for Glagolitic '
            'heritage, narrow lanes and Žlahtina wine.'
        ),
        'description': (
            'Vrbnik stands on a rocky cliff above the sea on the east coast of Krk. '
            'Its old centre has narrow stone lanes, a Glagolitic heritage and a '
            'wine tradition built on the local white grape Žlahtina. The town sits '
            'above a fertile valley of vineyards.'
        ),
        'highlights': [
            'The narrow lanes of the old town',
            'The Klančić alley',
            'Žlahtina wine and tasting',
            'Views from the cliff edge',
            'The Glagolitic heritage',
        ],
        'overview': (
            'Vrbnik is a small town built on a cliff high above the sea on the east '
            'coast of Krk. The old centre has stone houses, steep lanes and small '
            'squares, and one of its alleys, Klančić, is very narrow. The town has a '
            'long Glagolitic tradition, and the Vrbnik Statute, written in the '
            'Glagolitic script in 1388, is an important document of local law. The '
            'Vrbnik valley below the town is planted with vines, and the local white '
            'wine, Žlahtina, made from an indigenous grape, is the island’s best-known '
            'product and is served in the town’s wine cellars and restaurants. From '
            'the cliff edge there are views over the sea to the mainland. Vrbnik is a '
            'cultural visit rather than a beach stop, though small bays lie nearby.'
        ),
        'faqs': [
            {
                'q': 'Is Vrbnik worth visiting?',
                'a': (
                    'Yes, for a compact old town on a cliff, local wine and a quieter pace '
                    'than the larger resorts on Krk. It is usually visited as a half-day '
                    'trip.'
                ),
            },
            {
                'q': 'How do I get to Vrbnik?',
                'a': (
                    'Vrbnik is on the east coast of Krk, reached by road from Krk town. '
                    'Rijeka Airport (RJK) is on the island. A car is the easiest way to get '
                    'there.'
                ),
            },
            {
                'q': 'What is there to do in Vrbnik?',
                'a': (
                    'Walk the old town, see the narrow Klančić alley, taste Žlahtina wine, '
                    'enjoy the views from the cliff edge, and visit the church and heritage '
                    'sites.'
                ),
            },
            {
                'q': 'How long should I spend in Vrbnik?',
                'a': (
                    'Two to three hours is enough for a walk and a wine tasting. Add more '
                    'time for a meal or a swim at the coast below.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; autumn for the wine season',
            },
            {
                'label': 'Ideal for',
                'value': 'Old-town walks, wine tasting, heritage',
            },
            {
                'label': 'Time needed',
                'value': '2–3 hours to half a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Krk town',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), on the island of Krk',
            },
        ],
        'good_for': [
            'wine lovers',
            'heritage seekers',
            'photographers',
            'couples',
            'day trips',
        ],
        'sections': [
            {
                'heading': 'A town on a cliff',
                'body': (
                    'Vrbnik was built on a rocky outcrop with the sea far below, which '
                    'gave it natural protection. Its houses press close together along '
                    'steep lanes, and the walk through the old centre ends at the cliff '
                    'edge with a wide view of the Kvarner Bay and the mainland coast. '
                    'Klančić, a very narrow alley, is a small curiosity that visitors '
                    'often look for.'
                ),
            },
            {
                'heading': 'Glagolitic heritage',
                'body': (
                    'Vrbnik was a centre of Glagolitic writing, the early Slavic script '
                    'used in this part of the Adriatic. The Vrbnik Statute, the town’s '
                    'legal code, was written in Glagolitic in 1388. Glagolitic letters '
                    'appear in local churches and documents, and the tradition forms part '
                    'of the identity of the town and of Krk as a whole.'
                ),
            },
            {
                'heading': 'Žlahtina wine',
                'body': (
                    'The valley below Vrbnik is planted with Žlahtina, a white grape grown '
                    'on Krk, and the wine is the town’s best-known product. Cellars and '
                    'restaurants in and around the town offer tastings and local food, '
                    'usually alongside fish, cheese and olive oil. A short drive takes you '
                    'to coves for a swim after a visit.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.075,
        'longitude': 14.6761,
    },
    {
        'name': 'Cres',
        'slug': 'cres',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A Venetian-style harbour town on the island of Cres, with a quiet old '
            'centre and wild landscapes inland.'
        ),
        'description': (
            'Cres is the main town on the island of the same name, set around a '
            'sheltered harbour on the western coast. It has a Venetian-era old town '
            'with a loggia and town walls. The island beyond is thinly populated, '
            'with sheep pastures, oak woods, a freshwater lake and the northern '
            'village of Beli, where griffon vultures nest.'
        ),
        'highlights': [
            'The harbour and old town',
            'The town walls and gate',
            'Vransko Lake',
            'Beli and the griffon vultures',
            'Osor and the canal to Lošinj',
        ],
        'overview': (
            'Cres town lies on the western side of the island of Cres, around a '
            'sheltered, rounded harbour. The old centre has narrow lanes, a loggia and '
            'remains of the town walls, and it shows the influence of the centuries of '
            'Venetian rule across the Kvarner islands. Cres is long and thin, and much '
            'of it is wild: dry-stone walls divide sheep pastures, and oak forest '
            'covers the hills. Vransko Lake, in the middle of the island, is a '
            'freshwater lake that supplies water for Cres and Lošinj. In the north, '
            'the village of Beli stands on a cliff and is home to griffon vultures, '
            'with a visitor centre devoted to them. Cres and Lošinj are joined by a '
            'short canal at Osor, crossed by a swing bridge, so Lošinj can be reached '
            'by road across the bridge.'
        ),
        'faqs': [
            {
                'q': 'Is Cres worth visiting?',
                'a': (
                    'Yes, for a quiet harbour town and an island with wide, empty landscapes. '
                    'It suits travellers who want to walk, swim and eat well without crowds.'
                ),
            },
            {
                'q': 'How do I get to Cres?',
                'a': (
                    'Ferries run to Cres from the mainland, for example from Brestova in '
                    'Istria to Porozina, and from Krk to Merag. Rijeka Airport (RJK) is the '
                    'nearest main airport. Cres is joined to Lošinj by the Osor bridge.'
                ),
            },
            {
                'q': 'What is there to do in Cres?',
                'a': (
                    'Walk the old town and harbour, swim from the coves nearby, visit Vransko '
                    'Lake, drive to Beli and see griffon vultures, and cross to Osor and '
                    'Lošinj.'
                ),
            },
            {
                'q': 'How long should I spend in Cres?',
                'a': (
                    'A day covers the town and a drive to Osor. Staying several days lets you '
                    'explore the northern part of the island, including Beli.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet harbour towns, walking, wildlife',
            },
            {
                'label': 'Time needed',
                'value': 'A day to a week',
            },
            {
                'label': 'Getting there',
                'value': 'Ferry from Brestova (Istria) to Porozina, or from Krk to Merag',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), then ferry or road',
            },
        ],
        'good_for': [
            'quiet holidays',
            'walkers',
            'nature lovers',
            'couples',
            'sailors',
        ],
        'sections': [
            {
                'heading': 'The harbour town',
                'body': (
                    'Cres town is built around a small, rounded harbour that is lined with '
                    'stone houses and cafés. The old centre has a loggia, parts of the '
                    'town walls and a gate, and it is easy to walk in less than an hour. '
                    'Fishing boats and visiting yachts share the harbour. The pace is slow '
                    'outside the summer months, and small pebble beaches and rocky coves '
                    'lie within walking distance.'
                ),
            },
            {
                'heading': 'An island of pastures and woods',
                'body': (
                    'Cres is a long island with a spine of hills, covered with oak woods '
                    'and sheep pastures divided by dry-stone walls. Vransko Lake, in the '
                    'middle of the island, is a freshwater lake that supplies drinking '
                    'water for Cres and Lošinj. The roads are narrow and quiet, and the '
                    'landscape feels remote in comparison with the more developed parts of '
                    'the Adriatic coast.'
                ),
            },
            {
                'heading': 'Beli and Osor',
                'body': (
                    'In the north, the village of Beli sits on a cliff above the sea, and '
                    'the Caput Insulae eco-centre there is dedicated to the griffon '
                    'vultures that nest on the cliffs nearby. In the south, the town of '
                    'Osor stands beside the canal that separates Cres from Lošinj, and a '
                    'swing bridge opens for boats. Osor is a small, quiet town with Roman '
                    'and medieval remains and a history as an early bishop’s seat.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Cres — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Cres',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.9606,
        'longitude': 14.4086,
    },
    {
        'name': 'Mali Lošinj',
        'slug': 'mali-losinj',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'The largest town on the island of Lošinj, with a deep harbour, a seafaring '
            'past and dolphins in the waters nearby.'
        ),
        'description': (
            'Mali Lošinj is the largest town on the island of Lošinj, built around '
            'a long, sheltered harbour. It has a seafaring history, villas from the '
            'days of shipbuilding and the Apoxyomenos Museum, which shows an '
            'ancient Greek bronze statue found in the sea nearby. Pine woods and '
            'coves surround the town.'
        ),
        'highlights': [
            'The harbour promenade',
            'Apoxyomenos Museum',
            'Fortica, the old fortress tower',
            'Church of the Nativity of the Virgin Mary',
            'Pine-lined coves such as Čikat',
        ],
        'overview': (
            'Mali Lošinj sits at the southern end of the island of Lošinj, around a '
            'deep harbour that once made it an important seafaring port. In the 19th '
            'century the town grew rich from shipbuilding and sea trade, and the '
            'captains’ houses and villas near the harbour reflect that period. The '
            'Church of the Nativity of the Virgin Mary is the main parish church, and '
            'the fortress tower, Fortica, stands above the harbour. The Apoxyomenos '
            'Museum shows the ancient Greek bronze statue of an athlete that was found '
            'on the seabed off Lošinj in 1996. Pine woods grow along the shore, and '
            'the bay of Čikat has a shaded promenade and swimming spots. The waters of '
            'the Lošinj archipelago are home to bottlenose dolphins, which research '
            'groups on the island monitor.'
        ),
        'faqs': [
            {
                'q': 'Is Mali Lošinj worth visiting?',
                'a': (
                    'Yes, for a harbour town with a seafaring past, pine-shaded coves and a '
                    'good museum. It is a popular base for sailing, swimming and walks on the '
                    'island.'
                ),
            },
            {
                'q': 'How do I get to Mali Lošinj?',
                'a': (
                    'Lošinj is joined to Cres by a bridge at Osor, and Cres is reached by '
                    'ferry from the mainland. Rijeka Airport (RJK) is the nearest main '
                    'airport.'
                ),
            },
            {
                'q': 'What is there to do in Mali Lošinj?',
                'a': (
                    'Walk the harbour front, visit the Apoxyomenos Museum, climb to the '
                    'Fortica tower, swim at Čikat, take a boat trip, or walk the coastal path '
                    'to Veli Lošinj.'
                ),
            },
            {
                'q': 'How long should I spend in Mali Lošinj?',
                'a': (
                    'A day covers the town and the museum. A stay of several days suits '
                    'swimming, boat trips and walks on the island.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Swimming, boat trips, walking, harbour life',
            },
            {
                'label': 'Time needed',
                'value': 'A day to a week',
            },
            {
                'label': 'Getting there',
                'value': 'Road over the Osor bridge from Cres; ferries to the island group',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), then ferry and road',
            },
        ],
        'good_for': [
            'sailors',
            'swimmers',
            'couples',
            'families',
            'wildlife lovers',
        ],
        'sections': [
            {
                'heading': 'A seafaring town',
                'body': (
                    'Mali Lošinj grew as a harbour town, and in the 19th century local '
                    'shipowners and captains made it an important shipping town on the '
                    'Adriatic. Villas and tall houses along the harbour were built in that '
                    'period, and the town still has a maritime character. The harbour '
                    'front is the heart of town, lined with cafés and moored boats, with '
                    'the old streets rising behind it.'
                ),
            },
            {
                'heading': 'The Apoxyomenos',
                'body': (
                    'In 1996 a diver found an ancient Greek bronze statue of an athlete, '
                    'the Apoxyomenos, lying on the sea floor off Lošinj. After years of '
                    'conservation, it is displayed in the Apoxyomenos Museum in Mali '
                    'Lošinj. The museum tells the story of its discovery and restoration, '
                    'and explains how such statues were made and why this one is so well '
                    'preserved.'
                ),
            },
            {
                'heading': 'Coves, pines and dolphins',
                'body': (
                    'Pine trees grow down to the shore around Mali Lošinj, and a shaded '
                    'path leads along the bay of Čikat, where there are places to swim. '
                    'The sea around the island is home to bottlenose dolphins, and '
                    'conservation groups based on Lošinj monitor them. A coastal path '
                    'links Mali Lošinj with Veli Lošinj.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Mali Lošinj — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Mali%20Lo%C5%A1inj',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.5331,
        'longitude': 14.4689,
    },
    {
        'name': 'Veli Lošinj',
        'slug': 'veli-losinj',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A small harbour village on Lošinj with colourful houses, a stone tower and '
            'a dolphin research centre.'
        ),
        'description': (
            'Veli Lošinj is a small village on the island of Lošinj, a short '
            'distance from Mali Lošinj. Tall captains’ houses surround its tiny '
            'harbour, and a stone tower stands on the waterfront. The Blue World '
            'Institute, a marine research group, is based here and runs an '
            'education centre on dolphins and the sea.'
        ),
        'highlights': [
            'The small harbour and colourful houses',
            'The waterfront tower',
            'Church of St Anthony the Abbot',
            'Blue World Institute visitor centre',
            'Pine-shaded coastal paths',
        ],
        'overview': (
            'Veli Lošinj is the older of the two towns on the island of Lošinj, and it '
            'is smaller and quieter than Mali Lošinj. Its tiny harbour is ringed by '
            'tall, brightly coloured houses built by sea captains, with a stone tower '
            'beside the water. The parish Church of St Anthony the Abbot stands above '
            'the harbour. Paths lead out of the village through pine woods to rocky '
            'coves and bathing spots, and a coastal path leads to Mali Lošinj. Veli '
            'Lošinj is also the base of the Blue World Institute, a marine research '
            'group that studies the bottlenose dolphins of the Lošinj waters and runs '
            'a visitor centre with information about them and about marine '
            'conservation. It is a calm place for walks, swimming and boat trips.'
        ),
        'faqs': [
            {
                'q': 'Is Veli Lošinj worth visiting?',
                'a': (
                    'Yes, for a small, quiet harbour village with sea paths and swimming. It '
                    'is a good choice if you prefer a village feel to a larger town.'
                ),
            },
            {
                'q': 'How do I get to Veli Lošinj?',
                'a': (
                    'Veli Lošinj is a short drive from Mali Lošinj on the island of Lošinj. '
                    'The island is reached over the Osor bridge from Cres, which is served by '
                    'ferries from the mainland. Rijeka Airport (RJK) is the nearest main '
                    'airport.'
                ),
            },
            {
                'q': 'What is there to do in Veli Lošinj?',
                'a': (
                    'Walk around the harbour, visit the tower and the parish church, swim '
                    'from the coves, take the coastal path to Mali Lošinj, and visit the Blue '
                    'World Institute centre.'
                ),
            },
            {
                'q': 'How long should I spend in Veli Lošinj?',
                'a': (
                    'A few hours is enough for the village and the harbour. Longer stays suit '
                    'those who want to swim, walk the coastal paths and take boat trips.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Quiet village stays, coastal walks, marine wildlife',
            },
            {
                'label': 'Time needed',
                'value': 'A few hours to a few days',
            },
            {
                'label': 'Getting there',
                'value': 'Short drive or coastal walk from Mali Lošinj',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), then ferry and road',
            },
        ],
        'good_for': [
            'quiet holidays',
            'couples',
            'walkers',
            'wildlife lovers',
            'photographers',
        ],
        'sections': [
            {
                'heading': 'The harbour',
                'body': (
                    'Veli Lošinj is built around a very small harbour at the end of a '
                    'narrow inlet. Tall houses of different colours, built by captains who '
                    'made their living at sea, rise on three sides, and a stone tower '
                    'guards the water. Boats of all sizes tie up along the quay, and cafés '
                    'and restaurants fill the waterfront. The village is easy to explore '
                    'in an hour or two.'
                ),
            },
            {
                'heading': 'Dolphins and the sea',
                'body': (
                    'The Blue World Institute, a marine research and conservation group, '
                    'has its base in Veli Lošinj. It studies the bottlenose dolphins that '
                    'live in the waters around Lošinj and Cres, and its visitor centre '
                    'explains the work and the local marine environment. The centre is a '
                    'good stop for families and for anyone interested in the sea life of '
                    'the northern Adriatic.'
                ),
            },
            {
                'heading': 'Paths and coves',
                'body': (
                    'Pine woods grow around Veli Lošinj, and coastal paths lead through '
                    'them to rocky bays and swimming spots. The coastal path to Mali '
                    'Lošinj passes pine woods and small coves. Boat trips from the harbour '
                    'run in season, and the island’s quiet roads are good for walking.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Veli Lošinj — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Veli%20Lo%C5%A1inj',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.5217,
        'longitude': 14.5133,
    },
    {
        'name': 'Rab',
        'slug': 'rab',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A medieval walled town on the island of Rab, known for its four bell '
            'towers and its summer festival.'
        ),
        'description': (
            'Rab is a walled medieval town on a narrow peninsula on the western '
            'coast of the island of Rab. Its skyline is marked by four bell towers, '
            'and a long main street runs along the ridge of the old town. The '
            'Rapska fjera festival each July recreates medieval life.'
        ),
        'highlights': [
            'The four bell towers',
            'The old town and its main street',
            'Komrčar Park',
            'The Kalifront peninsula',
            'The Rapska fjera festival',
        ],
        'overview': (
            'Rab town stands on a narrow peninsula that projects into the sea on the '
            'island’s western side. The old town is easily recognised from the water '
            'by its four medieval bell towers, which rise in a line along the ridge. '
            'Three parallel streets run the length of the town, with stairs and lanes '
            'between them, and the Cathedral of the Assumption of the Virgin Mary is '
            'among the main sights. Park Komrčar, a pine-shaded park, lies along the '
            'coast below the old town, and the Kalifront peninsula faces the sea to '
            'the north. Each July the town holds the Rapska fjera, a festival with '
            'costumes, crafts and a crossbow tournament. The island of Rab is reached '
            'by ferry from the mainland, and its coast has coves and beaches, '
            'including the sandy bays near Lopar.'
        ),
        'faqs': [
            {
                'q': 'Is Rab worth visiting?',
                'a': (
                    'Yes, for a well-preserved medieval town on the sea, with a distinctive '
                    'skyline and good swimming nearby. It suits travellers who like walking '
                    'and old streets.'
                ),
            },
            {
                'q': 'How do I get to Rab?',
                'a': (
                    'Rab is reached by car ferry from Stinica on the mainland to Mišnjak on '
                    'the island, and there are seasonal boat links from other ports. Rijeka '
                    'Airport (RJK) is the nearest main airport.'
                ),
            },
            {
                'q': 'What is there to do in Rab?',
                'a': (
                    'Walk the three streets of the old town, climb a bell tower, stroll in '
                    'Komrčar Park, swim from the beaches nearby, and visit the sandy bays '
                    'near Lopar.'
                ),
            },
            {
                'q': 'How long should I spend in Rab?',
                'a': (
                    'A day covers the old town. Several days suit a beach holiday with walks '
                    'and time for Lopar.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; July for the Rapska fjera festival',
            },
            {
                'label': 'Ideal for',
                'value': 'Medieval old-town walks, swimming, family holidays',
            },
            {
                'label': 'Time needed',
                'value': 'A day to a week',
            },
            {
                'label': 'Getting there',
                'value': 'Car ferry Stinica–Mišnjak; seasonal boats from other ports',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), then road and ferry',
            },
        ],
        'good_for': [
            'old-town lovers',
            'families',
            'swimmers',
            'couples',
            'festival visitors',
        ],
        'sections': [
            {
                'heading': 'The town of four bell towers',
                'body': (
                    'Rab’s medieval old town is built along a ridge, and its four bell '
                    'towers are visible from far across the water. The three parallel '
                    'streets, linked by stairs, follow the ridge and make the town easy to '
                    'walk. Churches, small squares and stone palaces fill the area, and '
                    'the harbour on the sheltered side is lined with cafés and '
                    'restaurants.'
                ),
            },
            {
                'heading': 'Parks and shore',
                'body': (
                    'Park Komrčar, a pine park beside the sea, gives shade and walking '
                    'paths close to the old town. The Kalifront peninsula has a promenade '
                    'and views over the water. Pebble beaches and rocky platforms for '
                    'swimming are found along the shore on both sides.'
                ),
            },
            {
                'heading': 'Rapska fjera and Lopar',
                'body': (
                    'Each July the Rapska fjera brings costumed processions, crafts, music '
                    'and a crossbow tournament to the old town, recalling medieval life on '
                    'the island. At the northern end of the island, the Lopar peninsula '
                    'has several sandy beaches, which are unusual on the Croatian coast '
                    'and popular with families. Lopar is a short drive from Rab town.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Rab — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Rab',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.7565,
        'longitude': 14.76,
    },
    {
        'name': 'Lopar',
        'slug': 'lopar',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A peninsula at the northern end of Rab, known for its sandy beaches '
            'including Paradise Beach.'
        ),
        'description': (
            'Lopar occupies a peninsula at the northern end of the island of Rab '
            'and is known for its sandy beaches, among them Rajska plaža, or '
            'Paradise Beach. The sea here is shallow near the shore, which makes it '
            'popular with families, and pine woods and farmland lie behind the '
            'coast.'
        ),
        'highlights': [
            'Rajska plaža (Paradise Beach)',
            'Sandy bays with shallow water',
            'Pine woods behind the coast',
            'Walking and cycling paths',
            'The ferry link to the mainland',
        ],
        'overview': (
            'Lopar lies at the northern end of the island of Rab, on a peninsula edged '
            'by bays and low hills. Its main attraction is the sand: Rajska plaža, '
            'known in English as Paradise Beach, and several other bays have sandy '
            'shores and shallow water, a rarity on a coast that is mostly pebble and '
            'rock. This makes Lopar a popular choice for families with small children. '
            'Behind the beaches, pine woods and farmland cover the peninsula, with '
            'paths for walking and cycling. The area has a few small villages and '
            'holiday houses rather than a large town. Rab town is a short drive south, '
            'and the ferry from Stinica on the mainland lands at Mišnjak at the '
            'island’s southern end, from where the island road leads through Rab town '
            'to Lopar.'
        ),
        'faqs': [
            {
                'q': 'Is Lopar worth visiting?',
                'a': (
                    'Yes, for sandy beaches with shallow water, which suit families. It is a '
                    'quiet, beach-focused area rather than a town for sightseeing.'
                ),
            },
            {
                'q': 'How do I get to Lopar?',
                'a': (
                    'Lopar is at the northern end of the island of Rab. A car ferry from '
                    'Stinica on the mainland reaches Mišnjak on the island, and from there it '
                    'is a drive to Lopar. Rijeka Airport (RJK) is the nearest main airport.'
                ),
            },
            {
                'q': 'What is there to do in Lopar?',
                'a': (
                    'Swim and relax on Rajska plaža and other sandy beaches, walk or cycle '
                    'through the pine woods, and drive to Rab town to see the old town.'
                ),
            },
            {
                'q': 'How long should I spend in Lopar?',
                'a': (
                    'A day suits a beach visit. A stay of several days works for a family '
                    'holiday combined with trips to Rab town.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'June to early September for swimming',
            },
            {
                'label': 'Ideal for',
                'value': 'Sandy beaches, family holidays, walking and cycling',
            },
            {
                'label': 'Time needed',
                'value': 'A day to a week',
            },
            {
                'label': 'Getting there',
                'value': 'Car ferry Stinica–Mišnjak, then road to Lopar',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK), then road and ferry',
            },
        ],
        'good_for': [
            'families with children',
            'beach holidays',
            'cyclists',
            'walkers',
            'quiet stays',
        ],
        'sections': [
            {
                'heading': 'Sandy bays',
                'body': (
                    'Lopar’s beaches are made of sand, and the sea deepens slowly, which '
                    'is unusual in the northern Adriatic where most beaches are pebble or '
                    'rock. Rajska plaža, or Paradise Beach, is the best known, a long '
                    'sandy shore with shallow water and a gentle slope. Several other '
                    'sandy bays lie around the peninsula, with different degrees of '
                    'shelter and shade.'
                ),
            },
            {
                'heading': 'Pine woods and paths',
                'body': (
                    'Behind the coast, pine woods cover the peninsula, and marked paths '
                    'and quiet roads run through them. The terrain is gentle, so it is '
                    'suitable for walking and cycling at a relaxed pace. Small villages '
                    'and holiday houses are scattered across the area, and local '
                    'restaurants serve fish and island food.'
                ),
            },
            {
                'heading': 'Getting around the island',
                'body': (
                    'Most visitors reach Lopar by car, after taking the ferry from Stinica '
                    'to Mišnjak on Rab. Rab town, with its medieval old town, is a short '
                    'drive to the south, and boat trips run from the island’s harbours in '
                    'season. Check ferry times in advance for peak summer periods, when '
                    'queues for the crossing can be long.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Lopar — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Lopar',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.8317,
        'longitude': 14.7222,
    },
    {
        'name': 'Crikvenica',
        'slug': 'crikvenica',
        'region': 'kvarner',
        'place_type': 'coastal',
        'featured': False,
        'summary': (
            'A family seaside town on the Kvarner coast, with a long promenade, pebble '
            'beaches and a Pauline monastery.'
        ),
        'description': (
            'Crikvenica is a seaside town on the Vinodol coast south-east of '
            'Rijeka. Its long promenade, beaches and parks have made it a holiday '
            'destination since the late 19th century. The town grew up around a '
            'Pauline monastery, and the aquarium and the neighbouring resorts add '
            'to a family-friendly stay.'
        ),
        'highlights': [
            'The seafront promenade',
            'The Pauline monastery',
            'Pebble beaches',
            'Crikvenica Aquarium',
            'Neighbouring Selce and Novi Vinodolski',
        ],
        'overview': (
            'Crikvenica lies on the coast south-east of Rijeka, along the Kvarner '
            'coast. The town takes its name from the Croatian word for church, crkva, '
            'after the Pauline monastery founded here in the 15th century, which is '
            'still one of its main landmarks. From the late 19th century, Crikvenica '
            'developed as a health resort, and its long seafront promenade, gardens '
            'and beaches remain its main attractions. The beaches are mostly pebble, '
            'with shallow water that suits children. The town is a base for the nearby '
            'resorts of Selce and Novi Vinodolski and for trips to the islands of Krk '
            'and Rab. Rijeka is within easy reach by road, and the coast road '
            'continues south towards Senj and Zadar.'
        ),
        'faqs': [
            {
                'q': 'Is Crikvenica worth visiting?',
                'a': (
                    'Yes, for a relaxed family beach holiday with a long promenade and good '
                    'road access to Rijeka and the islands. It is more of a resort than a '
                    'sightseeing town.'
                ),
            },
            {
                'q': 'How do I get to Crikvenica?',
                'a': (
                    'Crikvenica is on the coast road south-east of Rijeka, with buses from '
                    'Rijeka. The nearest airport is Rijeka Airport (RJK) on Krk, reached over '
                    'the Krk Bridge.'
                ),
            },
            {
                'q': 'What is there to do in Crikvenica?',
                'a': (
                    'Walk the seafront promenade, swim from the town beaches, visit the '
                    'Pauline monastery and the aquarium, and take day trips to Krk, Rab and '
                    'Senj.'
                ),
            },
            {
                'q': 'How long should I spend in Crikvenica?',
                'a': (
                    'A day suits a beach stop. Families often stay a week and add trips along '
                    'the coast.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn',
            },
            {
                'label': 'Ideal for',
                'value': 'Family beach holidays, promenade walks, coastal base',
            },
            {
                'label': 'Time needed',
                'value': 'A day to a week',
            },
            {
                'label': 'Getting there',
                'value': 'Coast road and buses from Rijeka',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'families',
            'beach holidays',
            'walkers',
            'coastal road trips',
            'budget stays',
        ],
        'sections': [
            {
                'heading': 'A resort with monastic roots',
                'body': (
                    'The town grew around a Pauline monastery founded in the 15th century, '
                    'and the name Crikvenica comes from the word for church. The monastery '
                    'church and its buildings still stand near the sea. From the late 19th '
                    'century, the sheltered climate and seafront made Crikvenica a health '
                    'resort, and the promenade and gardens still reflect that tradition.'
                ),
            },
            {
                'heading': 'Beaches and promenade',
                'body': (
                    'A long seafront promenade runs along the beaches, with cafés, parks '
                    'and playgrounds. The beaches are mostly pebble with gentle entry to '
                    'the sea, which suits families with small children. Boat trips and '
                    'water sports operate in season, and neighbouring Selce, a smaller '
                    'village to the south-east, has its own quieter beaches.'
                ),
            },
            {
                'heading': 'Along the coast',
                'body': (
                    'Novi Vinodolski lies a short distance to the south-east, and the '
                    'coast road continues to Senj and further south. The island of Krk is '
                    'close by, and the ferry to Rab leaves from the mainland farther '
                    'south. Rijeka can be reached in under an hour by road, making day '
                    'trips to its museums and Trsat Castle simple.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Crikvenica — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Crikvenica',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.1769,
        'longitude': 14.6919,
    },
    {
        'name': 'Senj',
        'slug': 'senj',
        'region': 'kvarner',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'An old coastal town below the Velebit mountains, known for Nehaj Fortress, '
            'the Uskoks and the bura wind.'
        ),
        'description': (
            'Senj is an old town on the Adriatic coast at the foot of the Velebit '
            'mountains. Its landmark is Nehaj Fortress, built in 1558 above the '
            'town. Senj was home to the Uskoks, border fighters who defended the '
            'coast, and the strong northern wind called the bura often blows '
            'through the Vratnik pass above it.'
        ),
        'highlights': [
            'Nehaj Fortress',
            'The old town and the cathedral',
            'The Uskok history',
            'The waterfront and harbour',
            'Gateway to Northern Velebit',
        ],
        'overview': (
            'Senj is one of the oldest towns on the Croatian coast, with a history '
            'that goes back to antiquity. Its modern identity is closely tied to the '
            'Uskoks, refugees and fighters who defended the Habsburg border against '
            'the Ottomans in the 16th and 17th centuries. Nehaj Fortress, a square '
            'stone tower on a hill above the town, was built in 1558 and now houses a '
            'museum about the Uskoks and the town. In the old centre, the Cathedral of '
            'the Assumption and the narrow streets recall the town’s long history. '
            'Senj is also known for the bura, a strong cold wind that blows down from '
            'the mountains. The town lies on the coast road and is a gateway to the '
            'Northern Velebit National Park, which rises directly behind it.'
        ),
        'faqs': [
            {
                'q': 'Is Senj worth visiting?',
                'a': (
                    'Yes, for history and a less touristy stretch of coast. Nehaj Fortress '
                    'and the old town can be seen in a few hours, and the town is a good stop '
                    'on the coast road.'
                ),
            },
            {
                'q': 'How do I get to Senj?',
                'a': (
                    'Senj is on the coastal road between Rijeka and Zadar, with buses along '
                    'the route. The nearest airport is Rijeka Airport (RJK) on Krk. A car is '
                    'the easiest way to reach it.'
                ),
            },
            {
                'q': 'What is there to do in Senj?',
                'a': (
                    'Visit Nehaj Fortress and its museum, walk the old town and the '
                    'cathedral, stroll the waterfront, and use the town as a base for '
                    'Northern Velebit National Park.'
                ),
            },
            {
                'q': 'How long should I spend in Senj?',
                'a': (
                    'Two to four hours covers the fortress and the old town. Add a night if '
                    'you want to combine it with hiking in Velebit.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Late spring to early autumn; the bura can be strong in winter',
            },
            {
                'label': 'Ideal for',
                'value': 'History, coastal road trips, Velebit access',
            },
            {
                'label': 'Time needed',
                'value': '2–4 hours to a day',
            },
            {
                'label': 'Getting there',
                'value': 'Coastal road between Rijeka and Zadar; buses along the route',
            },
            {
                'label': 'Region',
                'value': 'Kvarner',
            },
            {
                'label': 'Nearest airport',
                'value': 'Rijeka Airport (RJK) on Krk, reached by road over the Krk Bridge',
            },
        ],
        'good_for': [
            'history lovers',
            'road trippers',
            'hikers',
            'photographers',
            'off-the-beaten-track travellers',
        ],
        'sections': [
            {
                'heading': 'The Uskoks',
                'body': (
                    'In the 16th century Senj became a base for the Uskoks, refugees from '
                    'lands conquered by the Ottomans who served as border soldiers for the '
                    'Habsburgs. They raided Ottoman and Venetian shipping from the '
                    'harbour, which led to diplomatic tension. Nehaj Fortress was built in '
                    '1558 to defend the town, and the legend of the Uskoks remains a '
                    'central part of Senj’s identity today.'
                ),
            },
            {
                'heading': 'Nehaj Fortress and the old town',
                'body': (
                    'Nehaj Fortress stands on a hill above Senj, a square tower with stone '
                    'walls. Inside, the museum tells the story of the Uskoks and of the '
                    'town, and the top gives a view of the coast and of the islands of '
                    'Krk, Rab and Prvić. In the old town below, the Cathedral of the '
                    'Assumption and the narrow streets are a short walk from the '
                    'waterfront.'
                ),
            },
            {
                'heading': 'The bura and Velebit',
                'body': (
                    'The bura is a cold, dry wind that blows from the mountains towards '
                    'the sea, and Senj is one of the places on the coast where it is '
                    'strongest. Behind the town, the Velebit mountains rise to the '
                    'Northern Velebit National Park, which offers hiking trails and '
                    'mountain scenery. Senj makes a convenient starting point for trips '
                    'into the park by car.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Senj — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Senj',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 44.9894,
        'longitude': 14.9036,
    },
    {
        'name': 'Zagreb',
        'slug': 'zagreb',
        'region': 'zagreb',
        'place_type': 'cities',
        'featured': True,
        'summary': (
            'Croatia’s capital, with a Habsburg-era centre, a hilltop Upper Town, '
            'lively cafés and Mount Medvednica behind.'
        ),
        'description': (
            'Zagreb is the capital and largest city of Croatia, set below Mount '
            'Medvednica. The Upper Town (Gornji grad) keeps medieval streets, St '
            'Mark’s Church and the Lotrščak Tower, while the Lower Town has '
            'Austro-Hungarian squares, parks and museums. The city is known for its '
            'café culture, markets and Advent season.'
        ),
        'highlights': [
            'Upper Town and St Mark’s Church',
            'Zagreb Cathedral',
            'Ban Jelačić Square and Dolac market',
            'Mirogoj cemetery',
            'Tkalčićeva Street and the Lotrščak Tower',
        ],
        'overview': (
            'Zagreb grew from two medieval settlements on neighbouring hills, Kaptol '
            'and Gradec, which merged into one city. Today it is Croatia’s capital, '
            'largest city and main centre for government, business and culture. The '
            'Upper Town keeps cobbled streets, gas lamps, the Gothic St Mark’s Church '
            'with its coloured tile roof, and the Lotrščak Tower, where a cannon is '
            'fired at noon every day. The Lower Town, laid out in the 19th century, '
            'has a grid of squares, parks and grand buildings, including the Croatian '
            'National Theatre and many museums. Ban Jelačić Square is the central '
            'meeting point, and the Dolac market is a daily feature. The Cathedral of '
            'the Assumption of the Virgin Mary, with its two spires, dominates the '
            'Kaptol. Cafés fill the streets, especially Tkalčićeva, and the city holds '
            'a large Advent market in December. Mount Medvednica rises directly behind '
            'the city for hiking.'
        ),
        'faqs': [
            {
                'q': 'Is Zagreb worth visiting?',
                'a': (
                    'Yes, for a walkable capital with museums, cafés, markets and a historic '
                    'centre. It also makes a good base for Samobor, Medvednica and the '
                    'continental part of Croatia.'
                ),
            },
            {
                'q': 'How do I get to Zagreb?',
                'a': (
                    'Zagreb Franjo Tuđman Airport (ZAG) is about 17 km south-east of the '
                    'centre, with bus and taxi links to the city. The city is also the main '
                    'hub for roads and trains in Croatia, with direct services from '
                    'neighbouring countries.'
                ),
            },
            {
                'q': 'What is there to do in Zagreb?',
                'a': (
                    'Walk the Upper Town and see St Mark’s Church, visit the cathedral and '
                    'Dolac market, stroll Tkalčićeva Street, see Mirogoj cemetery, visit '
                    'museums such as the Museum of Broken Relationships, and hike on '
                    'Medvednica.'
                ),
            },
            {
                'q': 'How long should I spend in Zagreb?',
                'a': (
                    'Two days cover the main sights. Three or four days allow more museums, '
                    'Medvednica and a day trip to Samobor.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring and autumn; December for the Advent season',
            },
            {
                'label': 'Ideal for',
                'value': 'City breaks, museums, cafés, culture',
            },
            {
                'label': 'Time needed',
                'value': '2–3 days',
            },
            {
                'label': 'Getting there',
                'value': 'Zagreb Airport (ZAG); main road and rail hub of Croatia',
            },
            {
                'label': 'Region',
                'value': 'Zagreb',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zagreb Franjo Tuđman Airport (ZAG), about 17 km from the centre',
            },
        ],
        'good_for': [
            'city breaks',
            'culture lovers',
            'foodies',
            'museum visitors',
            'Advent visits',
        ],
        'sections': [
            {
                'heading': 'Upper Town and Lower Town',
                'body': (
                    'The Upper Town (Gornji grad) is the oldest part of Zagreb, with '
                    'cobbled lanes, St Mark’s Church, the Lotrščak Tower and the funicular '
                    'that links it to the Lower Town. The Lower Town (Donji grad) was laid '
                    'out in the 19th century as a grid of squares and parks, with the '
                    'Zrinjevac park, museums and theatres. Together they give the city its '
                    'mix of medieval and Austro-Hungarian character.'
                ),
            },
            {
                'heading': 'Markets, cafés and museums',
                'body': (
                    'Dolac, the open-air market just off Ban Jelačić Square, sells produce '
                    'and local food daily. Café life centres on Tkalčićeva Street and the '
                    'squares of the Lower Town. The city has many museums, including the '
                    'Museum of Broken Relationships, the Museum of Contemporary Art, the '
                    'Mimara Museum and the Archaeological Museum. Mirogoj, the city '
                    'cemetery, is known for its arcades and park-like setting.'
                ),
            },
            {
                'heading': 'Around Zagreb',
                'body': (
                    'Mount Medvednica rises behind the city and is reached by road in '
                    'under an hour, offering hiking and views from its highest peak, '
                    'Sljeme. Samobor, a small town known for its cream cake and carnival, '
                    'lies west of Zagreb. The city is also well placed for trips by road '
                    'or rail to the coast, to Plitvice Lakes and to the countryside of '
                    'continental Croatia.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Zagreb — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Zagreb',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.815,
        'longitude': 15.9819,
    },
    {
        'name': 'Samobor',
        'slug': 'samobor',
        'region': 'zagreb',
        'place_type': 'cultural',
        'featured': False,
        'summary': (
            'A small town west of Zagreb, known for its cream cake, mustard, carnival '
            'and walks in the Samobor hills.'
        ),
        'description': (
            'Samobor is a small town at the foot of the Samobor hills, about 20 '
            'kilometres west of Zagreb. It has a pretty Baroque and '
            'Austro-Hungarian centre, a ruined old castle above it, and a food '
            'tradition that includes samoborska kremšnita, a cream cake, and '
            'Samobor mustard.'
        ),
        'highlights': [
            'The main square, Trg kralja Tomislava',
            'Samoborska kremšnita (cream cake)',
            'Samobor mustard',
            'The old castle ruins above the town',
            'The Samobor carnival (Fašnik)',
        ],
        'overview': (
            'Samobor lies on the Gradna stream at the foot of the Samobor hills, about '
            '20 kilometres west of Zagreb. The town centre is built around a compact '
            'main square with pastel Baroque and Austro-Hungarian buildings, a parish '
            'church and cafés. Above the town, the ruins of the old castle can be '
            'reached on foot through the woods, and the hills beyond offer walking '
            'trails, including routes to the medieval castle of Okić. Samobor is known '
            'for its food: the kremšnita, a custard and cream cake, is sold in the '
            'town’s pastry shops, and the local mustard is a traditional product. The '
            'Samobor carnival, Fašnik, takes place before Lent and is one of the '
            'town’s best-known events. The town is an easy half-day or day trip from '
            'Zagreb.'
        ),
        'faqs': [
            {
                'q': 'Is Samobor worth visiting?',
                'a': (
                    'Yes, as a short trip from Zagreb for a pleasant main square, local '
                    'pastries and walks in the hills. It is calm and compact.'
                ),
            },
            {
                'q': 'How do I get to Samobor?',
                'a': (
                    'Samobor is about 20 km west of Zagreb. Regular buses run from Zagreb, '
                    'and the drive takes roughly half an hour outside rush hour. Zagreb '
                    'Airport (ZAG) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Samobor?',
                'a': (
                    'Walk the main square, try a kremšnita, taste the local mustard, climb to '
                    'the castle ruins, and hike in the Samobor hills. In late winter the '
                    'carnival is a highlight.'
                ),
            },
            {
                'q': 'How long should I spend in Samobor?',
                'a': (
                    'Half a day covers the centre and a cake. Hikers can spend a full day in '
                    'the hills.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn for walks; February or March for the carnival',
            },
            {
                'label': 'Ideal for',
                'value': 'Day trips from Zagreb, food, easy hill walks',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'About 20 km west of Zagreb; regular buses',
            },
            {
                'label': 'Region',
                'value': 'Zagreb',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zagreb Franjo Tuđman Airport (ZAG)',
            },
        ],
        'good_for': [
            'day trippers',
            'foodies',
            'walkers',
            'families',
            'carnival visitors',
        ],
        'sections': [
            {
                'heading': 'The town centre',
                'body': (
                    'Samobor’s centre is built around Trg kralja Tomislava, a small main '
                    'square of low, pastel-coloured buildings with the parish church on '
                    'one side. The Gradna stream runs through the town, and the streets '
                    'around the square have small shops, pastry shops and cafés. The town '
                    'is compact and easy to explore on foot in an hour or two, with plenty '
                    'of places to stop.'
                ),
            },
            {
                'heading': 'Kremšnita and mustard',
                'body': (
                    'The samoborska kremšnita is a layered cake of custard and cream '
                    'between thin pastry, and several pastry shops in town sell it. The '
                    'local mustard, made to a traditional recipe, is another product '
                    'visitors take home. Restaurants in and around the town serve regional '
                    'dishes, and wine from the nearby hills is also offered.'
                ),
            },
            {
                'heading': 'Castle ruins and hills',
                'body': (
                    'A path leads from the town to the ruins of the Samobor old castle on '
                    'a hill above the centre. Beyond it, the Samobor hills have marked '
                    'trails through woods and meadows, including routes to the Okić castle '
                    'ruins. The Fašnik carnival, held before Lent, brings parades and '
                    'costumes to the town, and is a good time to visit if you want to see '
                    'local traditions.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Samobor — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Samobor',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.8011,
        'longitude': 15.7108,
    },
    {
        'name': 'Medvednica Nature Park',
        'slug': 'medvednica-nature-park',
        'region': 'zagreb',
        'place_type': 'mountains',
        'featured': False,
        'summary': (
            'The wooded mountain above Zagreb, with the Sljeme summit, forest trails '
            'and the medieval Medvedgrad fortress.'
        ),
        'description': (
            'Medvednica is the wooded mountain that rises directly north of Zagreb '
            'and was declared a nature park in 1981. Its highest point, Sljeme, is '
            'just over 1,000 metres. Forest trails, viewpoints, the medieval '
            'Medvedgrad fortress and a winter ski area make it the city’s main '
            'outdoor playground.'
        ),
        'highlights': [
            'Sljeme, the summit',
            'Medvedgrad fortress',
            'Forest hiking trails',
            'Views over Zagreb',
            'Winter skiing on Sljeme',
        ],
        'overview': (
            'Medvednica rises directly north of Zagreb and is covered mostly by beech '
            'and oak forest. It was declared a nature park in 1981 and is a popular '
            'day-out destination for the city’s residents. The highest point, Sljeme, '
            'stands just over 1,000 metres and has a television tower and a view south '
            'over Zagreb and, on clear days, towards the Zagorje hills. Medvedgrad, a '
            'medieval fortress restored in the 20th century, sits on a spur above the '
            'city and offers a close view of the capital. Marked trails of different '
            'lengths run across the mountain, and mountain huts offer simple food. In '
            'winter the Sljeme ski area opens when snow conditions allow, and it has '
            'hosted Alpine skiing World Cup races. The mountain is reached by road '
            'from the city centre in a short drive.'
        ),
        'faqs': [
            {
                'q': 'Is Medvednica worth visiting?',
                'a': (
                    'Yes, for a quick escape into forest and mountain air close to the city. '
                    'It suits an easy half-day outing as well as longer hikes.'
                ),
            },
            {
                'q': 'How do I get to Medvednica?',
                'a': (
                    'The park is directly north of Zagreb and is reached by road in under an '
                    'hour. Check current public transport timetables before you go. Zagreb '
                    'Airport (ZAG) is the nearest airport.'
                ),
            },
            {
                'q': 'What is there to do in Medvednica?',
                'a': (
                    'Hike the marked trails, walk to Sljeme for the view, visit Medvedgrad '
                    'fortress, stop at a mountain hut for food, and ski in winter when '
                    'conditions allow.'
                ),
            },
            {
                'q': 'How long should I spend in Medvednica?',
                'a': (
                    'A half day suits the main viewpoints. A full day lets you hike between '
                    'Medvedgrad and Sljeme.'
                ),
            },
        ],
        'quick_facts': [
            {
                'label': 'Best time',
                'value': 'Spring to autumn for hiking; winter for skiing when snow allows',
            },
            {
                'label': 'Ideal for',
                'value': 'Hiking, city views, forest walks, winter sports',
            },
            {
                'label': 'Time needed',
                'value': 'Half a day to a day',
            },
            {
                'label': 'Getting there',
                'value': 'By road from Zagreb; check public transport timetables',
            },
            {
                'label': 'Region',
                'value': 'Zagreb',
            },
            {
                'label': 'Nearest airport',
                'value': 'Zagreb Franjo Tuđman Airport (ZAG)',
            },
        ],
        'good_for': [
            'hikers',
            'families',
            'cyclists',
            'skiers',
            'city escapes',
        ],
        'sections': [
            {
                'heading': 'Forest above the city',
                'body': (
                    'Medvednica forms the green backdrop to Zagreb and is covered by beech '
                    'and oak forest. The park was declared in 1981 to protect its woods, '
                    'streams and caves. Because it is so close to the city, the paths are '
                    'busy on weekends, but the further trails are quiet. The air is cooler '
                    'than in town, which makes it a welcome escape in summer.'
                ),
            },
            {
                'heading': 'Sljeme and Medvedgrad',
                'body': (
                    'Sljeme is the highest point of the mountain, with a tower and a '
                    'viewing area. Medvedgrad, a medieval fortress above the city, was '
                    'restored in the 20th century and has views over Zagreb. Marked trails '
                    'link the fortress, the summit and the huts, so it is possible to plan '
                    'routes of different lengths, from short walks to a full day on foot.'
                ),
            },
            {
                'heading': 'Winter on Sljeme',
                'body': (
                    'In winter, when there is enough snow, the Sljeme ski area opens close '
                    'to the city. The slopes have hosted Alpine skiing World Cup races, '
                    'and the area is also used for sledding and winter walks. Conditions '
                    'vary from year to year, so check snow reports before going. In other '
                    'seasons the same paths are used for hiking and cycling.'
                ),
            },
        ],
        'external_links': [
            {
                'label': 'Medvednica — Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Medvednica',
            },
            {
                'label': 'Medvednica Nature Park',
                'url': 'https://pp-medvednica.hr/',
            },
            {
                'label': 'Croatian National Tourist Board',
                'url': 'https://croatia.hr/en-gb',
            },
        ],
        'latitude': 45.9014,
        'longitude': 15.9511,
    },
]
