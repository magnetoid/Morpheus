"""Draw a book's social card: 1200x630, the whole cover on the left, the title,
author and the start of the description on the right.

Pillow only, no Django and no network: `render_card(cover, content, style)`
returns JPEG bytes, and the same inputs always give the same bytes. Nothing
here writes text of its own: it lays out what it is given, shortens what does
not fit, and leaves out a line no bundled font can draw rather than print empty
boxes. The cover is scaled to fit, never cropped or stretched.

The fonts are bundled in `fonts/` under the SIL Open Font License (Libre
Baskerville for the title and wordmark, Inter for the rest); reportlab's Vera,
already installed, is the last fallback.
"""

from __future__ import annotations

import contextlib
import os
import unicodedata
import warnings
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, UnidentifiedImageError

WIDTH, HEIGHT = 1200, 630
# Bump when the drawing changes: it is part of every card's fingerprint, so a
# new layout redraws each card the next time its page is asked for.
TEMPLATE_VERSION = 1

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
SERIF = str(FONT_DIR / 'LibreBaskerville.ttf')
SANS = str(FONT_DIR / 'Inter.ttf')
try:
    import reportlab

    VERA = os.path.join(os.path.dirname(reportlab.__file__), 'fonts', 'Vera.ttf')
except Exception:  # noqa: BLE001 — a dependency, but the card must not need it
    VERA = ''

# What a cover may be before it is decoded: read from storage by its stored
# name only (never a URL), at most this big, and decoded only after its header
# says it is a plain image of a sane size. Pillow's own bomb check stays on.
MAX_COVER_BYTES = 20 * 1024 * 1024
MAX_COVER_SIDE = 10_000
MAX_COVER_PIXELS = 40_000_000
MIN_COVER_SIDE = 64
# MPO: a JPEG holding more than one picture (phones, cameras); its first is drawn.
COVER_FORMATS = frozenset({'JPEG', 'MPO', 'PNG', 'WEBP', 'GIF'})

# Layout, in pixels of the 1200x630 card.
FRAME_INSET = 22
COVER_BOX = (60, 70, 450, 540)  # left, top, right, bottom: the cover fits inside
SHADOW_OFFSET = (10, 18)
SHADOW_BLUR = 16
# How far the blurred shadow reaches past its rectangle (Pillow's kernel is ~3 radii).
SHADOW_REACH = 3 * SHADOW_BLUR
DIVIDER_X = 510
TEXT_LEFT = 568
TEXT_RIGHT = WIDTH - 76  # the text reaches to about 76 px from the right edge
TEXT_TOP, TEXT_BOTTOM = 84, 522
WORDMARK_TOP = 560

TITLE_SIZES = range(72, 38, -2)
TITLE_LINES = 3
AUTHOR_LINES = 2
DESCRIPTION_LINES = 3
ELLIPSIS = '…'

CREAM = (243, 235, 218)
MUTED = (214, 208, 196)


class CardError(Exception):
    """This book cannot have a card as things stand (a bad cover, a title no
    font can draw). Trying again with the same inputs gives the same answer."""


@dataclass(frozen=True)
class CardContent:
    title: str
    author: str = ''
    description: str = ''
    eyebrow: str = ''
    wordmark: str = ''


@dataclass(frozen=True)
class CardStyle:
    background: tuple[int, int, int] = (14, 29, 33)
    accent: tuple[int, int, int] = (200, 169, 106)


def parse_hex(value: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    """'#C8A96A' or 'c8a96a' → (200, 169, 106); anything else → `default`."""
    raw = (value or '').strip().lstrip('#')
    if len(raw) != 6:
        return default
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return default


def clean_text(value: str) -> str:
    """One line of plain text: NFC, controls dropped, whitespace collapsed."""
    text = unicodedata.normalize('NFC', value or '')
    text = ''.join(ch if unicodedata.category(ch)[0] != 'C' else ' ' for ch in text)
    return ' '.join(text.split())


# ── The cover ────────────────────────────────────────────────────────────────


def open_cover(fp, *, size_bytes: int | None = None) -> Image.Image:
    """Decode a cover from an open binary file, safely, as RGB.

    Refuses (CardError) a file over MAX_COVER_BYTES, anything that is not a
    JPEG (one picture or several), PNG, WebP or GIF, an image whose header
    claims more than MAX_COVER_PIXELS or a side over MAX_COVER_SIDE, and
    whatever Pillow cannot read or flags as a decompression bomb.
    """
    if size_bytes is not None and size_bytes > MAX_COVER_BYTES:
        raise CardError(f'cover file is {size_bytes} bytes, over {MAX_COVER_BYTES}')
    box_w, box_h = COVER_BOX[2] - COVER_BOX[0], COVER_BOX[3] - COVER_BOX[1]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            img = Image.open(fp)
            if img.format not in COVER_FORMATS:
                raise CardError(f'cover is {img.format or "not an image"}')
            w, h = img.size
            if min(w, h) < MIN_COVER_SIDE or max(w, h) > MAX_COVER_SIDE or w * h > MAX_COVER_PIXELS:
                raise CardError(f'cover is {w}x{h}')
            img.draft('RGB', (box_w * 2, box_h * 2))  # JPEG: decode at a smaller scale
            img.load()
            img = ImageOps.exif_transpose(img)
    except CardError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        EOFError,
    ) as e:
        raise CardError(f'cover cannot be read: {e}') from e
    if img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info):
        rgba = img.convert('RGBA')
        flat = Image.new('RGB', rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel('A'))
        return flat
    return img.convert('RGB')


# ── Fonts and text ───────────────────────────────────────────────────────────


@lru_cache(maxsize=64)
def _font(path: str, size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(path, size)
    try:
        axes = font.get_variation_axes()
    except OSError:  # not a variable font
        return font
    values = []
    for axis in axes:
        name = axis['name'].decode() if isinstance(axis['name'], bytes) else str(axis['name'])
        wanted = weight if name == 'Weight' else size if name.startswith('Optical') else None
        value = axis['default'] if wanted is None else wanted
        values.append(max(axis['minimum'], min(axis['maximum'], value)))
    with contextlib.suppress(OSError):
        font.set_variation_by_axes(values)
    return font


def _glyph_print(font: ImageFont.FreeTypeFont, ch: str) -> tuple:
    left, top, right, bottom = font.getbbox(ch)
    img = Image.new('L', (max(1, right - left) + 2, max(1, bottom - top) + 2))
    ImageDraw.Draw(img).text((1 - left, 1 - top), ch, font=font, fill=255)
    return (round(font.getlength(ch), 2), img.size, img.tobytes())


@lru_cache(maxsize=4096)
def _has_glyph(path: str, ch: str) -> bool:
    # A character the font does not map is drawn as its .notdef glyph, the same
    # as U+10FFFF, which no font maps.
    font = _font(path, 32)
    return _glyph_print(font, ch) != _glyph_print(font, '\U0010ffff')


def _covers(path: str, text: str) -> bool:
    return (
        bool(path)
        and os.path.exists(path)
        and all(_has_glyph(path, ch) for ch in set(text) if not ch.isspace())
    )


def _pick_font(text: str, chain: tuple[str, ...]) -> str | None:
    """The first font in `chain` that can draw every character of `text`."""
    return next((path for path in chain if _covers(path, text)), None)


def _width(text: str, font, tracking: float = 0) -> float:
    if not tracking:
        return font.getlength(text)
    return sum(font.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)


def _wrap(text: str, font, width: float, tracking: float = 0) -> list[str]:
    """Greedy word wrap by measured width; a word wider than a line is split."""
    lines: list[str] = []
    line = ''
    for word in text.split():
        candidate = f'{line} {word}' if line else word
        if _width(candidate, font, tracking) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        rest = word
        while _width(rest, font, tracking) > width and len(rest) > 1:
            cut = len(rest)
            while cut > 1 and _width(rest[:cut], font, tracking) > width:
                cut -= 1
            lines.append(rest[:cut])
            rest = rest[cut:]
        line = rest
    if line:
        lines.append(line)
    return lines


def _balanced(text: str, font, width: float) -> list[str]:
    """`text` in as many lines as a greedy wrap needs, split so that the
    longest line is as short as possible ("Partners / in Crime", not
    "Partners in / Crime")."""
    lines = _wrap(text, font, width)
    words = text.split()
    if not 2 <= len(lines) <= 3 or len(words) != sum(len(ln.split()) for ln in lines):
        return lines  # one line, or a word was split: keep the greedy wrap
    best, best_width = lines, max(font.getlength(ln) for ln in lines)
    n = len(words)
    cuts = (
        [(i,) for i in range(1, n)]
        if len(lines) == 2
        else [(i, j) for i in range(1, n - 1) for j in range(i + 1, n)]
    )
    for cut in cuts:
        bounds = (0, *cut, n)
        candidate = [' '.join(words[a:b]) for a, b in zip(bounds, bounds[1:], strict=False)]
        widest = max(font.getlength(ln) for ln in candidate)
        if widest <= width and widest < best_width - 0.5:
            best, best_width = candidate, widest
    return best


def _shorten(line: str, font, width: float, tracking: float = 0) -> str:
    """`line` cut at a word (or, failing that, a character) so that it fits with '…'."""
    words = line.split()
    while len(words) > 1:
        words.pop()
        candidate = ' '.join(words).rstrip(',;:–—-') + ELLIPSIS
        if _width(candidate, font, tracking) <= width:
            return candidate
    text = line
    while text and _width(text + ELLIPSIS, font, tracking) > width:
        text = text[:-1]
    return text.rstrip() + ELLIPSIS


def _fit(text: str, font, width: float, max_lines: int, tracking: float = 0) -> list[str]:
    lines = _wrap(text, font, width, tracking)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept[-1] = _shorten(f'{kept[-1]} {lines[max_lines]}', font, width, tracking)
    return kept


def _fit_description(text: str, font, width: float, max_lines: int) -> list[str]:
    """Whole sentences when some fit, else the text cut at a word with '…'."""
    if max_lines <= 0 or not text:
        return []
    lines = _wrap(text, font, width)
    if len(lines) <= max_lines:
        return lines
    sentences = [s for s in _sentences(text)]
    for end in range(len(sentences) - 1, 0, -1):
        head = ' '.join(sentences[:end])
        head_lines = _wrap(head, font, width)
        if len(head_lines) <= max_lines:
            return head_lines
    return _fit(text, font, width, max_lines)


def _sentences(text: str) -> list[str]:
    out, start = [], 0
    for i, ch in enumerate(text):
        if ch in '.!?' and (i + 1 == len(text) or text[i + 1] == ' '):
            out.append(text[start : i + 1].strip())
            start = i + 1
    rest = text[start:].strip()
    if rest:
        out.append(rest)
    return out


def _draw_tracked(draw, xy, text: str, font, fill, tracking: float) -> None:
    x, y = xy
    if not tracking:
        draw.text((x, y), text, font=font, fill=fill)
        return
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking


def _mix(a: tuple, b: tuple, amount: float) -> tuple[int, int, int]:
    """`amount` of colour a over colour b."""
    return tuple(round(a[i] * amount + b[i] * (1 - amount)) for i in range(3))


# ── Layout ───────────────────────────────────────────────────────────────────


@dataclass
class _Line:
    text: str
    font: ImageFont.FreeTypeFont
    fill: tuple
    height: int  # line box height
    tracking: float = 0


def _text_block(content: CardContent, style: CardStyle) -> list[tuple[str, object]]:
    """The right-hand column as a list of ('line', _Line) / ('gap', px) / ('rule', None)."""
    width = TEXT_RIGHT - TEXT_LEFT
    title_path = _pick_font(content.title, (SERIF, SANS, VERA))
    if not content.title or title_path is None:
        raise CardError('the title cannot be drawn with the bundled fonts')

    def caps(text: str, size: int, weight: int, tracking: float, max_lines: int):
        text = text.upper()
        path = _pick_font(text, (SANS, VERA))
        if not text or path is None:
            return []
        font = _font(path, size, weight)
        return [
            _Line(t, font, style.accent, round(size * 1.3), tracking)
            for t in _fit(text, font, width, max_lines, tracking)
        ]

    eyebrow = caps(content.eyebrow, 17, 500, 1.7, 1)
    author = caps(content.author, 19, 600, 1.5, AUTHOR_LINES)
    desc_path = _pick_font(content.description, (SANS, VERA)) if content.description else None
    desc_font = _font(desc_path, 22, 400) if desc_path else None
    available = TEXT_BOTTOM - TEXT_TOP

    def assemble(title_size: int, desc_lines: int):
        font = _font(title_path, title_size, 400)
        wrapped = _wrap(content.title, font, width)
        title_lines = (
            _balanced(content.title, font, width)
            if len(wrapped) <= TITLE_LINES
            else _fit(content.title, font, width, TITLE_LINES)
        )
        title = [_Line(t, font, CREAM, round(title_size * 1.14)) for t in title_lines]
        desc = (
            [
                _Line(t, desc_font, MUTED, 32)
                for t in _fit_description(content.description, desc_font, width, desc_lines)
            ]
            if desc_font
            else []
        )
        parts: list[tuple[str, object]] = []
        if eyebrow:
            parts += [('line', ln) for ln in eyebrow] + [('gap', 26)]
        parts += [('line', ln) for ln in title] + [('gap', 30), ('rule', None), ('gap', 28)]
        if author:
            parts += [('line', ln) for ln in author]
        if desc:
            parts += [('gap', 18 if author else 0)] + [('line', ln) for ln in desc]
        return parts

    def height(parts) -> int:
        return sum(p[1].height if p[0] == 'line' else p[1] if p[0] == 'gap' else 2 for p in parts)

    def title_wraps(title_size: int) -> bool:
        font = _font(title_path, title_size, 400)
        return len(_wrap(content.title, font, width)) <= TITLE_LINES

    # The biggest title that wraps into its lines, then as much description as
    # the column holds at that size; a smaller title before less description.
    for desc_lines in range(DESCRIPTION_LINES, -1, -1):
        for size in TITLE_SIZES:
            if not title_wraps(size) and size != TITLE_SIZES[-1]:
                continue
            parts = assemble(size, desc_lines)
            if height(parts) <= available:
                return parts
    return assemble(TITLE_SIZES[-1], 0)


def cover_rect(size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Where a cover of `size` goes: (x, y, width, height), the whole cover
    scaled to fit COVER_BOX with its proportions kept, centred in it."""
    box_w, box_h = COVER_BOX[2] - COVER_BOX[0], COVER_BOX[3] - COVER_BOX[1]
    cw, ch = size
    scale = min(box_w / cw, box_h / ch)
    w = max(1, min(box_w, round(cw * scale)))
    h = max(1, min(box_h, round(ch * scale)))
    return COVER_BOX[0] + (box_w - w) // 2, COVER_BOX[1] + (box_h - h) // 2, w, h


def render_card(cover: Image.Image, content: CardContent, style: CardStyle | None = None) -> bytes:
    """The card as JPEG bytes (1200x630, RGB)."""
    style = style or CardStyle()
    bg, accent = style.background, style.accent
    card = Image.new('RGB', (WIDTH, HEIGHT), bg)

    # A faint light behind the cover, so the dark ground is not flat.
    glow = Image.radial_gradient('L').resize((900, 900)).point(lambda v: round((255 - v) * 0.16))
    lighter = Image.new('RGB', (WIDTH, HEIGHT), _mix((255, 255, 255), bg, 0.10))
    mask = Image.new('L', (WIDTH, HEIGHT), 0)
    cx = (COVER_BOX[0] + COVER_BOX[2]) // 2
    cy = (COVER_BOX[1] + COVER_BOX[3]) // 2
    mask.paste(glow, (cx - 450, cy - 450))
    card = Image.composite(lighter, card, mask)

    draw = ImageDraw.Draw(card)
    draw.rectangle(
        [FRAME_INSET, FRAME_INSET, WIDTH - 1 - FRAME_INSET, HEIGHT - 1 - FRAME_INSET],
        outline=_mix(accent, bg, 0.55),
        width=1,
    )

    # The cover, whole, centred in its box, on a soft shadow.
    x, y, w, h = cover_rect(cover.size)
    art = cover.resize((w, h), Image.Resampling.LANCZOS)
    shadow = Image.new('L', (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(shadow).rectangle(
        [
            x + SHADOW_OFFSET[0],
            y + SHADOW_OFFSET[1],
            x + art.width + SHADOW_OFFSET[0],
            y + art.height + SHADOW_OFFSET[1],
        ],
        fill=150,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    card = Image.composite(Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0)), card, shadow)
    card.paste(art, (x, y))
    draw = ImageDraw.Draw(card)

    draw.line(
        [(DIVIDER_X, COVER_BOX[1] + 14), (DIVIDER_X, COVER_BOX[3] + 6)],
        fill=_mix(accent, bg, 0.5),
        width=1,
    )

    parts = _text_block(content, style)
    total = sum(p[1].height if p[0] == 'line' else p[1] if p[0] == 'gap' else 2 for p in parts)
    ty = TEXT_TOP + max(0, (TEXT_BOTTOM - TEXT_TOP - total) // 2)
    for kind, value in parts:
        if kind == 'gap':
            ty += value
        elif kind == 'rule':
            draw.rectangle([TEXT_LEFT, ty, TEXT_LEFT + 87, ty + 1], fill=accent)
            ty += 2
        else:
            # Line boxes are taller than the glyphs; sit the text near the top
            # of its box so the space falls under it.
            top = value.font.getbbox('Hg')[1]
            shift = (value.height - (value.font.getbbox('Hg')[3] - top)) // 3
            _draw_tracked(
                draw,
                (TEXT_LEFT, ty + shift - top),
                value.text,
                value.font,
                value.fill,
                value.tracking,
            )
            ty += value.height

    wordmark = content.wordmark.upper()
    mark_path = _pick_font(wordmark, (SERIF, SANS, VERA)) if wordmark else None
    if mark_path:
        font = _font(mark_path, 21, 400)
        line = _fit(wordmark, font, TEXT_RIGHT - TEXT_LEFT, 1, 1.2)[0]
        _draw_tracked(draw, (TEXT_LEFT, WORDMARK_TOP), line, font, CREAM, 1.2)

    out = BytesIO()
    card.save(out, 'JPEG', quality=90, optimize=True, progressive=True, subsampling=0)
    return out.getvalue()
