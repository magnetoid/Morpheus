"""Give every cover-less book a cover.

88% of the catalogue (Project-Gutenberg classics) shipped with no image, so
storefront cards render as weak text boxes and OG/feed previews are blank. Two
sources, in order of preference per book:

1. ``--gutenberg`` + a ``book.gutenberg_id`` metafield → fetch the real cover
   from gutenberg.org (only ~8 books still carry the id, but it's a free win).
2. Otherwise → render a styled "classic imprint" cover with Pillow from the
   data we *do* have: title (Product.name), author + genre (BookProduct), and a
   deterministic background colour seeded from the slug.

The same bytes are stored as the primary ProductImage (webp variant auto-
generates in ``ProductImage.save``) **and** as ``product.og_image`` — so social
/ feed completeness lands in the same pass.

Idempotent: only touches active products that have no image yet. Dry-run by
default; pass ``--apply`` to write.

    python manage.py backfill_book_covers --apply --gutenberg --limit 20
"""

from __future__ import annotations

import logging
import os
import zlib
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.book_product')

_W, _H = 800, 1200

# Vera ships with reportlab (a hard dependency), so these paths exist in every
# environment — local and the prod container alike. No bundled font, no
# unusable ImageFont.load_default() bitmap fallback at this size.
try:
    import reportlab

    _FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), 'fonts')
except Exception:  # noqa: BLE001 — reportlab always present; degrade if not
    _FONT_DIR = ''

_FONT_BOLD = os.path.join(_FONT_DIR, 'VeraBd.ttf')
_FONT_REG = os.path.join(_FONT_DIR, 'Vera.ttf')

# Muted, bookish background palette — deep cloth-binding tones. Title + imprint
# render in warm parchment ink on top.
_PALETTE = [
    (44, 62, 80),  # slate
    (61, 52, 45),  # espresso
    (51, 60, 51),  # forest
    (74, 49, 54),  # oxblood
    (45, 52, 71),  # indigo
    (80, 64, 45),  # tobacco
    (40, 56, 62),  # teal-grey
    (66, 50, 66),  # plum
]
_INK = (236, 226, 208)  # parchment
_INK_SOFT = (236, 226, 208, 170)


def _font(path: str, size: int):
    from PIL import ImageFont  # noqa: PLC0415

    try:
        return ImageFont.truetype(path, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    """Greedy word-wrap to a pixel width."""
    words = (text or '').split()
    lines: list[str] = []
    cur = ''
    for w in words:
        trial = f'{cur} {w}'.strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_cover_bytes(*, title: str, author: str = '', genre: str = '', slug: str = '') -> bytes:
    """Render an 800×1200 styled classic-cover JPEG. Pure function — unit-tested."""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    # Deterministic, non-crypto: same slug → same colour across runs.
    seed = zlib.crc32((slug or title).encode('utf-8'))
    bg = _PALETTE[seed % len(_PALETTE)]
    img = Image.new('RGB', (_W, _H), bg)
    draw = ImageDraw.Draw(img)

    margin = 70
    # Double rule frame.
    draw.rectangle([margin, margin, _W - margin, _H - margin], outline=_INK, width=3)
    draw.rectangle(
        [margin + 12, margin + 12, _W - margin - 12, _H - margin - 12], outline=_INK, width=1
    )

    # Imprint, top.
    imp = _font(_FONT_REG, 30)
    label = 'DOT BOOKS'
    draw.text(
        ((_W - draw.textlength(label, font=imp)) / 2, margin + 50), label, font=imp, fill=_INK
    )

    # Title — bold serif-ish, wrapped, vertically centred in the upper-middle.
    size = 84 if len(title) < 28 else (66 if len(title) < 55 else 50)
    tf = _font(_FONT_BOLD, size)
    max_w = _W - 2 * (margin + 50)
    lines = _wrap(draw, title, tf, max_w)
    line_h = int(size * 1.18)
    block_h = line_h * len(lines)
    y = (_H - block_h) // 2 - 60
    for ln in lines:
        draw.text(((_W - draw.textlength(ln, font=tf)) / 2, y), ln, font=tf, fill=_INK)
        y += line_h

    # Author, below the title.
    if author:
        af = _font(_FONT_REG, 38)
        ay = y + 26
        draw.text(((_W - draw.textlength(author, font=af)) / 2, ay), author, font=af, fill=_INK)

    # Genre label, bottom inside the frame.
    if genre:
        gf = _font(_FONT_REG, 26)
        g = genre.upper()
        gy = _H - margin - 64
        gw = draw.textlength(g, font=gf)
        draw.line(
            [(_W / 2 - gw / 2 - 24, gy + 16), (_W / 2 - gw / 2 - 8, gy + 16)], fill=_INK, width=1
        )
        draw.line(
            [(_W / 2 + gw / 2 + 8, gy + 16), (_W / 2 + gw / 2 + 24, gy + 16)], fill=_INK, width=1
        )
        draw.text(((_W - gw) / 2, gy), g, font=gf, fill=_INK)

    out = BytesIO()
    img.save(out, format='JPEG', quality=88, optimize=True)
    return out.getvalue()


def _gutenberg_cover_bytes(gid: str) -> bytes | None:
    """Fetch the real Gutenberg cover for `gid`; None if unavailable/bad."""
    import urllib.request  # noqa: PLC0415

    url = f'https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.cover.medium.jpg'
    try:
        req = urllib.request.Request(  # noqa: S310 — fixed https host, literal scheme
            url, headers={'User-Agent': 'dotbooks-cover-backfill/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — fixed https host
            if resp.status != 200:
                return None
            data = resp.read(2_000_000)
        if len(data) < 2048 or data[:3] != b'\xff\xd8\xff':  # JPEG magic
            return None
        return data
    except Exception as e:  # noqa: BLE001
        logger.debug('gutenberg cover %s failed: %s', gid, e)
        return None


class Command(BaseCommand):
    help = 'Backfill primary cover + og_image for cover-less active books.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write (default: dry-run).')
        parser.add_argument('--gutenberg', action='store_true', help='Fetch real covers by id.')
        parser.add_argument('--limit', type=int, default=0, help='Cap products processed.')

    def handle(self, *args, **opts):
        from plugins.installed.catalog.models import Product, ProductImage  # noqa: PLC0415

        apply = opts['apply']
        use_gb = opts['gutenberg']
        limit = opts['limit']

        qs = Product.objects.filter(status='active', images__isnull=True).distinct()
        if limit:
            qs = qs[:limit]

        done = gen = fetched = 0
        for p in qs.iterator():
            title = (p.name or '').strip() or 'Untitled'
            author, genre, gid = self._book_meta(p)

            data = None
            if use_gb and gid:
                data = _gutenberg_cover_bytes(gid)
                if data:
                    fetched += 1
            if data is None:
                data = render_cover_bytes(title=title, author=author, genre=genre, slug=p.slug)
                gen += 1

            if apply:
                self._save(p, data, ProductImage, alt=f'{title} — book cover')
            done += 1
            if done % 25 == 0:
                self.stdout.write(f'  …{done} processed ({fetched} fetched, {gen} generated)')

        verb = 'wrote' if apply else 'would write'
        self.stdout.write(
            self.style.SUCCESS(
                f'{verb} covers for {done} books ({fetched} from Gutenberg, {gen} generated).'
                + ('' if apply else '  [dry-run — pass --apply to write]')
            )
        )

    def _book_meta(self, p) -> tuple[str, str, str]:
        """(author, genre_name, gutenberg_id) for a product, best-effort."""
        author = genre = gid = ''
        try:
            from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

            bp = BookProduct.objects.filter(product=p).first()
            if bp:
                author = (bp.author or '').strip()
                g = bp.genres.first()
                genre = g.name if g else ''
        except Exception as e:  # noqa: BLE001
            logger.debug('book meta (bp) failed for %s: %s', p.slug, e)
        try:
            from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

            gid = str(Metafield.objects.for_obj(p).get('book.gutenberg_id') or '').strip()
        except Exception as e:  # noqa: BLE001
            logger.debug('book meta (gid) failed for %s: %s', p.slug, e)
        return author, genre, gid

    def _save(self, p, data: bytes, ProductImage, *, alt: str) -> None:
        pi = ProductImage(product=p, is_primary=True, sort_order=0, alt_text=alt[:255])
        pi.image.save(f'cover-{p.slug}.jpg', ContentFile(data), save=True)  # triggers webp variant
        p.og_image.save(f'og-{p.slug}.jpg', ContentFile(data), save=True)
