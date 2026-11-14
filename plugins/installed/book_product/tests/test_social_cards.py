"""A book's social card (v0.167.0): drawn from the book as stored, shared on its page.

The card is the 1200x630 image a shared product page shows: the whole cover on
the left, the title, author and the start of the book's own description on the
right, the store's wordmark under them (social_card_render.py). It is drawn by
the worker when a book has no card for its current inputs, kept in the default
storage, and shared as og:image / twitter:image only while the store has the
feature on and the page's share image is the product's own photo
(social_cards.py). Off, missing, stale or broken, the page shares what it
shared before.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import re
import struct
import tempfile
import zlib
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from djmoney.money import Money
from PIL import Image, ImageDraw

from plugins.installed.book_product import social_cards
from plugins.installed.book_product.models import BookProduct
from plugins.installed.book_product.social_card_render import (
    AUTHOR_LINES,
    COVER_BOX,
    DESCRIPTION_LINES,
    DIVIDER_X,
    FRAME_INSET,
    HEIGHT,
    MAX_COVER_BYTES,
    SHADOW_OFFSET,
    SHADOW_REACH,
    TEXT_LEFT,
    TEXT_RIGHT,
    TITLE_LINES,
    WIDTH,
    CardContent,
    CardError,
    CardStyle,
    _text_block,
    _width,
    cover_rect,
    open_cover,
    render_card,
)
from plugins.installed.catalog.models import Product, ProductImage
from plugins.registry import app_registry
from themes.registry import theme_registry

RED = (220, 20, 20)
GREEN = (20, 160, 60)
DESCRIPTION = (
    '<p>Tommy and Tuppence Beresford take over a detective agency.</p>'
    '<p>Each case is solved in the style of a famous fictional detective.</p>'
)
SIZES = [(600, 900), (900, 600), (500, 500), (300, 1200), (1200, 300)]


def cover_bytes(size=(600, 900), fmt='PNG', mode='RGB') -> bytes:
    """A green cover with a thick red border: a cut edge would lose the red."""
    img = Image.new(mode, size, GREEN if mode == 'RGB' else (*GREEN, 255))
    ImageDraw.Draw(img).rectangle([0, 0, size[0] - 1, size[1] - 1], outline=RED, width=24)
    out = BytesIO()
    img.save(out, fmt)
    return out.getvalue()


def png_header_only(width: int, height: int) -> bytes:
    """A PNG whose header claims `width` x `height` and holds no pixels."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
        )

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IEND', b'')


def content(**kw) -> CardContent:
    return CardContent(
        title=kw.get('title', 'Partners in Crime'),
        author=kw.get('author', 'Agatha Christie'),
        description=kw.get('description', 'Tommy and Tuppence take over a detective agency.'),
        eyebrow=kw.get('eyebrow', 'The DotBooks Collection'),
        wordmark=kw.get('wordmark', 'Dot Books.'),
    )


def card_lines(c: CardContent):
    return [part[1] for part in _text_block(c, CardStyle()) if part[0] == 'line']


def is_red(px) -> bool:
    return px[0] > 150 and px[1] < 100 and px[2] < 100


def is_green(px) -> bool:
    return px[1] > 110 and px[0] < 90


# ── Drawing ──────────────────────────────────────────────────────────────────


class RenderTests(SimpleTestCase):
    def render(self, size=(600, 900), c=None) -> Image.Image:
        cover = open_cover(BytesIO(cover_bytes(size)))
        return Image.open(BytesIO(render_card(cover, c or content())))

    def test_a_jpeg_of_1200_by_630(self):
        card = self.render()
        self.assertEqual(card.format, 'JPEG')
        self.assertEqual(card.size, (WIDTH, HEIGHT))
        self.assertEqual((WIDTH, HEIGHT), (1200, 630))
        self.assertEqual(card.mode, 'RGB')

    def test_the_whole_cover_shows_with_its_proportions(self):
        box_w, box_h = COVER_BOX[2] - COVER_BOX[0], COVER_BOX[3] - COVER_BOX[1]
        for size in SIZES:
            with self.subTest(size=size):
                x, y, w, h = cover_rect(size)
                self.assertGreaterEqual(x, COVER_BOX[0])
                self.assertGreaterEqual(y, COVER_BOX[1])
                self.assertLessEqual(x + w, COVER_BOX[2])
                self.assertLessEqual(y + h, COVER_BOX[3])
                # Scaled to fit, never stretched: one side fills the box, and the
                # ratio is the cover's to the pixel.
                self.assertTrue(w == box_w or h == box_h)
                self.assertLessEqual(abs(w * size[1] - h * size[0]), max(size))
                card = self.render(size).load()
                # Every edge of the cover is on the card (the red border), and
                # its middle too.
                for px in (
                    (x + 2, y + h // 2),
                    (x + w - 3, y + h // 2),
                    (x + w // 2, y + 2),
                    (x + w // 2, y + h - 3),
                ):
                    self.assertTrue(is_red(card[px]), (px, card[px]))
                self.assertTrue(is_green(card[x + w // 2, y + h // 2]))

    def test_the_shadow_stays_inside_the_frame(self):
        for size in SIZES:
            with self.subTest(size=size):
                x, y, w, h = cover_rect(size)
                self.assertGreaterEqual(x + SHADOW_OFFSET[0] - SHADOW_REACH, FRAME_INSET)
                self.assertGreaterEqual(y + SHADOW_OFFSET[1] - SHADOW_REACH, FRAME_INSET)
                self.assertLessEqual(x + w + SHADOW_OFFSET[0] + SHADOW_REACH, DIVIDER_X)
                self.assertLessEqual(y + h + SHADOW_OFFSET[1] + SHADOW_REACH, HEIGHT - FRAME_INSET)

    def test_the_text_stays_in_its_column(self):
        width = TEXT_RIGHT - TEXT_LEFT
        self.assertLessEqual(WIDTH - TEXT_RIGHT, 80)
        self.assertGreaterEqual(WIDTH - TEXT_RIGHT, 70)
        cases = [
            content(),
            content(
                title='The Mysterious Affair at Styles and Other Early Cases of Hercule Poirot'
            ),
            content(author='Agatha Christie, Mary Westmacott and a Very Long List of Co-Writers'),
            content(description='Word ' * 400),
            content(title='Supercalifragilisticexpialidocious' * 4),
        ]
        for c in cases:
            with self.subTest(title=c.title[:30]):
                for line in card_lines(c):
                    self.assertLessEqual(_width(line.text, line.font, line.tracking), width)

    def test_long_fields_are_cut_to_their_lines_cleanly(self):
        c = content(
            title='A Title That Goes On ' * 12,
            author='An Author With A Name ' * 8,
            description='This book has a description that never ends. ' * 30,
            eyebrow='',
        )
        lines = card_lines(c)
        by_fill: dict = {}
        for line in lines:
            by_fill.setdefault(line.fill, []).append(line.text)
        from plugins.installed.book_product.social_card_render import CREAM, MUTED

        title, desc = by_fill[CREAM], by_fill.get(MUTED, [])
        self.assertLessEqual(len(title), TITLE_LINES)
        self.assertTrue(title[-1].endswith('…'))
        self.assertLessEqual(len(desc), DESCRIPTION_LINES)
        author = by_fill[CardStyle().accent]  # no eyebrow: every accent line is the author
        self.assertLessEqual(len(author), AUTHOR_LINES)
        self.assertTrue(author[-1].endswith('…'))

    def test_unicode_titles_are_drawn(self):
        for title, author in (
            ('Ubistvo u Orijent ekspresu: Šćepan, Đurđa i Žarko', 'Agata Kristi'),
            ('Убиство у Оријент експресу', 'Агата Кристи'),
            ('Le Crime de l’Orient-Express — ça, déjà', 'Agatha Christie'),
        ):
            with self.subTest(title=title):
                lines = card_lines(content(title=title, author=author))
                drawn = ' '.join(ln.text for ln in lines)
                self.assertIn(title.split()[0], drawn)
                self.assertIn(author.upper().split()[0], drawn)
                cover = open_cover(BytesIO(cover_bytes()))
                card = Image.open(BytesIO(render_card(cover, content(title=title))))
                self.assertEqual(card.size, (WIDTH, HEIGHT))

    def test_a_title_no_bundled_font_can_draw_makes_no_card(self):
        cover = open_cover(BytesIO(cover_bytes()))
        with self.assertRaises(CardError):
            render_card(cover, content(title='東京物語'))

    def test_a_book_with_no_author_or_description_still_gets_a_card(self):
        c = content(author='', description='', eyebrow='')
        texts = [ln.text for ln in card_lines(c)]
        self.assertEqual(' '.join(texts), 'Partners in Crime')
        self.assertEqual(self.render(c=c).size, (WIDTH, HEIGHT))

    def test_a_bad_colour_falls_back_to_the_default(self):
        from plugins.installed.book_product.social_card_render import parse_hex

        self.assertEqual(parse_hex('#0E1D21', (0, 0, 0)), (14, 29, 33))
        self.assertEqual(parse_hex('red', (1, 2, 3)), (1, 2, 3))
        self.assertEqual(parse_hex('', (1, 2, 3)), (1, 2, 3))


class CoverInputTests(SimpleTestCase):
    def test_garbage_is_refused(self):
        with self.assertRaises(CardError):
            open_cover(BytesIO(b'this is not an image'))

    def test_a_truncated_file_is_refused(self):
        with self.assertRaises(CardError):
            open_cover(BytesIO(cover_bytes()[:300]))

    def test_a_header_claiming_too_many_pixels_is_refused_before_decoding(self):
        # Over this app's limit: refused by its own check.
        with self.assertRaises(CardError) as caught:
            open_cover(BytesIO(png_header_only(8_000, 8_000)))
        self.assertIn('8000x8000', str(caught.exception))
        # Far over it: Pillow's own bomb guard refuses it first, as a CardError.
        with self.assertRaises(CardError):
            open_cover(BytesIO(png_header_only(30_000, 30_000)))

    def test_an_oversized_file_is_refused_unread(self):
        fp = mock.Mock()
        with self.assertRaises(CardError):
            open_cover(fp, size_bytes=MAX_COVER_BYTES + 1)
        fp.read.assert_not_called()

    def test_other_formats_are_refused(self):
        with self.assertRaises(CardError):
            open_cover(BytesIO(cover_bytes(fmt='BMP')))

    def test_a_tiny_image_is_refused(self):
        with self.assertRaises(CardError):
            open_cover(BytesIO(cover_bytes(size=(20, 30))))

    def test_a_transparent_cover_is_put_on_white(self):
        img = open_cover(BytesIO(cover_bytes(mode='RGBA')))
        self.assertEqual(img.mode, 'RGB')

    def test_a_jpeg_holding_two_pictures_draws_the_first(self):
        first = Image.new('RGB', (600, 900), GREEN)
        buf = BytesIO()
        first.save(buf, 'MPO', save_all=True, append_images=[Image.new('RGB', (600, 900), RED)])
        buf.seek(0)
        self.assertEqual(Image.open(BytesIO(buf.getvalue())).format, 'MPO')
        img = open_cover(buf)
        self.assertEqual(img.mode, 'RGB')
        self.assertTrue(is_green(img.getpixel((img.width // 2, img.height // 2))))


# ── Fixtures ─────────────────────────────────────────────────────────────────

_serial = iter(range(1, 10_000))


def make_book(slug='partners-in-crime', *, cover=True, **fields) -> BookProduct:
    n = next(_serial)
    product = Product.objects.create(
        name=fields.pop('name', 'Partners in Crime'),
        slug=slug,
        sku=f'SC-{n}',
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
        short_description=fields.pop('short_description', DESCRIPTION),
    )
    if cover:
        name = default_storage.save(f'products/{slug}-cover.png', ContentFile(cover_bytes()))
        ProductImage.objects.create(product=product, image=name, is_primary=True)
    fields.setdefault('author', 'Agatha Christie')
    return BookProduct.objects.create(product=product, **fields)


def card_files() -> list[str]:
    try:
        return default_storage.listdir(social_cards.CARD_DIR)[1]
    except FileNotFoundError:
        return []


class _Clean(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        plugin = app_registry.get('book_product')
        plugin.invalidate_config_cache()
        self.addCleanup(plugin.invalidate_config_cache)
        self.plugin = plugin
        for name in card_files():
            default_storage.delete(f'{social_cards.CARD_DIR}/{name}')

    def switch_on(self, **more):
        self.plugin.set_config('social_cards', True)
        for key, value in more.items():
            self.plugin.set_config(key, value)
        self.plugin.invalidate_config_cache()


# ── Inputs, storage, regeneration ────────────────────────────────────────────


class CardInputsTests(_Clean):
    def test_inputs_come_from_the_book_as_stored(self):
        self.switch_on(social_card_eyebrow='The DotBooks Collection')
        book = make_book()
        inputs = social_cards.card_inputs(book)
        self.assertEqual(inputs.content.title, 'Partners in Crime')
        self.assertEqual(inputs.content.author, 'Agatha Christie')
        self.assertTrue(inputs.content.description.startswith('Tommy and Tuppence Beresford'))
        self.assertNotIn('<', inputs.content.description)
        self.assertIn('agency. Each case', inputs.content.description, 'paragraphs stay apart')
        self.assertEqual(inputs.content.eyebrow, 'The DotBooks Collection')
        self.assertTrue(inputs.content.wordmark, 'an empty wordmark is the store name')
        self.assertEqual(inputs.cover_name, book.product.images.get().image.name)

    def test_the_synopsis_stands_in_for_an_empty_short_description(self):
        book = make_book(short_description='', synopsis='A synopsis.')
        self.assertEqual(social_cards.card_inputs(book).content.description, 'A synopsis.')

    def test_an_author_may_come_from_the_contributors(self):
        book = make_book(author='', contributors=[{'name': 'A. Christie', 'role': 'Author'}])
        self.assertEqual(social_cards.card_inputs(book).content.author, 'A. Christie')

    def test_no_cover_no_card(self):
        book = make_book(cover=False)
        self.assertIsNone(social_cards.card_inputs(book))
        self.assertEqual(social_cards.render_and_store(book.pk), 'no-card')
        self.assertEqual(card_files(), [])

    def test_the_fingerprint_follows_every_input(self):
        book = make_book()
        key = social_cards.card_inputs(book).fingerprint()
        self.assertEqual(social_cards.card_inputs(book).fingerprint(), key)
        self.switch_on(social_card_accent='#FFFFFF')
        self.assertNotEqual(social_cards.card_inputs(book).fingerprint(), key)


class StoreTests(_Clean):
    def test_a_card_is_drawn_and_kept_in_storage(self):
        book = make_book()
        before = BookProduct.objects.values_list('updated_at', flat=True).get(pk=book.pk)
        self.assertEqual(social_cards.render_and_store(book.pk), 'stored')
        book.refresh_from_db()
        name = book.social_card.name
        self.assertRegex(name, rf'^book_social_cards/{book.product_id}-[0-9a-f]{{16}}\.jpg$')
        self.assertEqual(book.social_card_key, social_cards.card_inputs(book).fingerprint())
        with default_storage.open(name, 'rb') as fh:
            img = Image.open(BytesIO(fh.read()))
        self.assertEqual((img.format, img.size), ('JPEG', (WIDTH, HEIGHT)))
        after = BookProduct.objects.values_list('updated_at', flat=True).get(pk=book.pk)
        self.assertEqual(before, after, "the merchant's updated_at is untouched")

    def test_the_same_inputs_are_never_drawn_twice(self):
        book = make_book()
        social_cards.render_and_store(book.pk)
        with mock.patch.object(social_cards, 'draw') as draw:
            self.assertEqual(social_cards.render_and_store(book.pk), 'current')
        draw.assert_not_called()
        self.assertEqual(len(card_files()), 1)

    def test_a_change_draws_a_new_card_and_deletes_the_old_one(self):
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        old = book.social_card.name
        Product.objects.filter(pk=book.product_id).update(name='Partners in Crime (1929)')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(social_cards.render_and_store(book.pk), 'stored')
        book.refresh_from_db()
        self.assertNotEqual(book.social_card.name, old)
        self.assertFalse(default_storage.exists(old))
        self.assertEqual(card_files(), [book.social_card.name.rsplit('/', 1)[1]])

    def test_a_cover_that_cannot_be_read_is_recorded_and_not_retried(self):
        book = make_book()
        name = book.product.images.get().image.name
        default_storage.delete(name)
        default_storage.save(name, ContentFile(b'not an image at all'))
        self.assertEqual(social_cards.render_and_store(book.pk), 'failed')
        book.refresh_from_db()
        self.assertEqual(book.social_card.name or '', '')
        self.assertEqual(book.social_card_key, social_cards.card_inputs(book).fingerprint())
        with mock.patch.object(social_cards, 'render_card') as render:
            self.assertEqual(social_cards.render_and_store(book.pk), 'current')
        render.assert_not_called()

    def test_a_missing_cover_file_is_a_failed_card(self):
        book = make_book()
        default_storage.delete(book.product.images.get().image.name)
        self.assertEqual(social_cards.render_and_store(book.pk), 'failed')

    def test_a_storage_failure_records_nothing_and_raises_for_a_retry(self):
        book = make_book()
        with (
            mock.patch.object(default_storage, 'save', side_effect=OSError('disk full')),
            self.assertRaises(OSError),
        ):
            social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        self.assertEqual((book.social_card.name or '', book.social_card_key), ('', ''))

    def test_the_task_retries_then_gives_up_and_keeps_the_lock(self):
        from plugins.installed.book_product.tasks import render_social_card

        book = make_book()
        cache.add(social_cards._lock_key(book.pk), 'mine', 60)
        with mock.patch.object(
            social_cards, 'render_and_store', side_effect=OSError('disk full')
        ) as run:
            render_social_card.apply(args=[str(book.pk), 'mine'])
        self.assertEqual(run.call_count, render_social_card.max_retries + 1)
        # Left to run out, so a store whose storage refuses writes is not asked
        # again on the next page view.
        self.assertEqual(cache.get(social_cards._lock_key(book.pk)), 'mine')

    def test_the_lock_outlasts_the_retries(self):
        from plugins.installed.book_product.tasks import render_social_card

        retries = render_social_card.max_retries * render_social_card.default_retry_delay
        self.assertGreater(social_cards.LOCK_SECONDS, 2 * retries)

    def test_a_run_frees_only_its_own_lock(self):
        from plugins.installed.book_product.tasks import render_social_card

        book = make_book()
        key = social_cards._lock_key(book.pk)
        cache.set(key, 'a later request', 60)
        render_social_card.apply(args=[str(book.pk), 'mine'])
        self.assertEqual(cache.get(key), 'a later request')
        render_social_card.apply(args=[str(book.pk), 'a later request'])
        self.assertIsNone(cache.get(key))

    def test_a_recorded_card_whose_file_is_gone_is_drawn_again(self):
        # A database restored from a backup taken before the card changed, or a
        # file deleted by hand: the row names a file that is not there.
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        name = book.social_card.name
        default_storage.delete(name)
        self.assertEqual(social_cards.render_and_store(book.pk), 'stored')
        self.assertTrue(default_storage.exists(name))
        self.assertEqual(social_cards.render_and_store(book.pk), 'current')

    def test_a_card_file_cut_short_is_written_again(self):
        book = make_book()
        inputs = social_cards.card_inputs(book)
        key, data = inputs.fingerprint(), social_cards.draw(inputs)
        name = default_storage.save(
            social_cards.card_name(book.product_id, key), ContentFile(data[:100])
        )
        self.assertEqual(social_cards._store(book.product_id, key, data), name)
        self.assertEqual(default_storage.size(name), len(data))
        self.assertEqual(card_files(), [name.rsplit('/', 1)[1]])

    def test_a_book_changed_while_drawing_keeps_no_card(self):
        book = make_book()
        real_draw = social_cards.draw

        def draw_while_edited(inputs):
            Product.objects.filter(pk=book.product_id).update(name='Renamed meanwhile')
            return real_draw(inputs)

        with mock.patch.object(social_cards, 'draw', side_effect=draw_while_edited):
            self.assertEqual(social_cards.render_and_store(book.pk), 'stale')
        book.refresh_from_db()
        self.assertEqual((book.social_card.name or '', book.social_card_key), ('', ''))
        self.assertEqual(card_files(), [], 'the stale card left no file behind')

    def test_two_runs_storing_one_card_keep_one_file(self):
        book = make_book()
        inputs = social_cards.card_inputs(book)
        key, data = inputs.fingerprint(), social_cards.draw(inputs)
        first = social_cards._store(book.product_id, key, data)
        # The second run checked before the first had saved: storage renames it.
        with mock.patch.object(default_storage, 'exists', return_value=False):
            second = social_cards._store(book.product_id, key, data)
        self.assertEqual(first, second)
        self.assertEqual(card_files(), [first.rsplit('/', 1)[1]])

    def test_deleting_the_book_deletes_its_card(self):
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        name = book.social_card.name
        with self.captureOnCommitCallbacks(execute=True):
            book.product.delete()
        self.assertFalse(default_storage.exists(name))

    def test_the_delete_is_wired_whether_the_app_is_on_or_not(self):
        # The app manifest's ready() runs only for an app switched on at
        # start-up; Django's AppConfig.ready() always runs.
        from django.apps import apps
        from django.db.models.signals import post_delete

        uid = 'book_product.social_card'
        self.assertTrue(post_delete.disconnect(sender=BookProduct, dispatch_uid=uid))
        apps.get_app_config('book_product').ready()
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        name = book.social_card.name
        with self.captureOnCommitCallbacks(execute=True):
            book.product.delete()
        self.assertFalse(default_storage.exists(name))

    def test_a_card_is_asked_for_once_per_lock(self):
        book = make_book()
        with mock.patch('plugins.installed.book_product.tasks.render_social_card.delay') as delay:
            social_cards.request_card(book.pk)
            social_cards.request_card(book.pk)
        delay.assert_called_once()
        book_id, token = delay.call_args.args
        self.assertEqual(book_id, str(book.pk))
        self.assertEqual(cache.get(social_cards._lock_key(book.pk)), token)

    def test_a_queue_that_refuses_frees_the_lock(self):
        book = make_book()
        with mock.patch(
            'plugins.installed.book_product.tasks.render_social_card.delay',
            side_effect=ConnectionError('no broker'),
        ) as delay:
            social_cards.request_card(book.pk)
            social_cards.request_card(book.pk)
        self.assertEqual(delay.call_count, 2)


# ── The product page ─────────────────────────────────────────────────────────

_META = re.compile(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"')


class _Page(_Clean):
    def setUp(self):
        super().setUp()
        override = override_settings(MORPHEUS_ACTIVE_THEME='dot_books')
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active('dot_books')
        self.addCleanup(setattr, theme_registry, '_active_name', previous)

    def head(self, slug='partners-in-crime') -> dict[str, list[str]]:
        resp = self.client.get(f'/products/{slug}/')
        self.assertEqual(resp.status_code, 200)
        found: dict[str, list[str]] = {}
        for prop, value in _META.findall(resp.content.decode()):
            found.setdefault(prop, []).append(value)
        return found

    def set_share_image(self, product, url: str) -> None:
        from plugins.installed.seo.models import SeoMeta

        ct = ContentType.objects.get_for_model(Product)
        SeoMeta.objects.update_or_create(
            content_type=ct, object_id=str(product.pk), defaults={'og_image': url}
        )


class ProductPageTests(_Page):
    def test_the_page_shares_the_card(self):
        self.switch_on()
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        head = self.head()
        self.assertEqual(len(head['og:image']), 1)
        url = head['og:image'][0]
        self.assertTrue(url.startswith(('http://', 'https://')), url)
        self.assertTrue(url.endswith(book.social_card.name), url)
        self.assertEqual(head['og:image:secure_url'], [url])
        self.assertEqual(head['og:image:width'], ['1200'])
        self.assertEqual(head['og:image:height'], ['630'])
        self.assertEqual(head['og:image:alt'], ['Cover of Partners in Crime by Agatha Christie'])
        self.assertEqual(head['twitter:image'], [url])
        self.assertEqual(head['twitter:image:alt'], head['og:image:alt'])
        self.assertEqual(head['twitter:card'], ['summary_large_image'])

    def test_the_first_view_shares_the_cover_and_asks_for_the_card(self):
        self.switch_on()
        book = make_book()
        head = self.head()
        self.assertIn('/products/partners-in-crime-cover', head['og:image'][0])
        book.refresh_from_db()  # the test worker runs the task at once
        self.assertTrue(book.social_card.name)
        self.assertTrue(self.head()['og:image'][0].endswith(book.social_card.name))

    def test_off_by_default_the_page_is_untouched(self):
        self.assertFalse(app_registry.get('book_product').get_config_value('social_cards'))
        book = make_book()
        head = self.head()
        self.assertIn('/products/partners-in-crime-cover', head['og:image'][0])
        self.assertNotIn('twitter:image:alt', head)
        book.refresh_from_db()
        self.assertEqual(book.social_card_key, '', 'nothing is drawn while it is off')
        self.assertEqual(card_files(), [])

    def test_switching_it_off_shares_the_cover_at_once(self):
        self.switch_on()
        book = make_book()
        social_cards.render_and_store(book.pk)
        self.plugin.set_config('social_cards', False)
        self.plugin.invalidate_config_cache()
        self.assertIn('/products/partners-in-crime-cover', self.head()['og:image'][0])

    def test_a_share_image_picked_for_the_page_is_kept(self):
        self.switch_on()
        book = make_book()
        social_cards.render_and_store(book.pk)
        boxed_set = make_book('the-complete-tommy-and-tuppence', name='The Complete Series')
        other_photo = boxed_set.product.images.get().image.url
        for url in (
            'https://cdn.example.com/campaign.jpg',
            '/media/products/og/og-partners-in-crime.jpg',
            '/media/campaigns/autumn.jpg',
            other_photo,
            'https://another-store.example/media/products/partners-in-crime-cover.png',
        ):
            with self.subTest(url=url):
                self.set_share_image(book.product, url)
                head = self.head()
                self.assertTrue(head['og:image'][0].endswith(url), head['og:image'])
                self.assertNotIn('twitter:image:alt', head)

    def test_the_cover_seo_copied_is_replaced(self):
        self.switch_on()
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        cover = book.product.images.get().image.url
        from morpheus.core import absolutize

        for url in (
            cover,
            absolutize(cover),
            f'http://testserver{cover}',
            '/media/products/an-old-photo.png',
        ):
            with self.subTest(url=url):
                self.set_share_image(book.product, url)
                self.assertTrue(self.head()['og:image'][0].endswith(book.social_card.name))

    def test_a_card_whose_file_is_gone_shares_the_cover_and_is_drawn_again(self):
        self.switch_on()
        book = make_book()
        social_cards.render_and_store(book.pk)
        book.refresh_from_db()
        default_storage.delete(book.social_card.name)
        with mock.patch('plugins.installed.book_product.tasks.render_social_card.delay') as delay:
            self.assertIn('/products/partners-in-crime-cover', self.head()['og:image'][0])
        delay.assert_called_once()

    def test_a_stale_card_is_not_shared(self):
        self.switch_on()
        book = make_book()
        social_cards.render_and_store(book.pk)
        Product.objects.filter(pk=book.product_id).update(name='Partners in Crime (1929)')
        self.assertIn('/products/partners-in-crime-cover', self.head()['og:image'][0])

    def test_a_product_that_is_not_a_book_is_untouched(self):
        self.switch_on()
        product = Product.objects.create(
            name='Tote bag',
            slug='tote-bag',
            sku='TOTE-1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        name = default_storage.save('products/tote-bag.png', ContentFile(cover_bytes()))
        ProductImage.objects.create(product=product, image=name, is_primary=True)
        head = self.head('tote-bag')
        self.assertIn('/products/tote-bag', head['og:image'][0])
        self.assertNotIn('twitter:image:alt', head)
        self.assertEqual(card_files(), [])

    def test_a_card_that_fails_never_breaks_the_page(self):
        self.switch_on()
        make_book()
        with mock.patch.object(social_cards, 'card_inputs', side_effect=RuntimeError('boom')):
            head = self.head()
        self.assertIn('/products/partners-in-crime-cover', head['og:image'][0])

    def test_a_cover_that_cannot_be_drawn_keeps_the_cover(self):
        self.switch_on()
        book = make_book()
        name = book.product.images.get().image.name
        default_storage.delete(name)
        default_storage.save(name, ContentFile(b'broken'))
        self.head()
        self.assertTrue(self.head()['og:image'][0].endswith(name))


# ── Settings, Linda, the command ─────────────────────────────────────────────


class SettingsTests(_Clean):
    def test_the_options_sit_in_the_book_apps_panel(self):
        panel = self.plugin.contribute_settings_panel()
        self.assertEqual((panel.label, panel.category), ('Books', 'storefront'))
        props = set((panel.schema or {}).get('properties', {}))
        self.assertTrue(
            {
                'social_cards',
                'social_card_eyebrow',
                'social_card_wordmark',
                'social_card_background',
                'social_card_accent',
            }
            <= props
        )

    def test_the_panel_renders_and_saves(self):
        staff = get_user_model().objects.create_superuser(
            username='cards', email='cards@x.test', password='pw'
        )
        self.client.force_login(staff)
        url = '/dashboard/settings/book_product/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Social cards for books')
        self.assertContains(resp, 'name="social_card_eyebrow"')
        resp = self.client.post(
            url,
            {'social_cards': 'on', 'social_card_eyebrow': 'The DotBooks Collection'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.plugin.invalidate_config_cache()
        self.assertTrue(social_cards.enabled())
        self.assertEqual(
            self.plugin.get_config_value('social_card_eyebrow'), 'The DotBooks Collection'
        )

    def test_a_saved_book_asks_for_its_card_once_committed(self):
        self.switch_on()
        book = make_book()
        with (
            mock.patch('plugins.installed.book_product.dashboard.save_book_fields'),
            mock.patch.object(social_cards, 'request_card') as ask,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.plugin.on_product_form_saved(product=book.product, post={}, files=None)
        ask.assert_called_once_with(book.pk)

    def test_a_saved_book_asks_for_nothing_while_off(self):
        book = make_book()
        with (
            mock.patch('plugins.installed.book_product.dashboard.save_book_fields'),
            mock.patch.object(social_cards, 'request_card') as ask,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.plugin.on_product_form_saved(product=book.product, post={}, files=None)
        ask.assert_not_called()


class LindaToolTests(_Clean):
    def tool(self):
        from core.agents import agent_registry

        return agent_registry.get_tool('books.render_social_card')

    def test_the_tool_is_registered_as_a_gated_write(self):
        from core.assistant.gates import LINDA_SCOPES

        tool = self.tool()
        self.assertIsNotNone(tool)
        self.assertTrue(tool.requires_approval)
        self.assertEqual(list(tool.scopes), ['catalog.write'])
        self.assertIn('catalog.write', LINDA_SCOPES)

    def test_it_draws_only_after_a_yes(self):
        from core.agents import ToolError
        from plugins.installed.book_product.agent_tools import render_social_card_tool as fn

        book = make_book()
        handler = getattr(fn, 'handler', fn)
        with self.assertRaises(ToolError):
            handler(slug='partners-in-crime')
        self.assertEqual(card_files(), [])
        result = handler(slug='partners-in-crime', confirmed=True)
        self.assertEqual(result.output['outcome'], 'stored')
        self.assertFalse(result.output['shown_on_page'])
        book.refresh_from_db()
        self.assertTrue(result.output['url'].endswith(book.social_card.name))
        with self.assertRaises(ToolError):
            handler(slug='no-such-book', confirmed=True)


class CommandTests(_Clean):
    def run_command(self, *args) -> str:
        out = StringIO()
        call_command('book_social_cards', *args, stdout=out)
        return out.getvalue()

    def test_the_canary_draws_one_book_and_is_idempotent(self):
        book = make_book()
        make_book('another-book', name='Another Book')
        out = self.run_command('--product', 'partners-in-crime')
        self.assertIn('partners-in-crime: stored', out)
        self.assertIn('off for this store', out)
        self.assertIn(
            'partners-in-crime: current', self.run_command('--product', str(book.product_id))
        )
        self.assertEqual(len(card_files()), 1, 'only the canary was drawn')

    def test_a_preview_writes_a_local_file_and_stores_nothing(self):
        book = make_book()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'card.jpg'
            self.run_command('--product', 'partners-in-crime', '--preview', str(path))
            img = Image.open(path)
            self.assertEqual((img.format, img.size), ('JPEG', (WIDTH, HEIGHT)))
        book.refresh_from_db()
        self.assertEqual(book.social_card_key, '')
        self.assertEqual(card_files(), [])

    def test_the_backfill_is_bounded_and_carries_on(self):
        for i in range(3):
            make_book(f'book-{i}', name=f'Book {i}')
        make_book('no-cover', cover=False)
        self.assertIn('would draw', self.run_command('--all', '--dry-run'))
        self.assertEqual(card_files(), [])
        out = self.run_command('--all', '--limit', '2')
        self.assertEqual(out.count(': stored'), 2)
        self.assertIn('Stopped at --limit 2', out)
        out = self.run_command('--all', '--limit', '2')
        self.assertEqual(out.count(': stored'), 1)
        self.assertNotIn('Stopped', out)
        self.assertEqual(self.run_command('--all').count(': stored'), 0)
        self.assertEqual(len(card_files()), 3)

    def test_it_needs_a_book_or_all(self):
        with self.assertRaises(CommandError):
            self.run_command()
        with self.assertRaises(CommandError):
            self.run_command('--product', 'nope')
