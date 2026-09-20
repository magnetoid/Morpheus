"""Seed real Montenegro travel-blog articles and retire the core "dot books"
journal filler (idempotent).

`/journal/` renders published CMS pages tagged `metadata.category='journal'`
(see storefront.views.content.journal_index + cms.services.list_journal_entries).
Out of the box the Montenegro deployment inherited core morpheus's sample
bookstore articles ("the case for the small press", …). This publishes genuine
Montenegro travel articles and unpublishes the known core ones by slug — user-
authored journal pages are never touched.

    python manage.py seed_journal_montenegro
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

# Core "dot books" journal slugs to retire on this deployment (explicit list so
# any journal pages the merchant creates are left alone).
CORE_JOURNAL_SLUGS = [
    'a-short-note-on-patience',
    'why-we-dont-carry-books-we-havent-read',
    'the-case-for-the-small-press',
    'why-pride-and-prejudice-still-wins',
    'on-finally-reading-war-and-peace',
    'dracula-is-a-paperwork-novel',
    'moby-dick-gets-longer-the-longer-you-spend-with-it',
    'the-great-gatsby-in-2026',
    'jane-eyre-on-her-own-terms',
    'little-women-is-sneakier-than-you-remember',
    'the-count-of-monte-cristo-is-the-original-page-turner',
]

# Byline for the Montenegro travel journal — surfaced on-page (E-E-A-T) and in
# the Article JSON-LD via metadata.author.
AUTHOR = 'Marko Milosavljevic'

# (slug, title, excerpt, body HTML). Newest first — publish_at staggered back.
ARTICLES = [
    (
        'perast-our-lady-of-the-rocks',
        'Perast and Our Lady of the Rocks: The Bay of Kotor’s Baroque Jewel',
        'The most beautiful small town on the bay — a car-free stone waterfront, two '
        'island churches, and a short boat ride you won’t forget.',
        "<p>If Kotor is the bay's fortress, Perast is its drawing room. A single "
        'baroque waterfront of honey-coloured palazzi curves along the water beneath '
        "St. Nicholas' bell tower, with no cars and no beach — you swim straight off "
        'the rocks and the jetties. It is tiny, walkable end to end in ten minutes, '
        'and best in the golden hour when the stone glows and the day-trippers '
        'thin.</p>'
        '<h2>Our Lady of the Rocks and St. George</h2><p>Two islands float just offshore. Our Lady of the Rocks is man-made — for '
        'six centuries sailors have dropped stones here after safe voyages, building '
        'an islet beneath a blue-domed church whose museum is hung with silver '
        'votive plaques and a famous embroidered icon. Its natural twin, St. George, '
        'holds a cypress-shaded monastery closed to visitors but unforgettable from '
        'the water.</p>'
        '<h2>What to see and do in Perast</h2><p>Take one of the little boats from the waterfront (a few minutes each '
        'way), climb the bell tower for the classic view down the bay, and stay for '
        "a slow seafood dinner as the light goes. If you're here on 22 July, the "
        'fašinada procession of decorated boats is the bay at its most magical.</p>',
    ),
    (
        'ostrog-monastery-pilgrimage',
        'Ostrog Monastery: Montenegro’s Cliff-Face Sanctuary',
        'Carved into a sheer white rock face high above the Zeta valley, Ostrog is '
        'the Balkans’ great pilgrimage site — and an astonishing day trip.',
        '<p>Nothing quite prepares you for the first sight of the Upper Monastery: a '
        'whitewashed shrine set directly into a vertical cliff, as if pressed into '
        'the rock by hand. Founded in the 17th century around St. Basil of Ostrog, it '
        'draws pilgrims of every faith — Orthodox, Catholic and Muslim alike — who '
        "come to the two cave churches and the saint's relics.</p>"
        '<h2>The pilgrimage climb to the Upper Monastery</h2><p>The approach is half the experience: a road of tight hairpins climbs from '
        'the valley to the lower monastery, and the devout walk the final stretch '
        'uphill, some barefoot. Dress modestly (shoulders and knees covered), come '
        'early to beat both the heat and the crowds, and take a moment on the terrace '
        'for the enormous view back down the green Bjelopavlići plain.</p>'
        '<h2>How to visit Ostrog</h2><p>Ostrog sits roughly between Podgorica and Nikšić, an easy half-day from '
        'the coast or the northern mountains. Pair it with a lunch stop in the valley '
        "and you have one of Montenegro's most memorable — and most moving — days "
        'out, whatever your beliefs.</p>',
    ),
    (
        'cetinje-old-royal-capital',
        'Cetinje: Inside Montenegro’s Old Royal Capital',
        'The cradle of Montenegrin statehood — royal palaces, historic embassies and '
        'clear mountain air, half an hour above the coast.',
        '<p>Before Podgorica there was Cetinje, tucked in a high karst field beneath '
        'Mount Lovćen. For centuries this small, dignified town was the seat of '
        "Montenegro's prince-bishops and then its kings, and it still feels like a "
        'capital in miniature — low pastel streets, plane trees, and far more history '
        'than its size suggests.</p>'
        "<h2>What to see in Cetinje</h2><p>The set pieces cluster within a few walkable blocks: King Nikola's "
        'modest palace, now a museum of the royal era; the Cetinje Monastery, '
        'guardian of remarkable relics; and the Billiard House (Biljarda), home of '
        'the poet-ruler Njegoš. The grand old buildings that housed foreign '
        'embassies a century ago now serve as museums, academies and schools.</p>'
        '<h2>Cetinje and Lovćen National Park</h2><p>Cetinje makes an easy, cultured contrast to the beaches — cool, quiet and '
        "unhurried. It's also the gateway to Lovćen National Park, so many visitors "
        "climb from here to Njegoš's mountain-top mausoleum and drop down the "
        'serpentine to Kotor to finish the day by the sea.</p>',
    ),
    (
        'ulcinj-southern-beaches',
        'Ulcinj and the Southern Beaches: Montenegro’s Wild South',
        'An Ottoman old town above the sea, the 12-kilometre Velika Plaža, and the '
        'free-spirited river island of Ada Bojana.',
        '<p>The far south feels like a different country — hotter, wider and more '
        'relaxed than the bays up north, with a distinct Albanian-Montenegrin '
        "character. Ulcinj's old town rises on a rocky headland above the Adriatic, a "
        'warren of stone lanes and ramparts with a long, salty history of sailors '
        'and, once, pirates. Minarets and church towers share the same skyline.</p>'
        '<h2>Velika Plaža and the southern sands</h2><p>Below the town, little Mala Plaža fills fast in summer; the real prize is '
        "Velika Plaža, 'Long Beach' — twelve kilometres of open sand running toward "
        "the Albanian border, shallow and warm, and one of the Adriatic's best "
        'kitesurfing spots when the afternoon wind gets up.</p>'
        '<h2>Ada Bojana and the river’s edge</h2><p>At the very end lies Ada Bojana, a triangular island cradled between the '
        'river and the sea, long a byword for laid-back, clothing-optional beach life '
        'and lined with wooden fish restaurants built out over the water. Come for '
        'the sunset and a plate of fresh river fish; there is no better place to end '
        'a trip down the coast.</p>',
    ),
    (
        'njegusi-lovcen-food-and-mausoleum',
        'Njeguši and the Lovćen Road: Pršut, Cheese and a Mountain Mausoleum',
        'The switchback road above Kotor climbs to a national park, a legendary food '
        'village, and Njegoš’s tomb on the roof of Montenegro.',
        "<p>The old road out of Kotor is one of Europe's great short drives: twenty-"
        'five numbered hairpins stacked up the mountainside, each one opening a wider '
        'view over the bay until the whole fjord lies spread out silver below you. '
        'Take it slowly, stop often, and let faster locals pass.</p>'
        '<h2>Njeguši: pršut and mountain cheese</h2><p>Near the top sits Njeguši, an unassuming stone village with an outsized '
        'reputation. This is the ancestral home of the Petrović dynasty that ruled '
        'Montenegro, and the birthplace of its two national foods — pršut, the '
        'air-dried smoked ham cured in these mountain drafts, and a sharp local '
        'cheese. Half the village serves both; stop and eat.</p>'
        '<h2>Lovćen and the Njegoš Mausoleum</h2><p>From there, Lovćen National Park crowns the range. A road (and 461 steps) '
        'leads to the mausoleum of Petar II Petrović-Njegoš — poet, philosopher and '
        'prince-bishop — perched on the peak of Jezerski vrh. On a clear day the '
        'terrace behind the tomb takes in a staggering sweep of the country, from the '
        'coast to the far northern mountains.</p>',
    ),
    (
        'when-to-visit-montenegro-seasonal-guide',
        'When to Visit Montenegro: A Season-by-Season Guide',
        'Beaches in August, wildflowers in May, skiing in January — how to time your '
        'trip to the coast, the mountains and everything between.',
        "<p>Montenegro packs alps and Adriatic into a few hours' drive, so the best "
        "time to come depends on what you're chasing. High summer (July and August) "
        'is beach season: hot days, warm sea and lively coastal towns — but also the '
        'busiest and priciest, so book accommodation and Bay of Kotor boat trips well '
        'ahead.</p>'
        "<h2>Spring and autumn: the shoulder seasons</h2><p>The shoulder months are the connoisseur's choice. May and June bring "
        'wildflowers, full rivers and green mountains with comfortable walking '
        'weather; September and early October keep the sea warm enough to swim while '
        'the crowds fade and the light turns golden. These are the sweet spots for '
        'combining coast and mountains in one trip.</p>'
        '<h2>Winter: skiing and a quiet coast</h2><p>Winter is quieter but far from closed: Žabljak and Kolašin become '
        "Montenegro's ski resorts, the coast stays mild if subdued, and pilgrimage "
        'and heritage sites like Ostrog and Cetinje welcome visitors year-round. Two '
        'timing notes for the active: Tara Canyon rafting is at its wildest during '
        'the late-spring snowmelt, and the olive harvest colours the southern groves '
        'through autumn.</p>',
    ),
    (
        '48-hours-in-kotor',
        '48 Hours in Kotor: The Perfect Bay of Kotor Weekend',
        'How to spend two unforgettable days in the walled old town — from the '
        'fortress climb at dawn to sunset in Perast.',
        '<p>Kotor rewards the early riser. Start before the cruise crowds with the '
        'climb to the Fortress of San Giovanni — 1,350 steps switchbacking up the '
        'mountainside to the classic view over the fjord-like bay. Go at first light, '
        "carry water, and you'll have the ramparts almost to yourself.</p>"
        '<h2>Day one: the old town and Perast</h2><p>Spend the rest of day one inside the Venetian walls: the maze of stone '
        "lanes, St. Tryphon's Cathedral, the maritime museum, and a long lunch of "
        'fresh Adriatic fish. As the afternoon cools, drive (or boat) the short '
        'distance to Perast — a single baroque waterfront facing the two island '
        'churches of Our Lady of the Rocks. Take the little boat out, then stay for '
        'a sunset dinner by the water.</p>'
        '<h2>Day two: the bay and the Lovćen road</h2><p>Day two belongs to the bay itself. A morning kayak or small-boat cruise '
        'gets you into the quiet corners — the sunken submarine tunnels, the Blue '
        'Cave, hidden swimming coves. Back on land, wind up the Lovćen serpentine '
        'for pršut and cheese in the mountain village of Njeguši before the drive '
        'home.</p>',
    ),
    (
        'rafting-the-tara-canyon',
        'Rafting the Tara Canyon: Inside Europe’s Deepest Gorge',
        'What to expect on the emerald Tara — the second-deepest river canyon on '
        'earth, and Montenegro’s greatest adventure day out.',
        '<p>The Tara has carved 1,300 metres down through the Durmitor massif, and '
        'the only way to feel that scale is from the water. A half-day raft on the '
        'gentler lower section suits families and first-timers; the full-day run '
        'through the upper rapids in late spring, when the snowmelt is high, is the '
        'real thing.</p>'
        '<h2>The canyon and the water</h2><p>The water is astonishingly clear and cold — this is one of the cleanest '
        'rivers in Europe, drinkable straight from the side channels. Between rapids '
        'the canyon walls tower in silence, broken only by waterfalls dropping '
        'straight into the current. Most trips start near the Đurđevića Tara bridge, '
        'itself worth the stop for the view (and the zipline, if you dare).</p>'
        "<h2>What to bring rafting the Tara</h2><p>Bring a change of clothes, secure your shoes, and don't worry about "
        'experience — guides handle the technical lines and the wetsuits keep you '
        "warm. It's the kind of day that reframes the whole trip.</p>",
    ),
    (
        'budva-riviera-first-timer-guide',
        'A First-Timer’s Guide to the Budva Riviera',
        'Beaches, a walled old town and the liveliest nightlife on the coast — how '
        'to make the most of Montenegro’s central Adriatic.',
        '<p>Budva packs a lot into a small stretch of coast. The walled old town — a '
        "miniature of Kotor's, jutting into the sea — is best at dusk, when the day "
        'crowds thin and the stone glows. Climb the citadel for the view, then lose '
        'an hour in the lanes.</p>'
        '<h2>The best beaches on the Budva Riviera</h2><p>The beaches fan out on either side. Mogren, tucked below the old town, is '
        'the prettiest; head south toward Sveti Stefan — that postcard islet of '
        'terracotta roofs — for calmer swimming and long coastal walks. Rent a '
        'sun-lounger, or find a quieter cove by scooter.</p>'
        '<h2>Budva after dark</h2><p>After dark, Budva earns its reputation. The old-town bars fill first, '
        'then the beach clubs along the Slovenska Plaža strip run late. Prefer '
        'something slower? Perast and Kotor are a short drive north for a quiet '
        'seafood dinner instead.</p>',
    ),
    (
        'lake-skadar-wine-and-birds',
        'Lake Skadar: Montenegro’s Wine Country and Birdwatching Paradise',
        'The Balkans’ largest lake is a national park of lily-covered water, island '
        'monasteries and family vineyards. Here’s how to explore it.',
        '<p>Lake Skadar is where Montenegro slows down. Half of it spills into '
        'Albania; the Montenegrin shore is a national park of reed beds, water '
        "lilies and one of Europe's richest bird habitats — Dalmatian pelicans, "
        'pygmy cormorants, herons. A morning boat safari from Virpazar or Rijeka '
        'Crnojevića is the classic introduction.</p>'
        '<h2>Crmnica wine country</h2><p>The hills around the lake are the heart of the Crmnica wine region, home '
        "of Montenegro's native Vranac and Krstač grapes. Family cellars welcome "
        'visitors for tastings straight from the barrel, usually with a spread of '
        'local ham, cheese and smoked carp.</p>'
        "<h2>The Rijeka Crnojevića viewpoint</h2><p>Don't miss the viewpoint above Rijeka Crnojevića, where the river coils "
        'in a perfect S-bend through green hills — one of the most photographed '
        'scenes in the country, and best in the soft light of early morning.</p>',
    ),
    (
        'durmitor-in-a-day',
        'Durmitor in a Day: Hiking the Black Lake and Beyond',
        'A UNESCO massif of 48 peaks and eighteen glacial lakes. How to see the '
        'best of Durmitor National Park on a single day from Žabljak.',
        "<p>Base yourself in Žabljak, Montenegro's highest town, and the whole park "
        'is on your doorstep. The gentle introduction is the Black Lake (Crno '
        'jezero) — a 3.5 km forest loop around still, dark water beneath the peaks, '
        'easy enough for anyone and stunning in the morning calm.</p>'
        '<h2>Higher trails: Škrčka lakes and Bobotov Kuk</h2><p>With more time and stronger legs, push higher: the trail toward the '
        'Škrčka lakes or up toward Bobotov Kuk, the highest summit, opens into '
        "alpine meadows and those glacial 'mountain eyes' the range is famous for. "
        'Weather turns fast up here — carry layers even in summer.</p>'
        '<h2>Ending the day in Žabljak</h2><p>Round the day off on the drive back via the Đurđevića Tara bridge, or '
        'with a bowl of hearty mountain food in town. In winter the same slopes '
        "become Montenegro's main ski area.</p>",
    ),
    (
        'coastal-road-herceg-novi-to-ulcinj',
        'The Coastal Road: Driving from Herceg Novi to Ulcinj',
        'The whole Montenegrin coast in one unforgettable drive — bays, beaches, '
        'old towns and the long sands of the south.',
        "<p>Montenegro's coast is barely 100 kilometres end to end, which makes it "
        'one of the great short road trips in Europe. Start in the north at Herceg '
        "Novi, the sunny 'city of stairs' guarding the mouth of the Bay of Kotor, "
        'and work your way south.</p>'
        "<h2>The central coast: Kotor to Sveti Stefan</h2><p>The road hugs the water past Tivat's superyacht marina, over to Kotor "
        'and Perast, then out to the open Adriatic at Budva and Sveti Stefan. Every '
        'headland opens a new bay; every town is worth a stop. Give yourself far '
        'more time than the distance suggests — the point is to pull over often.</p>'
        '<h2>The wild south: Bar and Ulcinj</h2><p>The south feels different: wider, hotter, quieter. Bar has the haunting '
        'ruins of Stari Bar and thousand-year-old olive groves; Ulcinj, the most '
        'southerly town, has an atmospheric old town above the sea and Velika Plaža '
        '— a 12 km sweep of sand to finish the journey.</p>',
    ),
    (
        'boat-fishing-in-kotor',
        "Boat Fishing in Kotor Bay: A Local Angler's Guide",
        'Discover the best boat fishing spots in Kotor Bay. From deep-sea trolling to shore casting, learn where the locals fish, what gear you need, and how to book a guided fishing tour.',
        "<h2>The Bay of Kotor: A Fisherman's Secret</h2><p>The Bay of Kotor isn't just a UNESCO World Heritage site — it's one of the Adriatic's best-kept fishing secrets. The deep fjord-like waters, fed by submarine springs and protected from open-sea currents, create a unique ecosystem where Mediterranean and freshwater species overlap. You'll find sea bass, dentex, amberjack, and even bluefin tuna passing through the channel in late summer.</p><h2>Where the Locals Cast</h2><p>Skip the tourist piers. Head to the fishing village of Muo, where the dock extends into 40-metre-deep water — ideal for bottom fishing. The old submarine tunnels near Rose are legendary for squid at dusk. For fly fishing, the shallow lagoon at Tivat's Solila Nature Reserve holds sea bream and mullet. Local boat captains in Prčanj offer half-day trips from €60 per person, all gear included.</p><h2>Boat Fishing Tours: What to Book</h2><p>Three types of charters dominate the bay. <strong>Half-day trolling trips</strong> (€50-80) target pelagic fish — amberjack, bonito, mackerel. <strong>Full-day big game charters</strong> (€250-400) chase tuna and swordfish in the open Adriatic beyond the Verige strait. <strong>Night squid trips</strong> (€30-50) are the hidden gem — the bay lights up with phosphorescence and the catch is yours to grill at a waterfront konoba.</p><h2>When to Go</h2><p>June to September is peak season. May brings spawning sea bass close to shore. October-November is trophy season — the largest dentex and grouper are caught as waters cool. Avoid August afternoons: the bay gets crowded with cruise ships, sending fish deep.</p><h2>Gear You'll Need</h2><p>Most charters provide rods and tackle. If bringing your own: a 20-30 lb spinning rod covers inshore work, while 50-80 lb stand-up gear handles offshore trolling. Silver casting jigs (60-100g) and Rapala X-Rap Magnum 14s are local favourites. Bait shops in Kotor's Old Town stock live shrimp and squid from €5 per pack.</p><h2>The Catch-and-Cook Experience</h2><p>The best part: your catch becomes dinner. Most captains arrange for a waterfront restaurant to prepare it — typically grilled over olive wood with blitva (Swiss chard) and potatoes. Kostanjica and Ljuta have the best fish konobas. A 2 kg dentex feeds four, and the restaurant charges just €8-12 per person.</p><h2>Practical Tips</h2><ul><li>Book through your hotel concierge or direct with captains at the Kotor marina — avoid booking.com middlemen adding 25%</li><li>Fishing licenses: included in charter prices, but solo shore anglers need a €15 annual permit from the Harbour Master's office</li><li>Bring a waterproof jacket even in summer — the bura wind can whip through the bay without warning</li><li>Tipping 10% to the captain is standard if you land fish and the crew cleans your catch</li></ul>",
    ),
]


class Command(BaseCommand):
    help = (
        'Publish Montenegro travel-blog journal articles; retire core dot-books ones. Idempotent.'
    )

    def handle(self, *args, **options):
        from plugins.installed.cms.models import Page

        # Unpublish the known core "dot books" journal pages — off-brand
        # book-vertical demo content with no place on the Montenegro site.
        # UNPUBLISH, never delete: this command's contract (docstring above) is
        # to retire them, and a seeder that destroys CMS rows takes the
        # merchant's own later edits with them and cannot be undone. Retiring is
        # reversible from the dashboard. `update()` is safe for this particular
        # write: cms.Page has no pre/post_save receivers, and its `save()`
        # override only sanitises `body`, which a state-only flip never touches.
        retired = (
            Page.objects.filter(slug__in=CORE_JOURNAL_SLUGS)
            .exclude(state='draft')
            .update(state='draft')
        )

        now = timezone.now()
        created = republished = 0
        for i, (slug, title, excerpt, body) in enumerate(ARTICLES):
            page, was_created = Page.objects.get_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'excerpt': excerpt[:300],
                    'body': body,
                    'state': 'published',
                    'publish_at': now - timedelta(days=i),
                    'metadata': {'category': 'journal', 'author': AUTHOR},
                },
            )
            if was_created:
                created += 1
                continue
            # Ensure existing rows are published + tagged journal.
            dirty = []
            # One-time structure backfill: push the H2-subheaded body into any
            # article still carrying the old flat (no-<h2>) seed. Gated on the
            # absence of <h2> so a merchant's later manual edits are never
            # clobbered, and a re-run after backfill is a no-op.
            if '<h2' not in (page.body or ''):
                page.body = body
                dirty.append('body')
            if page.state != 'published':
                page.state = 'published'
                dirty.append('state')
            # Backfill category + byline. Author only when unset, so a merchant's
            # manually-attributed post is never overwritten.
            md = dict(page.metadata or {})
            meta_changed = False
            if md.get('category') != 'journal':
                md['category'] = 'journal'
                meta_changed = True
            if not md.get('author'):
                md['author'] = AUTHOR
                meta_changed = True
            if meta_changed:
                page.metadata = md
                dirty.append('metadata')
            if page.publish_at is None:
                page.publish_at = now - timedelta(days=i)
                dirty.append('publish_at')
            if dirty:
                page.save(update_fields=dirty)
                republished += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Journal: {created} created, {republished} updated, {retired} off-brand article(s) removed.'
            )
        )
