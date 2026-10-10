"""Build a product's Web Story: plain text, a page per idea, a real poster.

``build_panels_for(product)`` turns a product into pages, each saying one
thing:

  1. cover    — the main photo, the product name, a byline or its category
  2. lead     — the opening sentences of the short description
  3. points   — up to four bullets: the description's list items, or the
                sentences after the lead
  4. detail   — the description's first paragraph, when it adds something
  5. image    — every photo not used yet, with its alt text
  6. synopsis — a book's synopsis (book_product)
  7. cta      — the product name over its photo, and the AMP outlink button

The text in a product is rich text from the editor (``<p><span>…``), so every
string a page carries goes through ``extract``/``plain_text`` and is cut at a
sentence or word with ``clip`` — slicing the raw HTML is what put
``&lt;p&gt;`` on screen (2026-10-10).

``ensure_story(product)`` get-or-creates the WebStory row, rebuilds its pages
and makes the poster: a 720×960 (3:4) JPEG of the main photo on the photo's
own border colour, as Google asks (portrait, at least 640×853, raster). The
poster is reused while the photo is unchanged and the old file is removed when
it changes. Each photo is also measured once: a product shot on a plain
background is shown whole on that colour, a full-bleed photo fills the page.
"""

from __future__ import annotations

import hashlib
import html
import io
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger('morpheus.webstories')

#: Bumped when the page shape changes; a story built by an older builder is
#: rebuilt the first time it is viewed (views.story_page).
BUILDER_VERSION = 2

POSTER_SIZE = (720, 960)  # 3:4, above Google's 640×853 minimum
POSTER_DIR = 'webstories/posters'

_MAX_IMAGES = 5
_TITLE_MAX = 80
_BYLINE_MAX = 80
_LEAD_MAX = 200
_DETAIL_MAX = 220
_POINT_MAX = 90
_MAX_POINTS = 4
_CAPTION_MAX = 140
_ALT_MAX = 125
_SYNOPSIS_MAX = 260
_SUMMARY_MAX = 280

_SKIP_TAGS = frozenset({'script', 'style', 'template', 'noscript'})
_BLOCK_TAGS = frozenset(
    {
        'p', 'div', 'section', 'article', 'blockquote', 'pre', 'header', 'footer',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'dl', 'dt', 'dd',
        'table', 'tr', 'td', 'th', 'figure', 'figcaption',
    }
)  # fmt: skip
_SPACE = re.compile(r'\s+')
_BULLET = re.compile(r'^\s*(?:[-*•–]|\d+[.)])\s+')
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+')
_TERMINAL = ('.', '!', '?', '…', ':')


# ── Text ──────────────────────────────────────────────────────────────────


@dataclass
class Text:
    """Rich text as blocks: paragraphs and list items, each plain."""

    paragraphs: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    order: list[str] = field(default_factory=list)  # every block, document order


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text = Text()
        self._parts: list[str] = []
        self._in_item = 0
        self._skip = 0

    def _flush(self) -> None:
        chunk = _SPACE.sub(' ', ''.join(self._parts)).strip()
        self._parts = []
        if not chunk:
            return
        (self.text.items if self._in_item else self.text.paragraphs).append(chunk)
        self.text.order.append(chunk)

    def handle_starttag(self, tag, attrs):  # noqa: ARG002
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == 'li':
            self._flush()
            self._in_item += 1
        elif tag == 'br':
            self._parts.append(' ')
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag == 'li':
            self._flush()
            self._in_item = max(0, self._in_item - 1)
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def close(self):
        super().close()
        self._flush()


def _extract_plain(raw: str) -> Text:
    """Text with no markup: blank lines part paragraphs, ``- `` lines are items."""
    text = Text()
    paragraph: list[str] = []

    def end_paragraph():
        chunk = _SPACE.sub(' ', ' '.join(paragraph)).strip()
        paragraph.clear()
        if chunk:
            text.paragraphs.append(chunk)
            text.order.append(chunk)

    for line in html.unescape(raw).splitlines():
        if not line.strip():
            end_paragraph()
        elif _BULLET.match(line):
            end_paragraph()
            item = _SPACE.sub(' ', _BULLET.sub('', line)).strip()
            if item:
                text.items.append(item)
                text.order.append(item)
        else:
            paragraph.append(line)
    end_paragraph()
    return text


def extract(value) -> Text:
    """Paragraphs and list items of a product's rich (or plain) text."""
    raw = str(value or '')
    if '<' not in raw:
        return _extract_plain(raw)
    parser = _Extractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:  # noqa: BLE001 — malformed markup: keep what was read
        parser._flush()
    return parser.text


def plain_text(value) -> str:
    """One line of plain text; blocks end with a full stop when they have none."""
    blocks = extract(value).order
    if len(blocks) > 1:
        blocks = [b if b.endswith(_TERMINAL) else f'{b}.' for b in blocks]
    return ' '.join(blocks)


def clip(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` characters at a sentence end, else a word (…)."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    window = text[:limit]
    floor = int(limit * 0.5)
    sentence_end = -1
    for m in re.finditer(r'[.!?…](?=\s|$)', window):
        if m.end() >= floor:
            sentence_end = m.end()
    if sentence_end > 0:
        return window[:sentence_end].strip()
    cut = window[: limit - 1]
    space = cut.rfind(' ')
    if space >= floor:
        cut = cut[:space]
    return cut.rstrip(' ,;:–-') + '…'


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or '') if s.strip()]


def _lead(parts: list[str], limit: int) -> tuple[str, int]:
    """As many opening sentences as fit in ``limit``, and how many were used."""
    out, used = '', 0
    for sentence in parts:
        candidate = f'{out} {sentence}'.strip()
        if len(candidate) > limit:
            break
        out, used = candidate, used + 1
    if not out and parts:
        return clip(parts[0], limit), 1
    return out, used


def _same(a: str, b: str) -> bool:
    """Do two texts say the same thing (one opens with the other)?"""
    x, y = a.lower()[:60], b.lower()[:60]
    return bool(x and y) and (x.startswith(y[:40]) or y.startswith(x[:40]))


# ── Images ────────────────────────────────────────────────────────────────


def _image_url_for(image_row) -> str:
    """Prefer the WebP variant (smaller, AMP-friendly) when present."""
    if getattr(image_row, 'webp_image', None) and image_row.webp_image.name:
        return image_row.webp_image.url
    if getattr(image_row, 'image', None) and image_row.image.name:
        return image_row.image.url
    return ''


def _local_name(image_row) -> str:
    """The media-relative file name when the file is on local storage — what
    the image proxy (``/img/<fmt>/<width>/<name>``) can resize. '' otherwise."""
    name = getattr(getattr(image_row, 'image', None), 'name', '') or ''
    if not name:
        return ''
    try:
        from django.core.files.storage import FileSystemStorage, default_storage  # noqa: PLC0415

        if isinstance(default_storage, FileSystemStorage) and default_storage.exists(name):
            return name
    except Exception:  # noqa: BLE001
        logger.debug('webstories: storage check failed for %s', name, exc_info=True)
    return ''


def _open_rgb(name: str):
    """The stored photo as an RGB Pillow image; transparency becomes white."""
    from django.core.files.storage import default_storage  # noqa: PLC0415
    from PIL import Image, ImageOps  # noqa: PLC0415

    with default_storage.open(name, 'rb') as fh:
        data = fh.read()
    with Image.open(io.BytesIO(data)) as src:
        img = ImageOps.exif_transpose(src)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            rgba = img.convert('RGBA')
            flat = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
            flat.alpha_composite(rgba)
            return flat.convert('RGB')
        return img.convert('RGB')


def _border(img) -> tuple[tuple[int, int, int], float]:
    """The median colour of the photo's outer edge, and how much it varies."""
    from PIL import ImageStat  # noqa: PLC0415

    thumb = img.copy()
    thumb.thumbnail((240, 240))
    w, h = thumb.size
    strips = [
        thumb.crop((0, 0, w, 2)),
        thumb.crop((0, h - 2, w, h)),
        thumb.crop((0, 0, 2, h)),
        thumb.crop((w - 2, 0, w, h)),
    ]
    stats = [ImageStat.Stat(s) for s in strips]
    colour = tuple(
        sorted(channel)[len(channel) // 2]
        for channel in zip(*(s.median for s in stats), strict=True)
    )
    spread = max(max(s.stddev) for s in stats)
    return (int(colour[0]), int(colour[1]), int(colour[2])), float(spread)


def _look(name: str) -> dict[str, str]:
    """How a photo sits on a page: shown whole on its own background colour
    when it is a product shot on a plain backdrop, filling the page otherwise.
    Cached per file, so a product saved again is not decoded again."""
    from django.core.cache import cache  # noqa: PLC0415

    key = f'webstories:look:{hashlib.sha256(name.encode()).hexdigest()[:32]}'
    cached = cache.get(key)
    if cached:
        return cached
    look = {'fit': 'cover', 'bg': '#1a1a1a', 'tone': 'dark'}
    try:
        (r, g, b), spread = _border(_open_rgb(name))
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        look = {
            'fit': 'contain' if spread < 18 else 'cover',
            'bg': f'#{r:02x}{g:02x}{b:02x}',
            'tone': 'light' if luminance > 150 else 'dark',
        }
        if look['fit'] == 'cover':
            look['tone'] = 'dark'  # white text on the gradient over a photo
    except Exception:  # noqa: BLE001 — an unreadable photo still gets a page
        logger.debug('webstories: could not measure %s', name, exc_info=True)
    cache.set(key, look, timeout=60 * 60 * 24 * 30)
    return look


def _render_poster(data_name: str) -> bytes:
    """The 3:4 poster JPEG for a stored photo."""
    from PIL import Image, ImageOps  # noqa: PLC0415

    img = _open_rgb(data_name)
    colour, _spread = _border(img)
    width, height = POSTER_SIZE
    canvas = Image.new('RGB', (width, height), colour)
    fitted = ImageOps.contain(
        img, (int(width * 0.88), int(height * 0.88)), Image.Resampling.LANCZOS
    )
    canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    buf = io.BytesIO()
    canvas.save(buf, 'JPEG', quality=86, optimize=True, progressive=True)
    return buf.getvalue()


def _media_name(url: str) -> str:
    from django.conf import settings  # noqa: PLC0415

    prefix = settings.MEDIA_URL or '/media/'
    return url[len(prefix) :] if url and url.startswith(prefix) else ''


def _poster_for(product, image_row) -> str:
    """URL of the product's 3:4 poster, made once per photo; '' on failure."""
    name = getattr(getattr(image_row, 'image', None), 'name', '') or ''
    if not name:
        return ''
    from django.core.files.base import ContentFile  # noqa: PLC0415
    from django.core.files.storage import default_storage  # noqa: PLC0415

    try:
        try:
            size = default_storage.size(name)
        except Exception:  # noqa: BLE001
            size = 0
        digest = hashlib.sha256(f'{name}:{size}:{BUILDER_VERSION}'.encode()).hexdigest()[:12]
        target = f'{POSTER_DIR}/{product.pk}-{digest}.jpg'
        if not default_storage.exists(target):
            target = default_storage.save(target, ContentFile(_render_poster(name)))
        return default_storage.url(target)
    except Exception:  # noqa: BLE001 — the photo itself still works as a poster
        logger.warning(
            'webstories: poster for %s failed', getattr(product, 'pk', '?'), exc_info=True
        )
        return ''


def _drop_old_poster(old_url: str, new_url: str) -> None:
    if not old_url or old_url == new_url:
        return
    name = _media_name(old_url)
    if not name.startswith(f'{POSTER_DIR}/'):
        return
    try:
        from django.core.files.storage import default_storage  # noqa: PLC0415

        default_storage.delete(name)
    except Exception:  # noqa: BLE001
        logger.debug('webstories: could not remove %s', name, exc_info=True)


# ── Pages ─────────────────────────────────────────────────────────────────


def _book_metafields(product) -> dict[str, str]:
    """Book attributes (synopsis / author / …) for the story panels.

    Model-first (BookProduct) with a legacy book.* metafield fallback; empty
    when book_product/metafields aren't available.

    Empty while the book app is off, without asking it: a store that runs
    without it has no `plugins_bookproduct` table, and on Postgres the failed
    query aborted the product save's transaction even though it was caught."""
    from plugins.registry import app_registry  # noqa: PLC0415

    if not app_registry.is_active('book_product'):
        return {}
    try:
        from plugins.installed.book_product.compat import book_attrs  # noqa: PLC0415

        return book_attrs(product)
    except Exception as e:  # noqa: BLE001
        logger.debug('webstories: book attrs skipped: %s', e)
        return {}


class _Images:
    """Hands out the product's photos in order, then the main one again."""

    def __init__(self, rows: list) -> None:
        self.rows = rows
        self._next = 0

    def take(self):
        if not self.rows:
            return None
        if self._next < len(self.rows):
            row = self.rows[self._next]
            self._next += 1
            return row
        return self.rows[0]

    def rest(self) -> list:
        left = self.rows[self._next :]
        self._next = len(self.rows)
        return left


def _page(kind: str, image_row, *, alt_fallback: str, **fields) -> dict[str, Any]:
    page: dict[str, Any] = {'v': BUILDER_VERSION, 'kind': kind, 'image_url': '', 'image_path': ''}
    if image_row is not None:
        page['image_url'] = _image_url_for(image_row)
        page['image_path'] = _local_name(image_row)
        alt = plain_text(getattr(image_row, 'alt_text', '') or '') or alt_fallback
        page['alt'] = clip(alt, _ALT_MAX)
        page.update(_look(page['image_path']) if page['image_path'] else {})
    page.update({k: v for k, v in fields.items() if v not in (None, '', [])})
    return page


def build_panels_for(product) -> list[dict[str, Any]]:
    """Pages for ``product``, each saying one thing. Side-effect-free."""
    rows = list(product.images.order_by('-is_primary', 'sort_order')[:_MAX_IMAGES])
    images = _Images(rows)
    name = clip(plain_text(product.name or ''), _TITLE_MAX)
    short = extract(product.short_description)
    long = extract(product.description)
    book = _book_metafields(product)
    pages: list[dict[str, Any]] = []

    # 1 — cover
    author = plain_text(book.get('author') or '')
    category = getattr(getattr(product, 'category', None), 'name', '') or ''
    byline = f'by {author}' if author else category
    pages.append(
        _page(
            'cover', images.take(), alt_fallback=name, title=name, caption=clip(byline, _BYLINE_MAX)
        )
    )

    # 2 — lead: the opening sentences
    opening = sentences(' '.join(short.paragraphs) or ' '.join(long.paragraphs))
    lead, used = _lead(opening, _LEAD_MAX)
    if lead:
        pages.append(_page('lead', images.take(), alt_fallback=name, caption=lead))

    # 3 — points: list items, else the sentences after the lead
    points: list[str] = []
    for raw_item in [*short.items, *long.items]:
        item = clip(raw_item, _POINT_MAX)
        if item and item not in points and not _same(item, lead):
            points.append(item)
    if len(points) < 2:
        later = opening[used:] + [
            s for s in sentences(' '.join(long.paragraphs)) if s not in opening[:used]
        ]
        for raw_sentence in later:
            sentence = clip(raw_sentence, _POINT_MAX)
            if sentence not in points and not _same(sentence, lead):
                points.append(sentence)
            if len(points) >= _MAX_POINTS:
                break
    points = points[:_MAX_POINTS]
    if len(points) >= 2:
        pages.append(_page('points', images.take(), alt_fallback=name, points=points))

    # 4 — detail: the description's first paragraph, when it adds something
    for paragraph in long.paragraphs:
        detail = clip(paragraph, _DETAIL_MAX)
        if (
            detail
            and not _same(detail, lead)
            and not any(_same(detail, p) for p in points)
            and not any(s in points for s in sentences(detail))
        ):
            pages.append(_page('detail', images.take(), alt_fallback=name, caption=detail))
            break

    # 5 — the photos not shown yet
    for row in images.rest():
        caption = clip(plain_text(getattr(row, 'alt_text', '') or ''), _CAPTION_MAX)
        pages.append(_page('image', row, alt_fallback=name, caption=caption))

    # 6 — a book's synopsis
    synopsis = clip(plain_text(book.get('synopsis') or ''), _SYNOPSIS_MAX)
    if synopsis and not _same(synopsis, lead):
        pages.append(
            _page('synopsis', rows[0] if rows else None, alt_fallback=name, caption=synopsis)
        )

    # 7 — the call to action
    pages.append(
        _page(
            'cta',
            rows[0] if rows else None,
            alt_fallback=name,
            title=name,
            cta_url=f'/products/{product.slug}/',
        )
    )
    return pages


def ensure_story(product) -> tuple[Any, bool]:
    """Get-or-create the WebStory for ``product``, rebuild its pages and poster.

    Returns ``(story, changed)``; ``changed`` is always True today."""
    from plugins.installed.webstories.models import WebStory  # noqa: PLC0415

    panels = build_panels_for(product)
    rows = list(product.images.order_by('-is_primary', 'sort_order')[:1])
    poster = (_poster_for(product, rows[0]) if rows else '') or (
        panels[0].get('image_url', '') if panels else ''
    )
    title = clip(plain_text(product.name or ''), 120)
    summary = clip(plain_text(product.short_description or product.description or ''), _SUMMARY_MAX)

    story, _created = WebStory.objects.get_or_create(
        product=product,
        defaults={
            'title': title,
            'summary': summary,
            'panels': panels,
            'poster_portrait_url': poster,
        },
    )
    old_poster = story.poster_portrait_url
    story.title = title
    story.summary = summary
    story.panels = panels
    story.poster_portrait_url = poster
    story.save(update_fields=['title', 'summary', 'panels', 'poster_portrait_url', 'updated_at'])
    _drop_old_poster(old_poster, poster)
    return story, True


def is_current(story) -> bool:
    """Was ``story`` built by this builder?"""
    panels = story.panels or []
    return bool(panels) and isinstance(panels[0], dict) and panels[0].get('v') == BUILDER_VERSION


_PROXY_WIDTHS = (600, 800, 1200)


def render_pages(panels: list, *, base: str, image_proxy: bool, fallback_alt: str) -> list[dict]:
    """The pages as the template draws them, whatever builder made them.

    Text is cleaned again here, so a story stored before plain text existed
    renders clean before anything rebuilds it."""
    from urllib.parse import quote  # noqa: PLC0415

    pages = []
    for panel in panels or []:
        if not isinstance(panel, dict):
            continue
        kind = panel.get('kind') or ('cta' if panel.get('cta_url') else 'legacy')
        points = [clip(plain_text(p), _POINT_MAX) for p in panel.get('points') or []]
        page = {
            'kind': kind,
            'title': clip(plain_text(panel.get('title') or ''), _TITLE_MAX),
            'caption': clip(plain_text(panel.get('caption') or ''), _DETAIL_MAX),
            'points': [p for p in points if p],
            'image_url': panel.get('image_url') or '',
            'alt': clip(plain_text(panel.get('alt') or panel.get('caption') or ''), _ALT_MAX)
            or fallback_alt,
            'fit': panel.get('fit') if panel.get('fit') in ('contain', 'cover') else 'cover',
            'bg': panel.get('bg')
            if re.fullmatch(r'#[0-9a-f]{6}', panel.get('bg') or '')
            else '#1a1a1a',
            'tone': 'light' if panel.get('tone') == 'light' else 'dark',
            'srcset': '',
            'cta_href': '',
        }
        path = panel.get('image_path') or ''
        if image_proxy and path:
            safe = quote(path, safe='/')
            page['srcset'] = ', '.join(f'/img/webp/{w}/{safe} {w}w' for w in _PROXY_WIDTHS)
        cta = panel.get('cta_url') or ''
        if cta.startswith('/') and not cta.startswith('//'):
            page['cta_href'] = f'{base}{cta}'
        words = len(f'{page["title"]} {page["caption"]} {" ".join(page["points"])}'.split())
        page['seconds'] = max(5, min(12, 4 + words // 3))
        pages.append(page)
    return pages


def story_path(product_slug: str) -> str:
    return f'/story/{product_slug}/'
