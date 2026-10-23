---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/booking_marketplace/search.py

Symbols in `plugins/installed/booking_marketplace/search.py`.

- L156 `Doc` (class) — Something to find: its key (a pk), its kind and its (weight, text) fields.
- L164 `Term` (class) — A query word and the spellings that count as it (its singular, its synonyms).
- L171 `Matches` (class) — Score per key. `close`: no key matched every word, and these match some.
- L178 `_latin(text: str)` (function)
- L182 `_words(text: str)` (function)
- L187 `fold(text: str)` (function) — Lowercase Latin without accents, one space between words; `đ` becomes `d`.
- L192 `index_tokens(text: str)` (function) — A document's words. A word with `đ` is kept both ways (`durdevica`, `djurdjevica`):
- L202 `one_edit(a: str, b: str)` (function) — Whether `b` is `a` with one letter added, dropped or changed, or two neighbours swapped.
- L219 `_forms(word: str)` (function) — The word and its singular: `boats` also looks for `boat`, `beaches` for `beach`.
- L229 `parse_query(q: str)` (function) — The query's words, folded, without stopwords or repeats, each with its variants.
- L248 `Index` (class) — Folded words → {key: the best field weight the word appears in}, over `Doc`s.
- L251 `__init__(self, docs)` (method)
- L267 `_lookup(self, word: str, *, prefix: bool)` (method)
- L276 `_hits(self, term: Term)` (method) — The words `term` matches, and how well. A typo is tried only when nothing
- L292 `_scores(self, term: Term, kind: str, within)` (method)
- L303 `find(self, terms, *, kind: str, within=None, fallback: bool=True)` (method) — Keys of `kind` (only those in `within`, when given) matching every term, scored.
- L335 `_flatten(value)` (function) — Highlights as text: strings, or the strings inside lists and dicts.
- L346 `_region_names()` (function) — Each region's label in English and in Serbian, so `boka` finds Kotor Bay.
- L362 `documents()` (function) — The active listings (both kinds) and places, as the index reads them.
- L391 `_version()` (function)
- L404 `bump(**_kwargs)` (function) — post_save / post_delete: every process rebuilds its index before its next search.
- L414 `listing_index()` (function) — This process's index of the store, rebuilt first when it is stale.
