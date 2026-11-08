"""Croatia events: annual festivals, carnivals, fairs and sporting events.

Real annual events across Croatia, with approximate timing (``when_label``) and no prices or
fixed dates. Read by ``seed_croatia``.
"""

from __future__ import annotations

EVENTS: list[dict] = [
    {
        'name': 'Rijeka Carnival',
        'slug': 'rijeka-carnival',
        'category': 'tradition',
        'region': 'kvarner',
        'place_slug': 'rijeka',
        'venue': 'Rijeka city centre',
        'when_label': 'February to early March',
        'month': 2,
        'featured': True,
        'summary': 'A large winter carnival in Rijeka, with masked groups, bell ringers and a final '
        'parade through the city.',
        'description': 'Rijeka Carnival is held in the weeks before Lent and is one of the biggest '
        'carnivals in Croatia. Masked groups from Croatia and abroad take part in a '
        'final parade through the city, and the bell ringers (zvončari) of the '
        'Kvarner villages, in sheepskin costumes, are among its best-known figures. '
        'There is also a children’s carnival.',
        'highlights': [
            'Final parade of masked groups',
            'Zvončari bell ringers in traditional costume',
            'Children’s carnival',
            'Street events in the city centre',
        ],
        'faqs': [
            {
                'q': 'When is Rijeka Carnival held?',
                'a': 'In the weeks before Lent, usually from late January or February into early '
                'March, with the main parade on a weekend. The town announces exact dates '
                'each year.',
            },
            {
                'q': 'Is Rijeka Carnival free to watch?',
                'a': 'The street events and parades can be watched in the street; check the '
                'organisers for any ticketed events.',
            },
            {
                'q': 'Who are the zvončari?',
                'a': 'Groups of men from villages around Rijeka and Kastav who wear sheepskins and '
                'bells and walk in procession to drive away winter and evil. They are a '
                'Kvarner carnival tradition.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Samobor Carnival',
        'slug': 'samobor-carnival',
        'category': 'tradition',
        'region': 'zagreb',
        'place_slug': 'samobor',
        'venue': 'Samobor town centre',
        'when_label': 'February',
        'month': 2,
        'featured': False,
        'summary': 'A long-running carnival in the town of Samobor near Zagreb, with masked groups '
        'and parades before Lent.',
        'description': 'Samoborski fašnik is the carnival of the town of Samobor, west of Zagreb. In '
        'the weeks before Lent, masked groups, music and satirical performances fill '
        'the town centre, with a parade on the main weekend. It is a regional '
        'tradition and a popular day out from Zagreb.',
        'highlights': [
            'Masked groups and parades',
            'Satirical performances',
            'Music in the town centre',
            'Easy day trip from Zagreb',
        ],
        'faqs': [
            {
                'q': 'When is Samobor Carnival held?',
                'a': 'In the weeks before Lent, usually in February. The town sets exact dates '
                'each year.',
            },
            {
                'q': 'How do I get to Samobor?',
                'a': 'By road or bus from Zagreb, about 25 km west of the capital.',
            },
            {
                'q': 'Is the carnival suitable for children?',
                'a': 'Yes, families attend the parade, and the town usually also arranges events '
                'for children.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Feast of St Blaise',
        'slug': 'feast-of-st-blaise-dubrovnik',
        'category': 'tradition',
        'region': 'dubrovnik',
        'place_slug': 'dubrovnik',
        'venue': 'Dubrovnik Old Town',
        'when_label': 'Early February',
        'month': 2,
        'featured': False,
        'summary': 'Dubrovnik’s annual feast for its patron saint, with a procession through the Old '
        'Town.',
        'description': 'The Festivity of St Blaise (Festa svetog Vlaha) honours the patron saint of '
        'Dubrovnik. Processions carrying relics of the saint, with folk groups and '
        'clergy in traditional dress, pass through the Old Town. The festivity is on '
        'UNESCO’s list of intangible cultural heritage.',
        'highlights': [
            'Procession with relics of St Blaise',
            'Folk costume and flags',
            'Mass at the cathedral',
            'UNESCO-listed tradition',
        ],
        'faqs': [
            {
                'q': 'When is the Feast of St Blaise?',
                'a': 'On 3 February each year, with related events in the days around it.',
            },
            {
                'q': 'Who was St Blaise?',
                'a': 'The patron saint of Dubrovnik, who is traditionally said to have warned the '
                'city of an attack in the 10th century.',
            },
            {
                'q': 'Is it open to visitors?',
                'a': 'Yes, the processions pass through public streets and squares of the Old '
                'Town.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Dubrovnik Summer Festival',
        'slug': 'dubrovnik-summer-festival',
        'category': 'culture',
        'region': 'dubrovnik',
        'place_slug': 'dubrovnik',
        'venue': 'Open-air stages across Dubrovnik’s Old Town',
        'when_label': 'Mid-July to late August',
        'month': 7,
        'featured': True,
        'summary': 'A summer arts festival of theatre, music and dance on open-air stages in '
        'Dubrovnik’s Old Town.',
        'description': 'The Dubrovnik Summer Festival has been held since 1950 and fills the Old '
        'Town with theatre, classical music, opera and dance for around six weeks. '
        'Performances take place outdoors, on squares, in courtyards and in the '
        'fortress of Lovrijenac, whose setting is used for productions of '
        'Shakespeare’s Hamlet.',
        'highlights': [
            'Open-air theatre, opera and classical music',
            'Performances in historic squares and courtyards',
            'Hamlet at Lovrijenac fortress',
            'Dance and folklore programmes',
        ],
        'faqs': [
            {
                'q': 'When is the Dubrovnik Summer Festival?',
                'a': 'From mid-July to late August, with an opening ceremony in the Old Town.',
            },
            {
                'q': 'Do I need tickets?',
                'a': 'Many performances are ticketed; check the festival’s official site for the '
                'programme.',
            },
            {
                'q': 'Where are the performances held?',
                'a': 'On squares, in palaces and courtyards of the Old Town, and at Lovrijenac '
                'fortress.',
            },
        ],
        'official_url': 'https://www.dubrovnik-festival.hr',
    },
    {
        'name': 'Split Summer Festival',
        'slug': 'split-summer-festival',
        'category': 'culture',
        'region': 'split',
        'place_slug': 'split',
        'venue': 'Peristyle of Diocletian’s Palace and the Croatian National Theatre in Split',
        'when_label': 'Mid-July to mid-August',
        'month': 7,
        'featured': False,
        'summary': 'A summer season of opera, ballet, drama and concerts in Split, centred on the '
        'Peristyle of Diocletian’s Palace.',
        'description': 'The Split Summer Festival (Splitsko ljeto) is organised by the Croatian '
        'National Theatre in Split. Opera, ballet, drama and concerts are staged over '
        'several weeks in July and August, in the theatre and on open-air stages in '
        'the old town, including the Peristyle of Diocletian’s Palace.',
        'highlights': [
            'Opera and ballet productions',
            'Drama and concerts',
            'Open-air stages in the old town',
            'Peristyle of Diocletian’s Palace',
        ],
        'faqs': [
            {'q': 'When is the Split Summer Festival?', 'a': 'From mid-July to mid-August.'},
            {
                'q': 'Where does it take place?',
                'a': 'At the Croatian National Theatre in Split and on open-air stages in the old '
                'town, such as the Peristyle.',
            },
            {
                'q': 'Do I need tickets?',
                'a': 'Most performances need tickets; check the programme on the festival’s '
                'official channels.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Sinjska Alka',
        'slug': 'sinjska-alka',
        'category': 'tradition',
        'region': 'split',
        'place_slug': 'sinj',
        'venue': 'Alka grounds in Sinj',
        'when_label': 'Early August',
        'month': 8,
        'featured': True,
        'summary': 'A knights’ tournament in Sinj commemorating the town’s defence in 1715, on '
        'UNESCO’s heritage list.',
        'description': 'The Sinjska Alka is a competition in which riders in historical costume '
        'gallop down a track and try to put a lance through a small iron ring (the '
        'alka) hung on a rope. It commemorates the victory over the Ottoman army at '
        'Sinj in 1715 and has been held for centuries. It is on UNESCO’s list of '
        'intangible cultural heritage.',
        'highlights': [
            'Riders in historical costume',
            'Lance through the iron ring',
            'Procession of the participants',
            'UNESCO-listed tradition',
        ],
        'faqs': [
            {
                'q': 'When is the Sinjska Alka?',
                'a': 'In early August, usually on the first Sunday of the month.',
            },
            {
                'q': 'What does the Alka commemorate?',
                'a': 'The defence of Sinj against the Ottoman army in 1715.',
            },
            {
                'q': 'How do I get to Sinj?',
                'a': 'By road from Split, about an hour away; there are also buses.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Moreška, Korčula',
        'slug': 'moreska-korcula',
        'category': 'tradition',
        'region': 'dubrovnik',
        'place_slug': 'korcula',
        'venue': 'Korčula Old Town',
        'when_label': 'Summer season, with a performance in late July',
        'month': 7,
        'featured': False,
        'summary': 'A sword dance-drama performed in Korčula, in which the Black and White knights '
        'fight over a princess.',
        'description': 'The Moreška is a sword dance and play performed in Korčula Old Town. Two '
        'armies, the Moors in black and the Christians in white, fight with swords to '
        'the sound of a band, in a story about a rescued princess. It is performed '
        'through the summer, including around the feast of the town’s patron saint, '
        'St Theodore, in late July.',
        'highlights': [
            'Sword fight in choreographed dance',
            'Black and White armies in costume',
            'Live brass band',
            'Performed in the old town',
        ],
        'faqs': [
            {
                'q': 'When can I see the Moreška?',
                'a': 'During the summer season, with a performance around the feast of St Theodore '
                'in late July. Check local schedules.',
            },
            {
                'q': 'What is the Moreška about?',
                'a': 'A fight between Moorish and Christian armies over a princess, told in dance '
                'with swords.',
            },
            {
                'q': 'Is it only in Korčula?',
                'a': 'The Korčula performance is the best-known; the dance has been performed '
                'there for generations.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Pula Film Festival',
        'slug': 'pula-film-festival',
        'category': 'culture',
        'region': 'istria',
        'place_slug': 'pula',
        'venue': 'The Roman amphitheatre (Arena), Pula',
        'when_label': 'Mid-July',
        'month': 7,
        'featured': True,
        'summary': 'Croatia’s national film festival, with screenings in the Roman amphitheatre in '
        'Pula.',
        'description': 'The Pula Film Festival has been held since 1954 and is the main showcase for '
        'Croatian cinema. Screenings are held in the open air in the Roman '
        'amphitheatre, and the programme includes Croatian and international films, '
        'with a national competition.',
        'highlights': [
            'Screenings in the Roman Arena',
            'National competition',
            'Croatian and international films',
            'Open-air atmosphere',
        ],
        'faqs': [
            {
                'q': 'When is the Pula Film Festival?',
                'a': 'Usually in July. The festival announces exact dates each year.',
            },
            {
                'q': 'Where are the screenings?',
                'a': 'In the Roman amphitheatre in Pula and at other venues in town.',
            },
            {
                'q': 'Are the films subtitled?',
                'a': 'Croatian films are usually shown with English subtitles; check the festival '
                'programme.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Motovun Film Festival',
        'slug': 'motovun-film-festival',
        'category': 'culture',
        'region': 'istria',
        'place_slug': 'motovun',
        'venue': 'Motovun hilltop town',
        'when_label': 'Late July',
        'month': 7,
        'featured': False,
        'summary': 'An independent film festival held on a hilltop town in the centre of Istria.',
        'description': 'The Motovun Film Festival began in the late 1990s and brings independent and '
        'short films to the hilltop town of Motovun in inland Istria. Films are '
        'screened in the town square and other venues, and the programme includes '
        'talks and music in the evenings.',
        'highlights': [
            'Open-air screenings',
            'Independent and short films',
            'Talks and music',
            'Hilltop town setting',
        ],
        'faqs': [
            {'q': 'When is the Motovun Film Festival?', 'a': 'In late July, over several days.'},
            {
                'q': 'Where is it held?',
                'a': 'In the old town of Motovun, on a hill in inland Istria.',
            },
            {
                'q': 'How do I get to Motovun?',
                'a': 'By car from Pula, Poreč or Rovinj; public transport is limited.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'INmusic Festival',
        'slug': 'inmusic-festival',
        'category': 'music',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Lake Jarun, Zagreb',
        'when_label': 'Late June',
        'month': 6,
        'featured': False,
        'summary': 'A multi-day open-air music festival on the shore of Lake Jarun in Zagreb.',
        'description': 'INmusic is an annual music festival held in June on the shore of Lake Jarun, '
        'in Zagreb. It runs for several days on a number of stages and has a '
        'programme of rock, alternative and electronic acts, with Croatian and '
        'international performers.',
        'highlights': [
            'Multi-day open-air programme',
            'Several stages',
            'Croatian and international acts',
            'Lakeside setting',
        ],
        'faqs': [
            {'q': 'When is INmusic Festival?', 'a': 'Usually in late June.'},
            {'q': 'Where is it held?', 'a': 'At Lake Jarun, in the south-west of Zagreb.'},
            {
                'q': 'How do I get to Jarun?',
                'a': 'By tram or bus from the centre of Zagreb, or on foot or by bike along the '
                'lake.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Špancirfest',
        'slug': 'spancirfest',
        'category': 'culture',
        'region': 'continental',
        'place_slug': 'varazdin',
        'venue': 'Varaždin old town',
        'when_label': 'Late August to early September',
        'month': 8,
        'featured': True,
        'summary': 'A street festival in Varaždin, with performers, music, crafts and food across '
        'the old town.',
        'description': 'Špancirfest takes over Varaždin’s old town for around ten days in late '
        'summer. Street performers, musicians, craft stalls and food stands fill its '
        'squares and streets, and the festival has concerts and shows in the '
        'evenings. The name comes from the Croatian word for strolling.',
        'highlights': [
            'Street performers and music',
            'Craft stalls and food',
            'Evening concerts',
            'Baroque old town setting',
        ],
        'faqs': [
            {'q': 'When is Špancirfest?', 'a': 'Usually from late August into early September.'},
            {
                'q': 'Is Špancirfest free to attend?',
                'a': 'Most of the street programme is open to the public; check the organisers for '
                'any ticketed concerts.',
            },
            {
                'q': 'How do I get to Varaždin?',
                'a': 'By road or rail from Zagreb, about an hour and a half away.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Varaždin Baroque Evenings',
        'slug': 'varazdin-baroque-evenings',
        'category': 'music',
        'region': 'continental',
        'place_slug': 'varazdin',
        'venue': 'Churches and palaces in Varaždin',
        'when_label': 'Late September to early October',
        'month': 9,
        'featured': False,
        'summary': 'A festival of baroque and early music in the churches and palaces of Varaždin.',
        'description': 'The Varaždin Baroque Evenings (Varaždinske barokne večeri) is a series of '
        'concerts held in autumn in the town’s churches, palaces and other historic '
        'buildings. The programme centres on baroque and early music, performed by '
        'Croatian and visiting ensembles.',
        'highlights': [
            'Baroque and early music',
            'Concerts in historic buildings',
            'Croatian and visiting ensembles',
            'Autumn in the baroque town',
        ],
        'faqs': [
            {
                'q': 'When are the Baroque Evenings?',
                'a': 'In autumn, usually from late September into October.',
            },
            {
                'q': 'Where are the concerts held?',
                'a': 'In the churches, palaces and other historic buildings of Varaždin.',
            },
            {
                'q': 'Do I need tickets?',
                'a': 'Most concerts need tickets; check the festival’s programme.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Advent in Zagreb',
        'slug': 'advent-in-zagreb',
        'category': 'culture',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Squares and parks across central Zagreb',
        'when_label': 'Late November to early January',
        'month': 12,
        'featured': True,
        'summary': 'Zagreb’s Christmas season, with stalls, food, lights and concerts in the squares '
        'and parks of the centre.',
        'description': 'Advent in Zagreb runs from late November into early January. Stalls selling '
        'crafts, food and mulled wine are set up in squares and parks around the '
        'centre, and there are concerts and events throughout the season. Streets and '
        'squares are lit, and the city is busy in the evenings.',
        'highlights': [
            'Christmas stalls in the squares',
            'Food and mulled wine',
            'Concerts and events',
            'Lights in the city centre',
        ],
        'faqs': [
            {'q': 'When is Advent in Zagreb?', 'a': 'From late November to early January.'},
            {
                'q': 'Where is it held?',
                'a': 'At stalls and stages across central Zagreb, including the main square and '
                'the parks.',
            },
            {'q': 'Is it busy?', 'a': 'Evenings and weekends can be crowded; daytime is quieter.'},
        ],
        'official_url': '',
    },
    {
        'name': 'Animafest Zagreb',
        'slug': 'animafest-zagreb',
        'category': 'culture',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Cinemas and venues across Zagreb',
        'when_label': 'June',
        'month': 6,
        'featured': False,
        'summary': 'The World Festival of Animated Film, held in Zagreb every June.',
        'description': 'Animafest Zagreb is an international festival of animated film. Competition '
        'programmes of short and feature animation, retrospectives and talks are '
        'shown at cinemas and other venues in the city. It is one of the long-running '
        'animation festivals in Europe.',
        'highlights': [
            'Short and feature competitions',
            'Retrospectives',
            'Talks and workshops',
            'Venues across the city',
        ],
        'faqs': [
            {'q': 'When is Animafest Zagreb?', 'a': 'In June, over about a week.'},
            {'q': 'Where is it held?', 'a': 'At cinemas and cultural venues in Zagreb.'},
            {
                'q': 'Is it for families?',
                'a': 'The programme includes screenings for children as well as for adults.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Zagreb Film Festival',
        'slug': 'zagreb-film-festival',
        'category': 'culture',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Cinemas across Zagreb',
        'when_label': 'October to November',
        'month': 10,
        'featured': False,
        'summary': 'An autumn international film festival in Zagreb, with a competition and '
        'programmes of new cinema.',
        'description': 'The Zagreb Film Festival is an international festival held in the autumn, '
        'mostly at cinemas in Zagreb. It shows feature films from Croatia and abroad, '
        'with a main competition and other sections, and includes talks with '
        'directors.',
        'highlights': [
            'International feature film competition',
            'Croatian and foreign films',
            'Meetings with filmmakers',
            'Cinemas across the city',
        ],
        'faqs': [
            {
                'q': 'When is the Zagreb Film Festival?',
                'a': 'In autumn, usually in October or November.',
            },
            {'q': 'Where are the screenings?', 'a': 'At cinemas in Zagreb.'},
            {
                'q': 'Are films subtitled in English?',
                'a': 'Foreign films are usually shown in the original with subtitles; check the '
                'programme.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'ZagrebDox',
        'slug': 'zagrebdox',
        'category': 'culture',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Cinemas in Zagreb',
        'when_label': 'Late February to March',
        'month': 3,
        'featured': False,
        'summary': 'An international documentary film festival in Zagreb.',
        'description': 'ZagrebDox is an annual documentary film festival held in Zagreb at the end '
        'of winter. Its competition and other programmes show documentaries from '
        'Croatia and the world in cinemas around the city, with talks and workshops.',
        'highlights': [
            'International documentary competition',
            'Programmes from Croatia and abroad',
            'Talks and workshops',
            'Cinemas across the city',
        ],
        'faqs': [
            {'q': 'When is ZagrebDox?', 'a': 'Usually from late February into March.'},
            {'q': 'Where does it take place?', 'a': 'At cinemas in Zagreb.'},
            {
                'q': 'Are the films subtitled?',
                'a': 'Foreign documentaries are normally shown with subtitles; check the '
                'programme.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Interliber Book Fair',
        'slug': 'interliber-book-fair',
        'category': 'culture',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Zagreb Fair grounds',
        'when_label': 'November',
        'month': 11,
        'featured': False,
        'summary': 'Croatia’s international book fair, held every November at the Zagreb Fair.',
        'description': 'Interliber is a book fair held at the Zagreb Fair grounds. Publishers from '
        'Croatia and neighbouring countries present books, and the programme includes '
        'author meetings, readings and events for children.',
        'highlights': [
            'Publishers’ stands',
            'Author meetings and readings',
            'Events for children',
            'Held at the Zagreb Fair',
        ],
        'faqs': [
            {'q': 'When is Interliber?', 'a': 'Usually in November, over about a week.'},
            {
                'q': 'Where is it held?',
                'a': 'At the Zagreb Fair grounds, south of the city centre.',
            },
            {
                'q': 'Is it only for Croatian books?',
                'a': 'Croatian publishers dominate, but books from neighbouring countries are also '
                'shown.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Museum Night',
        'slug': 'museum-night-zagreb',
        'category': 'culture',
        'region': 'zagreb',
        'place_slug': 'zagreb',
        'venue': 'Museums and galleries across Zagreb',
        'when_label': 'Late January',
        'month': 1,
        'featured': False,
        'summary': 'An evening in late January when museums and galleries stay open late.',
        'description': 'Museum Night (Noć muzeja) is held in late January and takes place in towns '
        'across Croatia. In Zagreb, museums and galleries open in the evening with '
        'special programmes, guided tours and events, and many of them take part.',
        'highlights': [
            'Late opening of museums and galleries',
            'Special tours and events',
            'Programmes across the city',
            'Held in towns across Croatia',
        ],
        'faqs': [
            {'q': 'When is Museum Night?', 'a': 'On a Friday in late January.'},
            {
                'q': 'Which museums take part?',
                'a': 'Many museums and galleries in Zagreb; the list is published before the '
                'event.',
            },
            {'q': 'Is it only in Zagreb?', 'a': 'No, towns across Croatia take part.'},
        ],
        'official_url': '',
    },
    {
        'name': 'Đakovački vezovi',
        'slug': 'dakovacki-vezovi',
        'category': 'tradition',
        'region': 'continental',
        'place_slug': 'dakovo',
        'venue': 'Đakovo town centre',
        'when_label': 'Early July',
        'month': 7,
        'featured': False,
        'summary': 'A folk festival in Đakovo, with parades in traditional costume, music, dance and '
        'embroidery.',
        'description': 'Đakovački vezovi, or Đakovo Embroidery, is a folklore festival held every '
        'summer in Đakovo. Groups in traditional costume from Slavonia and further '
        'afield take part in a parade and perform songs and dances, and embroidery '
        'and other crafts are on show.',
        'highlights': [
            'Parade in folk costume',
            'Folklore performances',
            'Embroidery and crafts',
            'Slavonian music and food',
        ],
        'faqs': [
            {'q': 'When is Đakovački vezovi?', 'a': 'In early July, over several days.'},
            {'q': 'Where is it held?', 'a': 'In Đakovo, in Slavonia.'},
            {'q': 'How do I get to Đakovo?', 'a': 'By road or rail from Osijek or Zagreb.'},
        ],
        'official_url': '',
    },
    {
        'name': 'Vinkovci Autumns',
        'slug': 'vinkovacke-jeseni',
        'category': 'tradition',
        'region': 'continental',
        'place_slug': '',
        'venue': 'Vinkovci',
        'when_label': 'September',
        'month': 9,
        'featured': False,
        'summary': 'A folklore and cultural festival in the Slavonian town of Vinkovci.',
        'description': 'Vinkovačke jeseni, or Vinkovci Autumns, is a long-running festival of '
        'folklore and traditional culture in the Slavonian town of Vinkovci. It '
        'includes a parade, folklore performances, exhibitions and food, and it takes '
        'place in September.',
        'highlights': [
            'Parade and folklore groups',
            'Exhibitions',
            'Slavonian food and music',
            'Held in Vinkovci',
        ],
        'faqs': [
            {'q': 'When are the Vinkovci Autumns?', 'a': 'In September, over several days.'},
            {
                'q': 'Where is Vinkovci?',
                'a': 'In Slavonia, in eastern Croatia, between Osijek and Slavonski Brod.',
            },
            {
                'q': 'Is it a folklore festival?',
                'a': 'Yes, folklore and traditional culture are central to the programme.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Lepoglava Lace Festival',
        'slug': 'lepoglava-lace-festival',
        'category': 'tradition',
        'region': 'continental',
        'place_slug': '',
        'venue': 'Lepoglava',
        'when_label': 'September',
        'month': 9,
        'featured': False,
        'summary': 'A festival in the town of Lepoglava celebrating its traditional lace-making.',
        'description': 'Lepoglava has a centuries-old tradition of making bobbin lace, which is on '
        'UNESCO’s list of intangible cultural heritage. The annual lace festival in '
        'September has demonstrations by lacemakers, exhibitions, sales of lace and '
        'folklore performances.',
        'highlights': [
            'Lacemaking demonstrations',
            'Lace exhibitions',
            'Crafts and folklore',
            'UNESCO-listed lace tradition',
        ],
        'faqs': [
            {'q': 'When is the Lepoglava Lace Festival?', 'a': 'Usually in September.'},
            {
                'q': 'Where is Lepoglava?',
                'a': 'In the Zagorje, in northern Croatia, between Varaždin and Krapina.',
            },
            {
                'q': 'Can I buy lace there?',
                'a': 'Lace and other crafts are sold during the festival.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Rab Medieval Festival (Rapska fjera)',
        'slug': 'rapska-fjera',
        'category': 'tradition',
        'region': 'kvarner',
        'place_slug': 'rab',
        'venue': 'Rab Old Town',
        'when_label': 'Mid-to-late July',
        'month': 7,
        'featured': False,
        'summary': 'A medieval festival in Rab’s old town, with costumed groups, a crossbow '
        'tournament and market stalls.',
        'description': 'Rapska fjera, the Rab Fair, revives the medieval history of the island of '
        'Rab. Costumed groups, knights and craftspeople fill the old town, and there '
        'is a crossbow tournament, a market and performances over a few days in July.',
        'highlights': [
            'Costumed groups and parades',
            'Crossbow tournament',
            'Medieval market stalls',
            'Old town setting',
        ],
        'faqs': [
            {
                'q': 'When is Rapska fjera?',
                'a': 'In July, over a few days; the town announces exact dates.',
            },
            {
                'q': 'Where is it held?',
                'a': 'In the old town of Rab, on the island of the same name.',
            },
            {
                'q': 'Is it suitable for children?',
                'a': 'Yes, the town fills with costumed performers and stalls that appeal to '
                'families.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Zigante Truffle Days',
        'slug': 'zigante-truffle-days',
        'category': 'food',
        'region': 'istria',
        'place_slug': '',
        'venue': 'Livade, inland Istria',
        'when_label': 'Autumn',
        'month': 10,
        'featured': False,
        'summary': 'An autumn festival of truffles in the Istrian village of Livade.',
        'description': 'Zigante Truffle Days take place in Livade, in the Motovun forest area of '
        'inland Istria. The village is known for its white truffles, and the event '
        'offers tastings, a market, food stalls and demonstrations through the '
        'truffle season in autumn.',
        'highlights': [
            'Truffle tastings',
            'Market and food stalls',
            'Demonstrations',
            'Istrian wine and food',
        ],
        'faqs': [
            {
                'q': 'When are the Zigante Truffle Days?',
                'a': 'In autumn, during the truffle season.',
            },
            {'q': 'Where are they held?', 'a': 'In Livade, near Motovun in inland Istria.'},
            {
                'q': 'How do I get there?',
                'a': 'By car from Poreč, Pula or Rovinj; public transport is limited.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Grisia Art Fair',
        'slug': 'grisia-rovinj',
        'category': 'culture',
        'region': 'istria',
        'place_slug': 'rovinj',
        'venue': 'Grisia street, Rovinj',
        'when_label': 'August',
        'month': 8,
        'featured': False,
        'summary': 'An open-air art exhibition held on Grisia street in the old town of Rovinj.',
        'description': 'Grisia is a narrow cobbled street in Rovinj’s old town, lined with '
        'galleries. Once a year, in August, artists display paintings and drawings '
        'along the street and sell their work in an open-air exhibition.',
        'highlights': [
            'Open-air art exhibition',
            'Artists from the area',
            'Galleries on Grisia street',
            'Rovinj old town setting',
        ],
        'faqs': [
            {
                'q': 'When is the Grisia art fair?',
                'a': 'In August, usually on a single day; check local dates.',
            },
            {
                'q': 'Where is Grisia?',
                'a': 'A street in the old town of Rovinj, leading up to the church of St Euphemia.',
            },
            {
                'q': 'Can I buy art there?',
                'a': 'Artists sell their paintings and drawings directly.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Šibenik International Children’s Festival',
        'slug': 'sibenik-childrens-festival',
        'category': 'culture',
        'region': 'sibenik',
        'place_slug': 'sibenik',
        'venue': 'Šibenik old town',
        'when_label': 'Late June to early July',
        'month': 6,
        'featured': False,
        'summary': 'A festival of theatre, music and workshops for children in Šibenik.',
        'description': 'The Šibenik International Children’s Festival (Međunarodni dječji festival '
        'Šibenik) is a festival of theatre, music, film and workshops for children. '
        'It takes place in the old town of Šibenik, with performers from Croatia and '
        'abroad.',
        'highlights': [
            'Children’s theatre and music',
            'Workshops',
            'Performances in the old town',
            'Programmes for families',
        ],
        'faqs': [
            {'q': 'When is the festival?', 'a': 'From late June to early July.'},
            {
                'q': 'Where is it held?',
                'a': 'In the old town of Šibenik, with events at several venues.',
            },
            {
                'q': 'Is it only for children?',
                'a': 'Mainly, though families and adults also attend performances.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Lavender Festival, Velo Grablje',
        'slug': 'lavender-festival-velo-grablje',
        'category': 'tradition',
        'region': 'split',
        'place_slug': 'hvar',
        'venue': 'Velo Grablje, Hvar',
        'when_label': 'June',
        'month': 6,
        'featured': False,
        'summary': 'A festival of lavender in the village of Velo Grablje on the island of Hvar.',
        'description': 'Hvar is known for its lavender, which blooms in early summer. In Velo '
        'Grablje, a village in the hills above Hvar town, a lavender festival is held '
        'in June, with stalls selling lavender products, crafts, food and local wine, '
        'and demonstrations of lavender distillation.',
        'highlights': [
            'Lavender products and crafts',
            'Distillation demonstrations',
            'Local food and wine',
            'Village in the hills of Hvar',
        ],
        'faqs': [
            {'q': 'When is the lavender festival?', 'a': 'In June, when the lavender is in bloom.'},
            {
                'q': 'Where is Velo Grablje?',
                'a': 'In the hills of the island of Hvar, above Hvar town.',
            },
            {
                'q': 'How do I get there?',
                'a': 'By car or taxi from Hvar town; the roads in the hills are narrow.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Music Evenings in St Donatus',
        'slug': 'music-evenings-st-donatus',
        'category': 'music',
        'region': 'zadar',
        'place_slug': 'zadar',
        'venue': 'Church of St Donatus, Zadar',
        'when_label': 'Summer',
        'month': 7,
        'featured': False,
        'summary': 'A summer series of classical and early music in the church of St Donatus in '
        'Zadar.',
        'description': 'The Music Evenings in St Donatus (Glazbene večeri u sv. Donatu) is a summer '
        'series of concerts held in the round pre-Romanesque church of St Donatus, in '
        'Zadar. The church is known for its acoustics, and the programme includes '
        'early and classical music.',
        'highlights': [
            'Concerts in a historic church',
            'Early and classical music',
            'Known acoustics',
            'Zadar old town setting',
        ],
        'faqs': [
            {
                'q': 'When are the Music Evenings in St Donatus?',
                'a': 'In summer, usually in July and August.',
            },
            {'q': 'Where is the church?', 'a': 'In the old town of Zadar, on the Roman Forum.'},
            {
                'q': 'Do I need tickets?',
                'a': 'Concerts are ticketed; check the programme in advance.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Vinistra',
        'slug': 'vinistra-porec',
        'category': 'food',
        'region': 'istria',
        'place_slug': 'porec',
        'venue': 'Poreč',
        'when_label': 'May',
        'month': 5,
        'featured': False,
        'summary': 'An international wine exhibition in Poreč, showing the wines of Istria and the '
        'region.',
        'description': 'Vinistra is a wine exhibition held in Poreč in May. Winemakers from Istria '
        'and elsewhere present their wines to the public and the trade, with tastings '
        'and a competition.',
        'highlights': [
            'Istrian wine tastings',
            'Winemakers from the region',
            'Wine competition',
            'Held in Poreč',
        ],
        'faqs': [
            {'q': 'When is Vinistra?', 'a': 'In May.'},
            {'q': 'Where is it held?', 'a': 'In Poreč, on the west coast of Istria.'},
            {
                'q': 'Is it open to the public?',
                'a': 'Yes, the exhibition and tastings are open to visitors.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Feast of St Domnius',
        'slug': 'feast-of-st-domnius-split',
        'category': 'tradition',
        'region': 'split',
        'place_slug': 'split',
        'venue': 'Split old town',
        'when_label': 'Early May',
        'month': 5,
        'featured': False,
        'summary': 'Split’s annual feast for its patron saint, with a procession and street stalls.',
        'description': 'The Feast of St Domnius (Sveti Duje) is the day of the patron saint of '
        'Split. A Mass in the cathedral, in the former mausoleum of Diocletian, is '
        'followed by a procession through the old town and a day of stalls and street '
        'events.',
        'highlights': [
            'Mass at the cathedral',
            'Procession through the old town',
            'Street stalls',
            'City holiday',
        ],
        'faqs': [
            {'q': 'When is the Feast of St Domnius?', 'a': 'On 7 May each year.'},
            {
                'q': 'Where does it take place?',
                'a': 'In Split’s old town, around the cathedral and the Peristyle.',
            },
            {
                'q': 'Is it a public holiday in Split?',
                'a': 'It is a local holiday in the city; shops and offices may be closed.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Karlovac Beer Days',
        'slug': 'karlovac-beer-days',
        'category': 'food',
        'region': 'continental',
        'place_slug': 'karlovac',
        'venue': 'Karlovac',
        'when_label': 'Late summer',
        'month': 8,
        'featured': False,
        'summary': 'A beer festival in Karlovac, a city with a long brewing tradition.',
        'description': 'The Days of Beer (Dani piva) in Karlovac is a festival held in late summer. '
        'There are tastings of Croatian and other beers, live music and food in the '
        'city centre, in a town known for its brewing tradition.',
        'highlights': ['Beer tastings', 'Live music', 'Food stands', 'Held in the city centre'],
        'faqs': [
            {
                'q': 'When are the Days of Beer in Karlovac?',
                'a': 'In late summer, usually in August or early September.',
            },
            {'q': 'Where is it held?', 'a': 'In the centre of Karlovac.'},
            {
                'q': 'How do I get to Karlovac?',
                'a': 'By road or rail from Zagreb, about an hour away.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Festival of Dalmatian Klapa Singing, Omiš',
        'slug': 'omis-klapa-festival',
        'category': 'music',
        'region': 'split',
        'place_slug': 'omis',
        'venue': 'Omiš old town',
        'when_label': 'July',
        'month': 7,
        'featured': False,
        'summary': 'A festival of Dalmatian klapa, the unaccompanied male and mixed vocal groups of '
        'the coast.',
        'description': 'The Festival of Dalmatian Klapa Singing in Omiš is a competition and '
        'showcase of klapa singing, the a cappella vocal tradition of Dalmatia, which '
        'is on UNESCO’s list of intangible cultural heritage. Groups perform in the '
        'old town in July.',
        'highlights': [
            'Klapa groups performing live',
            'Open-air stages in the old town',
            'Dalmatian songs',
            'UNESCO-listed tradition',
        ],
        'faqs': [
            {
                'q': 'When is the Omiš klapa festival?',
                'a': 'In July; the town announces exact dates.',
            },
            {
                'q': 'What is klapa?',
                'a': 'A Dalmatian tradition of unaccompanied vocal harmony, sung by groups of men '
                'or women or mixed groups.',
            },
            {'q': 'Where is Omiš?', 'a': 'On the coast of Dalmatia, between Split and Makarska.'},
        ],
        'official_url': '',
    },
    {
        'name': 'Croatia Open Umag',
        'slug': 'croatia-open-umag',
        'category': 'sport',
        'region': 'istria',
        'place_slug': 'umag',
        'venue': 'ITC Stella Maris, Umag',
        'when_label': 'July',
        'month': 7,
        'featured': False,
        'summary': 'A professional men’s tennis tournament on clay in the Istrian town of Umag.',
        'description': 'The Croatia Open Umag is a men’s tennis tournament on the ATP Tour, played '
        'on clay courts in Umag in July. It has been played there for many years, and '
        'the players include top-ranked names from the circuit.',
        'highlights': [
            'ATP Tour tennis on clay',
            'International players',
            'Seaside setting',
            'Held in July',
        ],
        'faqs': [
            {'q': 'When is the Croatia Open Umag?', 'a': 'In July, over about a week.'},
            {
                'q': 'Where is it played?',
                'a': 'At a tennis centre in Umag, on the west coast of Istria.',
            },
            {
                'q': 'Do I need tickets?',
                'a': 'Yes, matches are ticketed; check the tournament’s official channels.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Vukovar Remembrance Day',
        'slug': 'vukovar-remembrance-day',
        'category': 'tradition',
        'region': 'continental',
        'place_slug': 'vukovar',
        'venue': 'Vukovar',
        'when_label': '18 November',
        'month': 11,
        'featured': False,
        'summary': 'The annual day of remembrance for the victims of the fall of Vukovar in 1991.',
        'description': 'Each year on 18 November, people walk in remembrance in Vukovar, from the '
        'hospital to the Memorial Cemetery, in a column called Kolona sjećanja. It '
        'marks the fall of the city in 1991 after a siege of about three months. It '
        'is a solemn event, and thousands of visitors take part from across Croatia.',
        'highlights': [
            'Remembrance walk to the Memorial Cemetery',
            'Candles and wreaths',
            'Observed across Croatia',
            'A solemn day',
        ],
        'faqs': [
            {'q': 'When is Vukovar Remembrance Day?', 'a': 'On 18 November each year.'},
            {
                'q': 'What happens?',
                'a': 'A silent walk from the Vukovar hospital to the Memorial Cemetery, with '
                'candles and wreaths.',
            },
            {
                'q': 'Can visitors take part?',
                'a': 'Yes, visitors are welcome to join respectfully.',
            },
        ],
        'official_url': '',
    },
    {
        'name': 'Za križen, Hvar',
        'slug': 'za-krizen-hvar',
        'category': 'tradition',
        'region': 'split',
        'place_slug': '',
        'venue': 'Villages of central Hvar',
        'when_label': 'Holy Week',
        'month': 4,
        'featured': False,
        'summary': 'A Holy Thursday night procession on Hvar, in which crossbearers walk between '
        'villages. UNESCO-listed.',
        'description': 'Za križen, or “behind the cross”, is a Holy Week procession on the island of '
        'Hvar. On the night of Holy Thursday, men carrying crosses walk from six '
        'villages in the centre of the island and return by dawn, in silence and with '
        'hymns. It is on UNESCO’s list of intangible cultural heritage.',
        'highlights': [
            'Overnight procession of crossbearers',
            'Villages of central Hvar',
            'Hymns and silence',
            'UNESCO-listed tradition',
        ],
        'faqs': [
            {
                'q': 'When is Za križen?',
                'a': 'On the night of Holy Thursday, in Holy Week before Easter.',
            },
            {
                'q': 'Where does it take place?',
                'a': 'In the villages of central Hvar, including Jelsa and Vrisnik.',
            },
            {
                'q': 'Can visitors watch?',
                'a': 'Yes, but it is a religious observance, so visitors are asked to be quiet and '
                'respectful.',
            },
        ],
        'official_url': '',
    },
]
