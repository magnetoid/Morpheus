"""Curated book-buyer subreddits for Reddit Ads community targeting.

Reddit ad performance hinges on targeting the right communities; for a bookshop
those are genre-specific reader subreddits. This is a hand-picked, genre-grouped
list the dashboard surfaces and Linda recommends — so the merchant targets where
book buyers actually are. (Reddit sets targeting account-side; this is guidance,
not an API call — no unverified integration.)
"""

from __future__ import annotations

# {genre: [subreddit, ...]} — high-intent reader communities. Names only (no
# leading r/); the merchant adds them as Communities in Reddit Ads ad groups.
BOOK_COMMUNITIES: dict[str, list[str]] = {
    'General readers': ['books', 'suggestmeabook', 'booksuggestions', '52book', 'literature'],
    'Fantasy': ['Fantasy', 'fantasywriters', 'Fantasy_Bookclub'],
    'Sci-fi': ['printSF', 'sciencefiction', 'scifi'],
    'Romance': ['RomanceBooks', 'romancelandia'],
    'Mystery & thriller': ['mystery', 'thrillers', 'suggestmeabook'],
    'Horror': ['horrorlit', 'horror'],
    'Young adult': ['YAlit', 'YAwriters'],
    'Literary & classics': ['literature', 'ClassicBookClub', 'TrueLit'],
    'Comics & graphic novels': ['comicbooks', 'graphicnovels'],
    'Audiobooks': ['audiobooks'],
}


def all_communities() -> list[str]:
    """De-duplicated flat list of every recommended subreddit."""
    seen: list[str] = []
    for subs in BOOK_COMMUNITIES.values():
        for s in subs:
            if s not in seen:
                seen.append(s)
    return seen


def communities_for(genre: str) -> list[str]:
    """Recommended subreddits for a genre (case-insensitive prefix match), or
    the general-readers set when there's no match."""
    g = (genre or '').strip().lower()
    if not g:
        return BOOK_COMMUNITIES['General readers']
    for name, subs in BOOK_COMMUNITIES.items():
        if g in name.lower() or name.lower() in g:
            return subs
    return BOOK_COMMUNITIES['General readers']
