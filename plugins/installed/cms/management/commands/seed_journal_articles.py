"""Seed 10 book-specific journal articles into cms.Page.

Each article is hand-written editorial copy tied to a classic title that
lives in the catalog. Articles surface on /journal/ because they carry
``state='published'`` + ``metadata={'category': 'journal', ...}``.

Idempotent — re-run safely; existing slugs are skipped.

Usage:
    python manage.py seed_journal_articles
    python manage.py seed_journal_articles --dry-run
    python manage.py seed_journal_articles --limit 3
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from plugins.installed.catalog.models import Product
from plugins.installed.cms.models import Page

# Map: book product slug → editorial article spec.
# `title` becomes the Page title (and seeds the slug).
# `body_html` is rendered as-is by the journal_detail template.
# `excerpt` is shown on /journal/ index + used as <meta description>.
ARTICLES: dict[str, dict[str, str]] = {
    'pride-and-prejudice': {
        'title': 'Why Pride and Prejudice still wins',
        'excerpt': 'A note on what Austen taught the modern novel — irony, structure, the shrug.',
        'body_html': (
            '<p>Two hundred years after Austen put down her pen, <em>Pride and Prejudice</em> keeps doing the thing every novel since has been trying to copy.</p>'
            "<p>The thing is structure. Austen built a machine — six set pieces, two reversals, one slow turn of the heart — and made it look like a drawing-room comedy. You can read the book for the jokes and miss it. You can read it for the romance and miss it. The trick of the book is that it works on whichever level you bring to it, and then quietly works on the next one when you come back. That's why the rereads are better than the first read. Most novels don't survive a second pass; this one gets sharper.</p>"
            "<p>What surprises people, when they come to it late, is how funny it is. Not charming — funny. Austen's irony is bone-dry and it does not date. She's writing about money, status, and the small humiliations of being a woman with an opinion in a room full of men who don't have one. Two centuries on, the room has different wallpaper. The dynamic is the same.</p>"
            '<p>We carry <a href="/products/pride-and-prejudice/">Pride and Prejudice</a> on the shelf because every shop should. It\'s the book we recommend when someone says they want to start reading again after a long pause. It welcomes you back.</p>'
            '<p>Read <a href="/products/pride-and-prejudice/">Pride and Prejudice</a> — on the shelf now &rarr;</p>'
        ),
    },
    'war-and-peace': {
        'title': 'On finally reading War and Peace',
        'excerpt': 'It is not the book you think it is. It is shorter, warmer, and stranger.',
        'body_html': (
            '<p><em>War and Peace</em> has a reputation problem, and the reputation is mostly wrong.</p>'
            "<p>People talk about it as if it were homework — a doorstop you survive rather than read. The truth is that it's one of the warmest novels ever written. Tolstoy is obsessed with how people actually behave at dinner, at a dance, in the silence after a misunderstanding. The battle scenes are famous; the dinner scenes are better. Natasha at fifteen, leaning out of a window because she can't sleep, is the whole reason to read this book.</p>"
            '<p>It is also shorter than it looks. The chapters are tiny — three or four pages on average — and the prose moves. You can read forty pages in a sitting without trying. Pick it up in October, finish it by February. Tolstoy did not write this to torture you. He wrote it because he wanted to know how a person makes a decent life inside history, and he was willing to use 1,200 pages to find out.</p>'
            '<p>Our copy of <a href="/products/war-and-peace/">War and Peace</a> is the one we\'d hand a friend who said they were thinking about it. It is the right edition with the right footnotes and it does not pretend the book is harder than it is.</p>'
            '<p>Read <a href="/products/war-and-peace/">War and Peace</a> — on the shelf now &rarr;</p>'
        ),
    },
    'frankenstein': {
        'title': "Frankenstein wasn't the monster",
        'excerpt': 'Mary Shelley wrote a novel about responsibility. We keep reading it as a novel about horror.',
        'body_html': (
            "<p>Frankenstein wasn't supposed to be the monster. That was always the point, and it's still the part most people get wrong.</p>"
            '<p>Mary Shelley was nineteen when she wrote it. She had just lost a child. She was living in a rented house on a lake with a husband who was not yet famous and a brother-in-law who would never be. The novel she produced that summer is not a horror story — it is a novel about what a man owes the thing he makes. The creature is articulate, lonely, and unloved. Victor is a coward. The horror is the abandonment, not the lightning.</p>'
            '<p>What surprises readers who come to the book expecting Boris Karloff is how much of it is conversation. The creature reads Milton. He learns French by eavesdropping. He asks his maker for a wife and is refused. The novel is asking what we owe each other, and refusing to give an easy answer. It also happens to be the first science fiction novel in English, which is a fact worth pausing on: the genre starts with a question about ethics, not a question about technology.</p>'
            '<p>We carry <a href="/products/frankenstein/">Frankenstein</a> because it is one of the books people most often misremember, and rereading it as an adult is a small revelation.</p>'
            '<p>Read <a href="/products/frankenstein/">Frankenstein</a> — on the shelf now &rarr;</p>'
        ),
    },
    'dracula': {
        'title': 'Dracula is a paperwork novel',
        'excerpt': 'It is told in letters, telegrams, diary entries, and shipping manifests — and that is why it works.',
        'body_html': (
            '<p>Dracula is a paperwork novel, and that is why it still works.</p>'
            "<p>Stoker built the book out of documents — diary entries, letters, telegrams, ship's logs, newspaper clippings. There is no narrator. There is only a stack of evidence, assembled after the fact by people who did not know what they were looking at while they were inside it. The form is the horror. You read the book the way the characters live it: in fragments, out of order, watching dread accumulate in the gaps between the pages.</p>"
            "<p>People who come to Dracula expecting velvet capes and Transylvanian fog are surprised by how procedural it is. The middle of the novel is essentially a detective story conducted by lawyers, doctors, and a Texan with a Bowie knife. Van Helsing's job is mostly paperwork. The vampire is dispatched, in the end, because the heroes are good at filing. There is a lesson in that about modernity, and Stoker knew it.</p>"
            '<p>It is also genuinely scary in places — the sequence aboard the Demeter is one of the great set pieces in 19th-century fiction. Read <a href="/products/dracula/">Dracula</a> for that scene alone and you\'ll come away thinking the rest is a bonus.</p>'
            '<p>Read <a href="/products/dracula/">Dracula</a> — on the shelf now &rarr;</p>'
        ),
    },
    'moby-dick': {
        'title': 'Moby-Dick gets longer the longer you spend with it',
        'excerpt': "Melville's white whale is not the point. The detours are the point.",
        'body_html': (
            "<p>Moby-Dick is the kind of book that gets longer the longer you spend with it. That's its trick, and its point.</p>"
            '<p>People who try to read it like a thriller bounce off it around chapter forty, when Melville stops the plot to deliver a fifteen-page lecture on the anatomy of a whale. People who give in — who let the digressions be the book — discover that the digressions are where Melville actually lives. The cetology chapters, the sermon on Jonah, the meditation on the colour white, the long aside on the rope: this is not filler. This is the novel. Ahab and the whale are a frame. The book is everything Melville knew about labour, race, friendship, and the sea, dumped on the page in a voice that has not aged a day.</p>'
            '<p>What surprises new readers is how funny it is. Ishmael is a comedian. The first hundred pages, before the Pequod sails, are essentially a buddy comedy between Ishmael and Queequeg, and the affection between them is one of the warmest things in American literature. The novel is not a slog. It is a long, strange, generous letter from a man who wanted to put everything in.</p>'
            '<p>Our copy of <a href="/products/moby-dick/">Moby-Dick</a> is the unabridged one, because there is no other kind. Read it slowly. Take a year.</p>'
            '<p>Read <a href="/products/moby-dick/">Moby-Dick</a> — on the shelf now &rarr;</p>'
        ),
    },
    'the-great-gatsby': {
        'title': 'The Great Gatsby in 2026',
        'excerpt': 'A short novel about money that is mostly about loneliness, and reads sharper every year.',
        'body_html': (
            '<p>The Great Gatsby is short, and that is part of the joke.</p>'
            "<p>Fitzgerald wrote a 180-page book about the richest man on Long Island and made it feel inexhaustible. The novel is a magic trick: nothing much happens, the prose is light enough to read in an afternoon, and yet it has outlasted nearly everything written around it. Re-read it now and the parts that hit hardest are not the parties. They are the small things — Nick lying about his age at the end, Daisy's voice being full of money, the green light that turns out to mean nothing. The book is about loneliness in a costume of glamour, and the costume has not lost a sequin.</p>"
            '<p>What surprises readers who come back to it as adults is how moral the book is. Fitzgerald is not celebrating Gatsby. He is mourning him, and he is angry. The last page is one of the great closing paragraphs in English, and it is a paragraph about defeat. We keep teaching this book to teenagers because it is short. We should probably re-teach it to ourselves at forty.</p>'
            '<p>We carry <a href="/products/the-great-gatsby/">The Great Gatsby</a> on the shelf because every few years someone walks in and says they haven\'t read it since school, and they are about to have a very good week.</p>'
            '<p>Read <a href="/products/the-great-gatsby/">The Great Gatsby</a> — on the shelf now &rarr;</p>'
        ),
    },
    'jane-eyre': {
        'title': 'Jane Eyre, on her own terms',
        'excerpt': "Charlotte Brontë's first-person voice invented something we now take for granted.",
        'body_html': (
            '<p>Jane Eyre walks into the room and tells you what she thinks. That was new in 1847. It is still the engine of the book.</p>'
            '<p>What Brontë did with the first-person voice in this novel — direct, unembarrassed, willing to argue with the reader — is the thing every confessional novel since has been trying to do. Jane is poor, plain, and angry, and she will not pretend otherwise to make you comfortable. She is also funny, in a quiet way, and her judgement on the people around her is razor-edged. Mr Rochester is the famous one, but Jane is the one who carries the book, and she carries it by refusing to be a heroine in the way the 19th century wanted heroines to be carried.</p>'
            "<p>The novel is also, separately, a very strange book. There is a ghost. There is a fire. There is a long stretch on a moor that reads like a hallucination. Brontë did not care about realism the way her sister did. She cared about feeling, and the feelings in this book are enormous. Read it for Jane's voice. Stay for the moor.</p>"
            '<p>Our edition of <a href="/products/jane-eyre/">Jane Eyre</a> has the introduction we like — short, deferential, gets out of the way.</p>'
            '<p>Read <a href="/products/jane-eyre/">Jane Eyre</a> — on the shelf now &rarr;</p>'
        ),
    },
    'little-women': {
        'title': 'Little Women is sneakier than you remember',
        'excerpt': 'Alcott wrote a domestic novel that quietly argues with itself about every choice it makes.',
        'body_html': (
            '<p>Little Women is sneakier than you remember.</p>'
            "<p>On the surface it is a domestic novel about four sisters in Concord, Massachusetts, getting older during and after the Civil War. Underneath, it is a book in argument with itself. Alcott wanted to write a different ending. Her publisher wanted Jo to get married. The compromise — Professor Bhaer, the school, the refusal to give Jo to Laurie — is the book's most interesting move, and you can feel Alcott working it out on the page. The novel is not naïve about marriage. It is making a case, in a quiet voice, that a woman might want a life of her own.</p>"
            "<p>What surprises adult readers is how sad it is. Beth's chapters are written without sentiment. Meg's marriage is unglamorous. Amy in Europe is lonely. The book that everyone remembers as cozy is actually a book about how families work, and how they don't, and how you keep loving people who have disappointed you. Alcott knew her readers, and she gave them more than they asked for.</p>"
            '<p>We carry <a href="/products/little-women/">Little Women</a> because it is one of those books that gets better every decade you carry it. Read it at twelve, twenty-five, forty. You will be reading three different novels.</p>'
            '<p>Read <a href="/products/little-women/">Little Women</a> — on the shelf now &rarr;</p>'
        ),
    },
    'the-count-of-monte-cristo': {
        'title': 'The Count of Monte Cristo is the original page-turner',
        'excerpt': 'Dumas wrote it in serial. You can feel the cliffhangers. That is the fun.',
        'body_html': (
            '<p>The Count of Monte Cristo is the book to read when you have forgotten that novels can be fun.</p>'
            '<p>Dumas wrote it in serial for a Paris newspaper, and you can feel that on every page. The chapters end on hooks. The plot moves like a current. There is a wrongful imprisonment, a treasure, a disguise, a duel, an elaborate revenge that takes a decade to execute, and a final twist that turns the whole moral argument of the book inside out. It is twelve hundred pages and it does not waste any of them. People who think long books are slow have not read this one.</p>'
            '<p>What surprises readers is how modern it feels. Dumas is interested in money, identity, and the long game. Edmond Dantès is not a hero in the simple sense; he is a man who spends the second half of the novel discovering that revenge has costs he did not budget for. The book is asking, in its big melodramatic way, whether justice and vengeance are the same thing. It decides — eventually, on the last page — that they are not. The arrival at that answer is the whole point.</p>'
            '<p>Read <a href="/products/the-count-of-monte-cristo/">The Count of Monte Cristo</a> on a long winter. It will fill it.</p>'
            '<p>Read <a href="/products/the-count-of-monte-cristo/">The Count of Monte Cristo</a> — on the shelf now &rarr;</p>'
        ),
    },
    'alice-s-adventures-in-wonderland': {
        'title': 'Alice is a logic book disguised as a children’s book',
        'excerpt': 'Carroll was a mathematician. The nonsense is rigorous. That is the joke.',
        'body_html': (
            "<p>Alice's Adventures in Wonderland is a logic book disguised as a children's book, and the disguise is the joke.</p>"
            "<p>Carroll was a mathematician at Oxford. Every piece of nonsense in this book is rigorous nonsense — it follows rules, it just follows rules nobody else has thought to write down. The Caterpillar's questions are syllogisms. The trial at the end is an essay on procedure. The poems are parodies of poems schoolchildren in 1865 would have known by heart, and the parodies work even when the originals are forgotten. The book is funnier the more you know about how 19th-century England educated its children.</p>"
            "<p>What surprises adult readers is how short it is, and how strange. There is no plot in the conventional sense. Alice falls down a hole and meets a series of arguments. She wins some of them. She loses some of them. She wakes up. The whole thing reads like a dream because it was written like a dream — Carroll told it to Alice Liddell on a boat one afternoon and wrote it down afterwards. The looseness is the point. Most children's books since have tried to be tidier and have been worse for it.</p>"
            '<p>We carry <a href="/products/alice-s-adventures-in-wonderland/">Alice\'s Adventures in Wonderland</a> in the edition with the Tenniel illustrations, because there is no other edition that matters.</p>'
            '<p>Read <a href="/products/alice-s-adventures-in-wonderland/">Alice\'s Adventures in Wonderland</a> — on the shelf now &rarr;</p>'
        ),
    },
}


def _article_slug(title: str) -> str:
    return slugify(title)


class Command(BaseCommand):
    help = (
        'Seed 10 hand-written journal articles tied to classic books in the catalog. '
        'Idempotent: existing slugs are skipped. Use --dry-run to preview.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be created without writing to the DB.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Cap the number of articles created (after skipping existing).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        now = timezone.now()
        created = 0
        skipped_existing: list[str] = []
        skipped_missing_product: list[str] = []
        would_create: list[str] = []

        for index, (product_slug, spec) in enumerate(ARTICLES.items()):
            if limit is not None and created >= limit and not dry_run:
                break
            if limit is not None and len(would_create) >= limit and dry_run:
                break

            # Skip if the book product doesn't exist in this environment.
            product = (
                Product.objects.filter(slug=product_slug, is_active=True)
                .only('id', 'slug', 'name')
                .first()
            )
            if product is None:
                skipped_missing_product.append(product_slug)
                self.stdout.write(self.style.WARNING(f'  skip (no product): {product_slug}'))
                continue

            title = spec['title']
            slug = _article_slug(title)

            if Page.objects.filter(slug=slug).exists():
                skipped_existing.append(slug)
                self.stdout.write(self.style.NOTICE(f'  skip (slug exists): {slug}'))
                continue

            # Stagger publish_at: newest first, ~1 per day going back.
            publish_at = now - timedelta(days=index)

            if dry_run:
                would_create.append(slug)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  would create: {slug}  ({title!r})  publish_at={publish_at.date()}'
                    )
                )
                continue

            Page.objects.create(
                slug=slug,
                title=title,
                excerpt=spec['excerpt'][:300],
                body=spec['body_html'],
                state='published',
                publish_at=publish_at,
                metadata={
                    'category': 'journal',
                    'related_product_slug': product_slug,
                },
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f'  created: {slug}  -> /journal/{slug}/'))

        # Summary
        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN: would create {len(would_create)} article(s); '
                    f'skipped {len(skipped_existing)} existing, '
                    f'{len(skipped_missing_product)} missing-product.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done. Created {created} article(s); '
                    f'skipped {len(skipped_existing)} existing, '
                    f'{len(skipped_missing_product)} missing-product.'
                )
            )
