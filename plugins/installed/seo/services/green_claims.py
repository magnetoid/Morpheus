"""Environmental claims in what a page shows (v0.178.0).

Directive (EU) 2024/825 applies from 27 September 2026. It bans two kinds of claim
outright (Annex I of Directive 2005/29/EC, points 4a and 4c):

- a **generic environmental claim** ("eco-friendly", "green", "ecological") for which
  the trader cannot show recognised excellent environmental performance (recital 9
  lists the examples this module looks for);
- a claim, **based on offsetting** greenhouse-gas emissions, that a product has a
  neutral, reduced or positive impact ("climate neutral", "CO2 neutral", "climate
  compensated"; recital 12).

The site audit runs every rendered page through `Matcher.find`, and each hit is a
finding that names the page and the phrase, for the merchant to substantiate or
remove. A hit is something to check, not a verdict: a book ABOUT ecology is not a
claim about the book. So the check only reports, never edits anything.

Text is folded before matching (lower case, Serbian Cyrillic to Latin, accents
and đ dropped), so one list covers Croatian and Serbian in either script, typed with
or without diacritics. In a pattern a space stands for any run of spaces or hyphens
and `~` for an optional one: `eco~friendly` matches "eco-friendly", "eco friendly"
and "ecofriendly".
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger('morpheus.seo.green_claims')

GENERIC = 'generic'
OFFSET = 'offset'

_STEM = r'[a-z0-9]*'

# Most specific first: at one position the first alternative that matches wins, so
# "ecologically friendly" is reported whole rather than as "ecologically".
_PATTERNS: dict[str, tuple[str, ...]] = {
    OFFSET: (
        # English (recital 12: climate neutral, CO2 neutral certified, carbon
        # positive, climate net zero, climate compensated, reduced climate impact,
        # limited CO2 footprint).
        r'(?:climate|carbon|co~2|ghg|greenhouse gas) neutral(?:ity)?',
        r'(?:climate|carbon) (?:positive|negative)',
        r'(?:climate )?net~zero',
        r'(?:climate|carbon|co~2|emissions?) compensated',
        r'compensat(?:e|es|ed|ing)(?: [a-z0-9]+){0,2} (?:carbon|co~2|emissions?|footprint)',
        r'carbon~offset(?:s|ting)?',
        r'offset(?:s|ting)?(?: (?:this|your|the|our|each|every))?(?: (?:order|purchase)(?:\'s)?)?'
        r' (?:carbon )?(?:footprint|emissions?|carbon|co~2)',
        r'reduced (?:climate|carbon|co~2) (?:impact|footprint)',
        r'limited (?:co~2|carbon) footprint',
        r'zero (?:carbon|emissions?)',
        # Croatian and Serbian (folded): klimatski / ugljično / ugljenično / CO2
        # neutralan, klimatski pozitivan, neto nula, kompenzacija emisija.
        rf'(?:klimatsk{_STEM}|ugljicn{_STEM}|ugljenicn{_STEM}|ugljik{_STEM}|co~2) neutral{_STEM}',
        rf'(?:klimatsk{_STEM}|ugljicn{_STEM}|ugljenicn{_STEM}) pozitiv{_STEM}',
        rf'neto~nul{_STEM}',
        rf'nult{_STEM} neto',
        rf'kompenz{_STEM}(?: [a-z0-9]+){{0,2}} (?:co~2|uglj{_STEM}|emisij{_STEM}|otis{_STEM})',
        rf'smanjen{_STEM} (?:klimatsk{_STEM}|ugljicn{_STEM}|ugljenicn{_STEM}|co~2)'
        rf' (?:utjecaj{_STEM}|uticaj{_STEM}|otis{_STEM})',
    ),
    GENERIC: (
        # English (recital 9: environmentally friendly, eco-friendly, green, nature's
        # friend, ecological, environmentally correct, climate friendly, gentle on the
        # environment, carbon friendly, energy efficient, biodegradable, biobased).
        r'environment(?:ally)?~friendly',
        r'ecological(?:ly)? friendly',
        r'(?:eco|earth|planet|nature|climate|carbon)~friendly',
        r"nature'?s friend",
        r'environmentally (?:correct|sound|responsible|safe|conscious)',
        r'(?:gentle|kind) (?:on|to) the (?:environment|planet|earth)',
        r'energy~efficient',
        r'bio~degradable',
        r'bio~based',
        r'green (?:products?|choices?|alternatives?)',
        r'ecological(?:ly)?',
        # Croatian and Serbian (folded): ekološki prihvatljiv, prijatelj prirode,
        # prihvatljiv za okoliš / životnu sredinu, klimatski prihvatljiv,
        # biorazgradiv, energetski učinkovit / efikasan, eko proizvod, ekološki.
        rf'ekolosk{_STEM} (?:prihvatljiv{_STEM}|cist{_STEM}|isprav{_STEM})',
        rf'eko~(?:prihvatljiv{_STEM}|proizvod{_STEM})',
        rf'prihvatljiv{_STEM} (?:za|prema) (?:okolis{_STEM}|prirod{_STEM}|zivotn{_STEM} sredin{_STEM})',
        rf'prijatelj{_STEM} (?:(?:prema|za) )?(?:okolis{_STEM}|prirod{_STEM}|zivotn{_STEM} sredin{_STEM}|planet{_STEM})',
        rf'njez{_STEM} (?:prema|za) (?:okolis{_STEM}|prirod{_STEM}|zivotn{_STEM} sredin{_STEM})',
        rf'klimatsk{_STEM} prihvatljiv{_STEM}',
        rf'zelen{_STEM} (?:proizvod{_STEM}|izbor{_STEM})',
        rf'biorazgradiv{_STEM}',
        rf'energetsk{_STEM} (?:ucinkovit{_STEM}|efikas{_STEM})',
        rf'ekolosk{_STEM}',
    ),
}

# Serbian Cyrillic, straight to the folded Latin the patterns are written in.
_CYRILLIC = dict(
    zip(
        'абвгдђежзијклљмнњопрстћуфхцчџш',
        [
            'a',
            'b',
            'v',
            'g',
            'd',
            'd',
            'e',
            'z',
            'z',
            'i',
            'j',
            'k',
            'l',
            'lj',
            'm',
            'n',
            'nj',
            'o',
            'p',
            'r',
            's',
            't',
            'c',
            'u',
            'f',
            'h',
            'c',
            'c',
            'dz',
            's',
        ],
        strict=True,
    )
)
_SAME = {
    'đ': 'd',
    '’': "'",
    '‘': "'",
    'ʼ': "'",
    '‐': '-',
    '‑': '-',
    '‒': '-',
    '–': '-',
    '—': '-',
}
SNIPPET_CHARS = 50


def fold(text: str) -> tuple[str, list[int]]:
    """`text` folded for matching, and for each folded character its index in `text`."""
    out: list[str] = []
    where: list[int] = []
    for i, ch in enumerate(text or ''):
        low = ch.lower()
        rep = _CYRILLIC.get(low) or _SAME.get(low)
        if rep is None:
            rep = ''.join(
                c for c in unicodedata.normalize('NFKD', low) if not unicodedata.combining(c)
            )
        for c in rep:
            out.append(c)
            where.append(i)
    return ''.join(out), where


def _regex(pattern: str) -> str:
    return pattern.replace('~', r'[\s\-]*').replace(' ', r'[\s\-]+')


def _literal(phrase: str) -> str:
    """A merchant's own phrase as a pattern: folded, escaped, spaces flexible."""
    folded, _ = fold(phrase.strip())
    words = [re.escape(w) for w in re.split(r'[\s\-]+', folded) if w]
    return r'[\s\-]+'.join(words)


def _compile(alternatives: list[str]) -> re.Pattern | None:
    if not alternatives:
        return None
    return re.compile(r'(?<![a-z0-9])(?:' + '|'.join(alternatives) + r')(?![a-z0-9])')


@dataclass(frozen=True)
class Hit:
    kind: str
    phrase: str  # as the page shows it
    snippet: str  # the words around it

    @property
    def key(self) -> str:
        """The phrase without case, accents, script, spaces or hyphens."""
        return _key(fold(self.phrase)[0])


class Matcher:
    """Finds the claims in a page's visible text."""

    def __init__(self, extra_words: list[str] | tuple[str, ...] = ()):
        self._kinds: list[tuple[str, re.Pattern]] = []
        for kind in (OFFSET, GENERIC):
            alternatives = [_regex(p) for p in _PATTERNS[kind]]
            if kind == GENERIC:
                # The merchant's own words go first, so a phrase they named is
                # reported as they wrote it, not as a shorter built-in match.
                own = [_literal(w) for w in extra_words if str(w or '').strip()]
                alternatives = [a for a in own if a] + alternatives
            compiled = _compile(alternatives)
            if compiled is not None:
                self._kinds.append((kind, compiled))

    def find(self, text: str) -> list[Hit]:
        """Each claim once per page: the first place each phrase appears."""
        if not text:
            return []
        folded, where = fold(text)
        spans: list[tuple[int, int]] = []
        seen: set[tuple[str, str]] = set()
        hits: list[Hit] = []
        for kind, pattern in self._kinds:
            for match in pattern.finditer(folded):
                start, end = match.span()
                if any(s < end and start < e for s, e in spans):
                    continue  # already reported as an offset claim
                spans.append((start, end))
                key = (kind, _key(match.group(0)))
                if key in seen:
                    continue
                seen.add(key)
                first, last = where[start], where[end - 1] + 1
                hits.append(Hit(kind, text[first:last], _snippet(text, first, last)))
        return hits


def _key(folded: str) -> str:
    return re.sub(r'[\s\-]+', '', folded)


def _snippet(text: str, start: int, end: int) -> str:
    """The words around `text[start:end]`, cut at word boundaries."""
    left = text[max(0, start - SNIPPET_CHARS) : start]
    right = text[end : end + SNIPPET_CHARS]
    if start - SNIPPET_CHARS > 0 and ' ' in left:
        left = '…' + left.split(' ', 1)[1]
    if end + SNIPPET_CHARS < len(text) and ' ' in right:
        right = right.rsplit(' ', 1)[0] + '…'
    return (left + text[start:end] + right).strip()


def _setting(key: str, default):
    try:
        from plugins.registry import app_registry

        seo = app_registry.get('seo')
        if seo is not None:
            return seo.get_config_value(key, default)
    except Exception:  # noqa: BLE001 — a settings glitch falls back to the default
        logger.debug('green_claims: could not read seo.%s', key, exc_info=True)
    return default


def matcher() -> Matcher | None:
    """The store's matcher, or None while the check is switched off."""
    if not _setting('claims_check', True):
        return None
    extra = _setting('claims_extra_words', []) or []
    if isinstance(extra, str):
        extra = [w for w in re.split(r'[,\n]', extra)]
    return Matcher([str(w) for w in extra if str(w).strip()])
