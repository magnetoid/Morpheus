"""
Demo seed data for a small modern bookstore.

50 public-domain classics from Project Gutenberg. Each book carries a
``gutenberg_id`` whose canonical cover lives at
``https://www.gutenberg.org/cache/epub/<id>/pg<id>.cover.medium.jpg``.
The seed in ``services._seed_books`` downloads the cover once per book
and attaches it as a ``ProductImage``.
"""
from __future__ import annotations

# Slugs of demo books from previous seed iterations that are no longer in
# BOOKS. Listed here so _wipe_demo can clean them up when the catalog is
# re-seeded — without these the old fictional titles would linger forever.
LEGACY_BOOK_SLUGS = [
    'on-quiet-hours', 'last-letter-home', 'unfinished-light',
    'small-history-listening', 'rooms-we-didnt-choose', 'how-to-read-building',
    'borrowed-garden', 'archive-of-almost', 'river-light', 'map-we-carried',
    'field-notes-calmer', 'nine-letters', 'rain-on-the-train', 'fold-out-cookbook',
]


CATEGORIES = [
    {'name': 'Fiction',     'slug': 'fiction'},
    {'name': 'Non-fiction', 'slug': 'nonfiction'},
    {'name': 'Poetry',      'slug': 'poetry'},
    {'name': 'Essays',      'slug': 'essays'},
    {'name': 'Children',    'slug': 'children'},
    {'name': 'Art & Design', 'slug': 'art-design'},
]

COLLECTIONS = [
    {
        'name': 'Editor\'s pick — classics',
        'slug': 'editors-pick-april',
        'description': 'One title a month. The classic that earned the spotlight by surviving every reading list.',
        'is_featured': True,
    },
    {
        'name': 'Reading the canon',
        'slug': 'reading-the-spring',
        'description': 'A small rotating shelf of the books everyone says they should read.',
        'is_featured': True,
    },
    {
        'name': 'Independent presses we love',
        'slug': 'independent-presses',
        'description': 'Tiny shops doing the work that big houses won\'t.',
        'is_featured': False,
    },
]

VENDORS = [
    {'name': 'Project Gutenberg', 'slug': 'project-gutenberg', 'commission_rate': '0.00'},
    {'name': 'Pelican Press',     'slug': 'pelican-press',     'commission_rate': '15.00'},
    {'name': 'Lantern Books',     'slug': 'lantern-books',     'commission_rate': '15.00'},
    {'name': 'Foxglove Editions', 'slug': 'foxglove-editions', 'commission_rate': '20.00'},
]


# (name, slug, sku, category_slug, vendor_slug, price, short_description, description, featured)
# All Project Gutenberg public-domain works. Prices are nominal — public-domain
# bookstores typically sell printed editions of classics for $5-15.
BOOKS = [
    # ── Fiction (32) ──────────────────────────────────────────────────────
    ('Pride and Prejudice', 'pride-and-prejudice', 'PG-1342', 'fiction', 'project-gutenberg',
     '8.00', 'Manners, marriage, and Mr Darcy.',
     'Austen\'s comedy of manners around the five Bennet sisters and the men who do and don\'t deserve them. Witty, sharp, and the gold standard for the form.', True),

    ('Frankenstein', 'frankenstein', 'PG-84', 'fiction', 'project-gutenberg',
     '7.50', 'A scientist creates life — and learns the cost.',
     'Mary Shelley\'s gothic novel about Victor Frankenstein and his creation. Less monster movie, more meditation on responsibility, ambition, and what we owe what we make.', True),

    ('Dracula', 'dracula', 'PG-345', 'fiction', 'project-gutenberg',
     '8.50', 'Letters, journals, and a Transylvanian count.',
     'Stoker\'s epistolary horror novel that defined the vampire genre. Read for the dread, stay for the structure — a story told entirely through documents.', False),

    ('The Adventures of Sherlock Holmes', 'sherlock-holmes', 'PG-1661', 'fiction', 'project-gutenberg',
     '9.00', 'Twelve cases, one consulting detective.',
     'Conan Doyle\'s short-story collection introducing the world\'s most famous detective. Best read at one chapter per evening with a strong cup of tea.', True),

    ('Great Expectations', 'great-expectations', 'PG-1400', 'fiction', 'project-gutenberg',
     '8.00', 'Pip, Estella, and a benefactor in the dark.',
     'Dickens at his most psychological. A coming-of-age novel about social class, longing, and the long shadow of a single childhood encounter.', False),

    ('A Tale of Two Cities', 'tale-of-two-cities', 'PG-98', 'fiction', 'project-gutenberg',
     '7.50', 'London, Paris, and the Revolution.',
     'It was the best of times, it was the worst of times. Dickens\'s tightest novel — sacrifice, doubles, and a guillotine\'s edge.', False),

    ('Wuthering Heights', 'wuthering-heights', 'PG-768', 'fiction', 'project-gutenberg',
     '7.50', 'Heathcliff, Catherine, and the moors.',
     'Emily Brontë\'s only novel. A claustrophobic study in obsession, written by someone who clearly understood weather as a third character.', False),

    ('Jane Eyre', 'jane-eyre', 'PG-1260', 'fiction', 'project-gutenberg',
     '8.00', 'Reader, I married him.',
     'Charlotte Brontë\'s portrait of an orphaned governess who refuses to be small. Gothic, romantic, and stubbornly modern in its insistence on a self.', True),

    ('The Picture of Dorian Gray', 'dorian-gray', 'PG-174', 'fiction', 'project-gutenberg',
     '8.00', 'Vanity, a portrait, and a price.',
     'Wilde\'s only novel — a fable about beauty, corruption, and the things you can\'t hide forever. Pithier and meaner than the play.', False),

    ('Adventures of Huckleberry Finn', 'huckleberry-finn', 'PG-76', 'fiction', 'project-gutenberg',
     '8.50', 'Down the Mississippi on a raft.',
     'Twain\'s vernacular masterpiece. A boy, an escaped slave, and a country in argument with itself — funny, brutal, and far better than any movie has ever managed.', False),

    ('Moby-Dick', 'moby-dick', 'PG-2701', 'fiction', 'project-gutenberg',
     '12.00', 'Call me Ishmael.',
     'Melville\'s leviathan. A whaling novel, a workplace drama, an encyclopedia of cetology, and the most patient revenge story ever told. Take your time.', True),

    ('The Scarlet Letter', 'scarlet-letter', 'PG-25344', 'fiction', 'project-gutenberg',
     '7.50', 'A and a public stage.',
     'Hawthorne\'s study in shame and the small towns that enforce it. Read for the moral architecture, not the plot.', False),

    ('Sense and Sensibility', 'sense-and-sensibility', 'PG-161', 'fiction', 'project-gutenberg',
     '8.00', 'Two sisters, two ways of feeling.',
     'Austen\'s first published novel. The colder one of her sisters books, and probably the funnier.', False),

    ('Emma', 'emma', 'PG-158', 'fiction', 'project-gutenberg',
     '8.00', 'A meddler comes of age.',
     'Austen on a heroine no one but Austen could have liked. The matchmaking comedy that taught novelists how to do close third person.', False),

    ('Crime and Punishment', 'crime-and-punishment', 'PG-2554', 'fiction', 'project-gutenberg',
     '11.00', 'Raskolnikov, an axe, and 600 pages of guilt.',
     'Dostoyevsky\'s claustrophobic St Petersburg novel. The interior monologue of a murderer trying to talk himself into the philosophical superhero he isn\'t.', True),

    ('Anna Karenina', 'anna-karenina', 'PG-1399', 'fiction', 'project-gutenberg',
     '12.50', 'A train, a marriage, a doomed affair.',
     'Tolstoy\'s social novel about love, farming, faith, and the hum of history under all of them. Levin\'s chapters are the best agriculture writing in the canon.', False),

    ('War and Peace', 'war-and-peace', 'PG-2600', 'fiction', 'project-gutenberg',
     '15.00', 'Tolstoy\'s big one.',
     'Five families, twelve years, two emperors, and a thousand pages of theory about why generals don\'t actually decide battles. The novel-as-cathedral.', False),

    ('Madame Bovary', 'madame-bovary', 'PG-2413', 'fiction', 'project-gutenberg',
     '8.00', 'A provincial life, perfectly described.',
     'Flaubert\'s sentence-level scrutiny of a marriage that fails for very ordinary reasons. The first modern novel — every page exhibit A.', False),

    ('The Brothers Karamazov', 'brothers-karamazov', 'PG-28054', 'fiction', 'project-gutenberg',
     '13.00', 'Three brothers, one father, every theological argument.',
     'Dostoyevsky\'s last novel. A patricide mystery that takes detours through the inquisition, the existence of God, and the weather. Read the legend of the Grand Inquisitor twice.', False),

    ('Don Quixote', 'don-quixote', 'PG-996', 'fiction', 'project-gutenberg',
     '13.50', 'A knight, a squire, a windmill.',
     'Cervantes\'s great hinge between the medieval and the modern. An old man reads too much chivalric fiction and decides to live inside it.', False),

    ('Heart of Darkness', 'heart-of-darkness', 'PG-219', 'fiction', 'project-gutenberg',
     '6.50', 'A journey up the river.',
     'Conrad\'s slim, unsettling novella about colonial trade and what it does to the people who do it. Apocalypse Now is one of many things this book made possible.', False),

    ('The Time Machine', 'time-machine', 'PG-35', 'fiction', 'project-gutenberg',
     '6.00', 'Forward, and forward again.',
     'Wells\'s short novel that invented the genre. The Eloi, the Morlocks, and a future that turns out to be, in the end, a history lesson.', False),

    ('The War of the Worlds', 'war-of-the-worlds', 'PG-36', 'fiction', 'project-gutenberg',
     '7.00', 'Tripods over Surrey.',
     'Wells\'s alien invasion novel. Best read for the texture of late-Victorian England under siege — the journalism of Mars.', False),

    ('Treasure Island', 'treasure-island', 'PG-120', 'fiction', 'project-gutenberg',
     '7.50', 'X marks the spot.',
     'Stevenson\'s adventure that supplied the template for every pirate story since. A boy, a one-legged cook, and a map that actually means it.', False),

    ('Dr Jekyll and Mr Hyde', 'jekyll-and-hyde', 'PG-43', 'fiction', 'project-gutenberg',
     '6.00', 'A door, a man, two of them.',
     'Stevenson\'s short, sharp study of a respectable Victorian who isn\'t. Reads in an evening; ages in your head for years.', False),

    ('The Adventures of Tom Sawyer', 'tom-sawyer', 'PG-74', 'fiction', 'project-gutenberg',
     '7.50', 'A fence, a cave, a hot summer.',
     'Twain\'s warmer, simpler precursor to Huck Finn. Childhood in Hannibal, Missouri, before America had finished happening.', False),

    ('Little Women', 'little-women', 'PG-514', 'fiction', 'project-gutenberg',
     '8.50', 'Meg, Jo, Beth, Amy.',
     'Alcott\'s portrait of four sisters in wartime Massachusetts. Funny, sad, and quietly furious about what girls were and weren\'t allowed to do.', True),

    ('Anne of Green Gables', 'anne-of-green-gables', 'PG-45', 'fiction', 'project-gutenberg',
     '8.00', 'A red-headed orphan, a Prince Edward Island farm.',
     'Montgomery\'s book about an imagination so loud it bends a household around it. Yes, it\'s for children. It\'s also for everyone.', False),

    ('Persuasion', 'persuasion', 'PG-105', 'fiction', 'project-gutenberg',
     '8.00', 'A second chance, eight years later.',
     'Austen\'s last completed novel and her quietest. Read it after the others — it works best when you can hear what isn\'t being said.', False),

    ('Hamlet', 'hamlet', 'PG-1524', 'fiction', 'project-gutenberg',
     '7.00', 'A prince delays.',
     'Shakespeare\'s longest tragedy. Read the soliloquies aloud at least once.', False),

    ('Romeo and Juliet', 'romeo-and-juliet', 'PG-1513', 'fiction', 'project-gutenberg',
     '6.50', 'Two households, one balcony.',
     'Shakespeare\'s teenage tragedy. Faster than you remember and grimmer than the high-school version makes it look.', False),

    ('Macbeth', 'macbeth', 'PG-1533', 'fiction', 'project-gutenberg',
     '6.50', 'A throne, a knife, three sisters on a heath.',
     'Shakespeare\'s tightest tragedy. The Scottish play, read for ambition\'s mechanics.', False),

    # ── Poetry (6) ────────────────────────────────────────────────────────
    ('Leaves of Grass', 'leaves-of-grass', 'PG-1322', 'poetry', 'project-gutenberg',
     '11.00', 'America in long lines.',
     'Whitman\'s expanding life-work. A collection that grew across editions, one of the few books in English that the country was actually written into.', True),

    ('The Raven and Other Poems', 'the-raven', 'PG-1065', 'poetry', 'project-gutenberg',
     '6.50', 'Quoth the raven.',
     'Poe\'s short, hypnotic gothic poems. Read in one sitting after dark.', False),

    ('Shakespeare\'s Sonnets', 'shakespeare-sonnets', 'PG-1041', 'poetry', 'project-gutenberg',
     '7.50', '154 fourteen-line poems.',
     'The sonnets, complete. The most argued-over love poems in English; still very strange.', False),

    ('The Iliad', 'the-iliad', 'PG-6130', 'poetry', 'project-gutenberg',
     '11.00', 'Wrath and Achilles.',
     'Homer\'s war epic in Pope\'s English. Twenty-four books of bronze, grief, and gods who do not understand what they are watching.', False),

    ('The Odyssey', 'the-odyssey', 'PG-1727', 'poetry', 'project-gutenberg',
     '11.00', 'A long way home.',
     'Homer\'s sequel-of-sorts. Butler\'s prose translation — the cleanest gateway, then upgrade to verse.', True),

    ('The Divine Comedy', 'divine-comedy', 'PG-8800', 'poetry', 'project-gutenberg',
     '13.00', 'Hell, then up.',
     'Dante in Cary\'s 19th-century English. Inferno gets the hype; Purgatorio is where the actual reading happens.', False),

    # ── Essays (3) ────────────────────────────────────────────────────────
    ('Self-Reliance and Other Essays', 'self-reliance', 'PG-16643', 'essays', 'project-gutenberg',
     '7.00', 'Trust thyself.',
     'Emerson\'s essays. Read Self-Reliance every January and Compensation every July.', False),

    ('Beyond Good and Evil', 'beyond-good-and-evil', 'PG-4363', 'essays', 'project-gutenberg',
     '8.00', 'Aphorisms with teeth.',
     'Nietzsche in his middle period, when the prose got faster and the targets got bigger. Read in chunks; argue back.', False),

    ('Meditations', 'meditations', 'PG-2680', 'essays', 'project-gutenberg',
     '7.50', 'Notes to himself.',
     'Marcus Aurelius\'s journal, written by an emperor as private reminders. The most practical philosophy book ever published by accident.', True),

    # ── Non-fiction (3) ───────────────────────────────────────────────────
    ('Walden', 'walden', 'PG-205', 'nonfiction', 'project-gutenberg',
     '9.00', 'A pond, two years, a cabin.',
     'Thoreau\'s account of life lived deliberately. Read it less as nature writing and more as a long argument about how much furniture a person actually needs.', False),

    ('The Souls of Black Folk', 'souls-of-black-folk', 'PG-408', 'nonfiction', 'project-gutenberg',
     '9.50', 'Sociology, history, and the colour line.',
     'Du Bois\'s 1903 essays. The book that put the phrase "double-consciousness" into English and didn\'t apologise for it.', False),

    ('Civil Disobedience', 'civil-disobedience', 'PG-71', 'nonfiction', 'project-gutenberg',
     '5.50', 'On the duty of refusing.',
     'Thoreau\'s pamphlet, fifty pages. Influenced Gandhi, MLK, and every conscientious objector since.', False),

    # ── Children (6) ──────────────────────────────────────────────────────
    ('Alice\'s Adventures in Wonderland', 'alice-in-wonderland', 'PG-11', 'children', 'project-gutenberg',
     '7.00', 'A rabbit hole, a tea party.',
     'Carroll\'s logic-soaked children\'s book. The grown-ups are insane, the children are the only sensible ones, and the math is real.', True),

    ('The Wonderful Wizard of Oz', 'wizard-of-oz', 'PG-55', 'children', 'project-gutenberg',
     '7.00', 'A road, paved.',
     'Baum\'s American fairy tale. Stranger and gentler than the movie — the book has fourteen pigs.', False),

    ('Peter Pan', 'peter-pan', 'PG-16', 'children', 'project-gutenberg',
     '7.00', 'Second star to the right.',
     'Barrie\'s novel, much darker than every adaptation. Ages 8-80; cry at the ending.', False),

    ('The Jungle Book', 'jungle-book', 'PG-236', 'children', 'project-gutenberg',
     '7.00', 'Stories from the Indian forests.',
     'Kipling\'s linked stories. Mowgli, Rikki-Tikki-Tavi, and a whole bestiary of animals who explain themselves.', False),

    ('Grimms\' Fairy Tales', 'grimms-fairy-tales', 'PG-2591', 'children', 'project-gutenberg',
     '8.50', 'Two hundred and ten of them.',
     'The Grimm brothers\' household tales, complete. Originally not for children; ideal for them now.', True),

    ('The Adventures of Pinocchio', 'pinocchio', 'PG-500', 'children', 'project-gutenberg',
     '7.00', 'A wooden puppet learns.',
     'Collodi\'s Italian original. Funnier, sadder, and considerably more violent than the Disney version.', False),
]


# Book-specific metadata, indexed by slug. Written as Metafields with
# namespace='book' during seeding — picked up by the storefront PDP
# "About this edition" card. ``gutenberg_id`` drives cover download.
BOOK_METADATA = {
    'pride-and-prejudice':       {'gutenberg_id': 1342,  'author': 'Jane Austen',          'publisher': 'Project Gutenberg', 'published_year': 1813, 'format': 'Paperback', 'pages': 432, 'language': 'English'},
    'frankenstein':              {'gutenberg_id': 84,    'author': 'Mary Shelley',         'publisher': 'Project Gutenberg', 'published_year': 1818, 'format': 'Paperback', 'pages': 280, 'language': 'English'},
    'dracula':                   {'gutenberg_id': 345,   'author': 'Bram Stoker',          'publisher': 'Project Gutenberg', 'published_year': 1897, 'format': 'Paperback', 'pages': 418, 'language': 'English'},
    'sherlock-holmes':           {'gutenberg_id': 1661,  'author': 'Arthur Conan Doyle',   'publisher': 'Project Gutenberg', 'published_year': 1892, 'format': 'Paperback', 'pages': 307, 'language': 'English'},
    'great-expectations':        {'gutenberg_id': 1400,  'author': 'Charles Dickens',      'publisher': 'Project Gutenberg', 'published_year': 1861, 'format': 'Paperback', 'pages': 544, 'language': 'English'},
    'tale-of-two-cities':        {'gutenberg_id': 98,    'author': 'Charles Dickens',      'publisher': 'Project Gutenberg', 'published_year': 1859, 'format': 'Paperback', 'pages': 489, 'language': 'English'},
    'wuthering-heights':         {'gutenberg_id': 768,   'author': 'Emily Brontë',         'publisher': 'Project Gutenberg', 'published_year': 1847, 'format': 'Paperback', 'pages': 416, 'language': 'English'},
    'jane-eyre':                 {'gutenberg_id': 1260,  'author': 'Charlotte Brontë',     'publisher': 'Project Gutenberg', 'published_year': 1847, 'format': 'Paperback', 'pages': 532, 'language': 'English'},
    'dorian-gray':               {'gutenberg_id': 174,   'author': 'Oscar Wilde',          'publisher': 'Project Gutenberg', 'published_year': 1890, 'format': 'Paperback', 'pages': 254, 'language': 'English'},
    'huckleberry-finn':          {'gutenberg_id': 76,    'author': 'Mark Twain',           'publisher': 'Project Gutenberg', 'published_year': 1884, 'format': 'Paperback', 'pages': 366, 'language': 'English'},
    'moby-dick':                 {'gutenberg_id': 2701,  'author': 'Herman Melville',      'publisher': 'Project Gutenberg', 'published_year': 1851, 'format': 'Paperback', 'pages': 720, 'language': 'English'},
    'scarlet-letter':            {'gutenberg_id': 25344, 'author': 'Nathaniel Hawthorne',  'publisher': 'Project Gutenberg', 'published_year': 1850, 'format': 'Paperback', 'pages': 286, 'language': 'English'},
    'sense-and-sensibility':     {'gutenberg_id': 161,   'author': 'Jane Austen',          'publisher': 'Project Gutenberg', 'published_year': 1811, 'format': 'Paperback', 'pages': 374, 'language': 'English'},
    'emma':                      {'gutenberg_id': 158,   'author': 'Jane Austen',          'publisher': 'Project Gutenberg', 'published_year': 1815, 'format': 'Paperback', 'pages': 474, 'language': 'English'},
    'crime-and-punishment':      {'gutenberg_id': 2554,  'author': 'Fyodor Dostoyevsky',   'publisher': 'Project Gutenberg', 'published_year': 1866, 'format': 'Paperback', 'pages': 671, 'language': 'English'},
    'anna-karenina':             {'gutenberg_id': 1399,  'author': 'Leo Tolstoy',          'publisher': 'Project Gutenberg', 'published_year': 1877, 'format': 'Paperback', 'pages': 864, 'language': 'English'},
    'war-and-peace':             {'gutenberg_id': 2600,  'author': 'Leo Tolstoy',          'publisher': 'Project Gutenberg', 'published_year': 1869, 'format': 'Paperback', 'pages': 1296, 'language': 'English'},
    'madame-bovary':             {'gutenberg_id': 2413,  'author': 'Gustave Flaubert',     'publisher': 'Project Gutenberg', 'published_year': 1856, 'format': 'Paperback', 'pages': 343, 'language': 'English'},
    'brothers-karamazov':        {'gutenberg_id': 28054, 'author': 'Fyodor Dostoyevsky',   'publisher': 'Project Gutenberg', 'published_year': 1880, 'format': 'Paperback', 'pages': 985, 'language': 'English'},
    'don-quixote':               {'gutenberg_id': 996,   'author': 'Miguel de Cervantes',  'publisher': 'Project Gutenberg', 'published_year': 1605, 'format': 'Paperback', 'pages': 1023, 'language': 'English'},
    'heart-of-darkness':         {'gutenberg_id': 219,   'author': 'Joseph Conrad',        'publisher': 'Project Gutenberg', 'published_year': 1899, 'format': 'Paperback', 'pages': 96,  'language': 'English'},
    'time-machine':              {'gutenberg_id': 35,    'author': 'H. G. Wells',          'publisher': 'Project Gutenberg', 'published_year': 1895, 'format': 'Paperback', 'pages': 118, 'language': 'English'},
    'war-of-the-worlds':         {'gutenberg_id': 36,    'author': 'H. G. Wells',          'publisher': 'Project Gutenberg', 'published_year': 1898, 'format': 'Paperback', 'pages': 192, 'language': 'English'},
    'treasure-island':           {'gutenberg_id': 120,   'author': 'Robert Louis Stevenson', 'publisher': 'Project Gutenberg', 'published_year': 1883, 'format': 'Paperback', 'pages': 256, 'language': 'English'},
    'jekyll-and-hyde':           {'gutenberg_id': 43,    'author': 'Robert Louis Stevenson', 'publisher': 'Project Gutenberg', 'published_year': 1886, 'format': 'Paperback', 'pages': 96,  'language': 'English'},
    'tom-sawyer':                {'gutenberg_id': 74,    'author': 'Mark Twain',           'publisher': 'Project Gutenberg', 'published_year': 1876, 'format': 'Paperback', 'pages': 274, 'language': 'English'},
    'little-women':              {'gutenberg_id': 514,   'author': 'Louisa May Alcott',    'publisher': 'Project Gutenberg', 'published_year': 1868, 'format': 'Paperback', 'pages': 759, 'language': 'English'},
    'anne-of-green-gables':      {'gutenberg_id': 45,    'author': 'L. M. Montgomery',     'publisher': 'Project Gutenberg', 'published_year': 1908, 'format': 'Paperback', 'pages': 320, 'language': 'English'},
    'persuasion':                {'gutenberg_id': 105,   'author': 'Jane Austen',          'publisher': 'Project Gutenberg', 'published_year': 1817, 'format': 'Paperback', 'pages': 252, 'language': 'English'},
    'hamlet':                    {'gutenberg_id': 1524,  'author': 'William Shakespeare',  'publisher': 'Project Gutenberg', 'published_year': 1603, 'format': 'Paperback', 'pages': 192, 'language': 'English'},
    'romeo-and-juliet':          {'gutenberg_id': 1513,  'author': 'William Shakespeare',  'publisher': 'Project Gutenberg', 'published_year': 1597, 'format': 'Paperback', 'pages': 160, 'language': 'English'},
    'macbeth':                   {'gutenberg_id': 1533,  'author': 'William Shakespeare',  'publisher': 'Project Gutenberg', 'published_year': 1606, 'format': 'Paperback', 'pages': 128, 'language': 'English'},
    'leaves-of-grass':           {'gutenberg_id': 1322,  'author': 'Walt Whitman',         'publisher': 'Project Gutenberg', 'published_year': 1855, 'format': 'Paperback', 'pages': 432, 'language': 'English'},
    'the-raven':                 {'gutenberg_id': 1065,  'author': 'Edgar Allan Poe',      'publisher': 'Project Gutenberg', 'published_year': 1845, 'format': 'Paperback', 'pages': 96,  'language': 'English'},
    'shakespeare-sonnets':       {'gutenberg_id': 1041,  'author': 'William Shakespeare',  'publisher': 'Project Gutenberg', 'published_year': 1609, 'format': 'Paperback', 'pages': 192, 'language': 'English'},
    'the-iliad':                 {'gutenberg_id': 6130,  'author': 'Homer (tr. Pope)',     'publisher': 'Project Gutenberg', 'published_year': 1715, 'format': 'Paperback', 'pages': 528, 'language': 'English'},
    'the-odyssey':               {'gutenberg_id': 1727,  'author': 'Homer (tr. Butler)',   'publisher': 'Project Gutenberg', 'published_year': 1900, 'format': 'Paperback', 'pages': 384, 'language': 'English'},
    'divine-comedy':             {'gutenberg_id': 8800,  'author': 'Dante (tr. Cary)',     'publisher': 'Project Gutenberg', 'published_year': 1814, 'format': 'Paperback', 'pages': 720, 'language': 'English'},
    'self-reliance':             {'gutenberg_id': 16643, 'author': 'Ralph Waldo Emerson',  'publisher': 'Project Gutenberg', 'published_year': 1841, 'format': 'Paperback', 'pages': 224, 'language': 'English'},
    'beyond-good-and-evil':      {'gutenberg_id': 4363,  'author': 'Friedrich Nietzsche',  'publisher': 'Project Gutenberg', 'published_year': 1886, 'format': 'Paperback', 'pages': 244, 'language': 'English'},
    'meditations':               {'gutenberg_id': 2680,  'author': 'Marcus Aurelius',      'publisher': 'Project Gutenberg', 'published_year': 180,  'format': 'Paperback', 'pages': 256, 'language': 'English'},
    'walden':                    {'gutenberg_id': 205,   'author': 'Henry David Thoreau',  'publisher': 'Project Gutenberg', 'published_year': 1854, 'format': 'Paperback', 'pages': 384, 'language': 'English'},
    'souls-of-black-folk':       {'gutenberg_id': 408,   'author': 'W. E. B. Du Bois',     'publisher': 'Project Gutenberg', 'published_year': 1903, 'format': 'Paperback', 'pages': 272, 'language': 'English'},
    'civil-disobedience':        {'gutenberg_id': 71,    'author': 'Henry David Thoreau',  'publisher': 'Project Gutenberg', 'published_year': 1849, 'format': 'Paperback', 'pages': 56,  'language': 'English'},
    'alice-in-wonderland':       {'gutenberg_id': 11,    'author': 'Lewis Carroll',        'publisher': 'Project Gutenberg', 'published_year': 1865, 'format': 'Paperback', 'pages': 192, 'language': 'English'},
    'wizard-of-oz':              {'gutenberg_id': 55,    'author': 'L. Frank Baum',        'publisher': 'Project Gutenberg', 'published_year': 1900, 'format': 'Paperback', 'pages': 272, 'language': 'English'},
    'peter-pan':                 {'gutenberg_id': 16,    'author': 'J. M. Barrie',         'publisher': 'Project Gutenberg', 'published_year': 1911, 'format': 'Paperback', 'pages': 224, 'language': 'English'},
    'jungle-book':               {'gutenberg_id': 236,   'author': 'Rudyard Kipling',      'publisher': 'Project Gutenberg', 'published_year': 1894, 'format': 'Paperback', 'pages': 288, 'language': 'English'},
    'grimms-fairy-tales':        {'gutenberg_id': 2591,  'author': 'Brothers Grimm',       'publisher': 'Project Gutenberg', 'published_year': 1812, 'format': 'Paperback', 'pages': 528, 'language': 'English'},
    'pinocchio':                 {'gutenberg_id': 500,   'author': 'Carlo Collodi',        'publisher': 'Project Gutenberg', 'published_year': 1883, 'format': 'Paperback', 'pages': 256, 'language': 'English'},
}
