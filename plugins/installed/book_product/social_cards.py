"""A book's social card: what goes on it, when it is drawn, where it is kept,
and when a product page shares it instead of the plain cover.

Off by default; each store switches it on in the book app's settings
(`social_cards`), so another store never shows the DotBooks look.

**What goes on it** comes from the book as stored: the product's name, the
book's author, the first lines of the product's short description (else the
book's synopsis, else the description), and the store's own settings for the
line above the title and the wordmark (empty wordmark: the store name). The
cover is the product's primary photo, read from storage by its name. Nothing is
written for the card.

**When it is drawn.** Every input goes into a fingerprint. A product page whose
book has no card for its current fingerprint asks the worker for one and shares
the cover meanwhile; the worker draws it, stores it, and records it only if the
book still has that fingerprint. A card is never drawn twice for the same
inputs, and a failed cover is recorded against its fingerprint so it is not
retried until something changes.

**Where it is kept.** Through the default storage, at
`book_social_cards/<product id>-<fingerprint>.jpg`. A new card replaces the old
one's file once its row commits; deleting the book deletes the card. A recorded
card whose file is gone (a restored database, a deleted file) is drawn again.

**When a page shares it.** Only when the feature is on, the page is the book's
product page, the stored card matches the book as it is now, and the image the
seo app chose is the product's own photo. A share image somebody picked for the
page, anything other than the product's photos (another product's photo, an
image on another site), is kept.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import uuid
from dataclasses import dataclass
from functools import partial
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from plugins.installed.book_product.social_card_render import (
    HEIGHT,
    MAX_COVER_BYTES,
    TEMPLATE_VERSION,
    WIDTH,
    CardContent,
    CardError,
    CardStyle,
    clean_text,
    open_cover,
    parse_hex,
    render_card,
)

logger = logging.getLogger('morpheus.book_product')

CARD_DIR = 'book_social_cards'
DEFAULT_BACKGROUND = '#0E1D21'
DEFAULT_ACCENT = '#C8A96A'
# A queued card holds this long: page views of the same book within it ask
# for nothing more. It outlasts the task's retries (tasks.py: 3 more tries, 120 s
# apart), and a run that ends in an error keeps it, so a store whose storage
# refuses writes tries each book at most once in this time.
LOCK_SECONDS = 30 * 60
# How long a page trusts that a card's file is there before it looks again.
FILE_CHECK_SECONDS = 24 * 60 * 60
# How much of the description the card reads; it shows at most three lines.
DESCRIPTION_CHARS = 600

_BLOCK_END = re.compile(r'<(?:br|/p|/div|/li|/h[1-6]|/blockquote)\b[^>]*>', re.I)


def _plugin():
    from plugins.registry import app_registry  # noqa: PLC0415

    return app_registry.get('book_product')


def _config(key: str, default=None):
    plugin = _plugin()
    return plugin.get_config_value(key, default) if plugin is not None else default


def enabled() -> bool:
    from plugins.registry import app_registry  # noqa: PLC0415

    return app_registry.is_active('book_product') and bool(_config('social_cards', False))


def card_style() -> CardStyle:
    defaults = CardStyle()
    return CardStyle(
        background=parse_hex(
            str(_config('social_card_background', DEFAULT_BACKGROUND)), defaults.background
        ),
        accent=parse_hex(str(_config('social_card_accent', DEFAULT_ACCENT)), defaults.accent),
    )


def plain_text(value: str) -> str:
    """Product text is rich HTML: paragraphs apart, tags and entities gone."""
    return clean_text(html.unescape(strip_tags(_BLOCK_END.sub(' ', value or ''))))


@dataclass(frozen=True)
class CardInputs:
    cover_name: str
    content: CardContent
    style: CardStyle

    def fingerprint(self) -> str:
        payload = {
            'v': TEMPLATE_VERSION,
            'cover': self.cover_name,
            'title': self.content.title,
            'author': self.content.author,
            'description': self.content.description,
            'eyebrow': self.content.eyebrow,
            'wordmark': self.content.wordmark,
            'background': self.style.background,
            'accent': self.style.accent,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()


def cover_image(product):
    """The product's primary photo with a file, else its first; None without one."""
    images = [img for img in product.images.all() if getattr(img.image, 'name', '')]
    primary = next((img for img in images if img.is_primary), None)
    return primary or (
        min(images, key=lambda img: (img.sort_order, str(img.pk))) if images else None
    )


def _author(book) -> str:
    author = clean_text(book.author)
    if author:
        return author
    for person in book.contributors or []:
        if isinstance(person, dict) and str(person.get('role', '')).lower() == 'author':
            name = clean_text(str(person.get('name', '')))
            if name:
                return name
    return ''


def card_inputs(book) -> CardInputs | None:
    """What this book's card shows, or None when it can have none (no cover, no name)."""
    from core.utils.site import store_name  # noqa: PLC0415

    product = book.product
    cover = cover_image(product)
    title = clean_text(product.name)
    if cover is None or not title:
        return None
    description = ''
    for source in (product.short_description, book.synopsis, product.description):
        description = plain_text(source)
        if description:
            break
    return CardInputs(
        cover_name=cover.image.name,
        content=CardContent(
            title=title,
            author=_author(book),
            description=description[:DESCRIPTION_CHARS],
            eyebrow=clean_text(str(_config('social_card_eyebrow', '') or '')),
            wordmark=clean_text(str(_config('social_card_wordmark', '') or '') or store_name()),
        ),
        style=card_style(),
    )


def card_name(product_id, key: str) -> str:
    return f'{CARD_DIR}/{product_id}-{key[:16]}.jpg'


# ── Drawing and keeping ──────────────────────────────────────────────────────


def draw(inputs: CardInputs) -> bytes:
    """The card's JPEG bytes. CardError when the cover cannot be used."""
    name = inputs.cover_name
    try:
        size = default_storage.size(name)
    except Exception:  # noqa: BLE001 — a storage without sizes still bounds the decode
        size = None
    if size is not None and size > MAX_COVER_BYTES:
        raise CardError(f'cover {name} is {size} bytes')
    try:
        fh = default_storage.open(name, 'rb')
    except FileNotFoundError as e:
        raise CardError(f'cover {name} is missing') from e
    with fh:
        cover = open_cover(fh, size_bytes=size)
    return render_card(cover, inputs.content, inputs.style)


def _store(product_id, key: str, data: bytes) -> str:
    name = card_name(product_id, key)
    if default_storage.exists(name):
        # The same inputs make the same card; a file of another size was cut
        # short (a worker killed while writing it).
        if default_storage.size(name) == len(data):
            return name
        default_storage.delete(name)
    saved = default_storage.save(name, ContentFile(data))
    if saved != name:  # a concurrent run stored this very card first
        default_storage.delete(saved)
    return name


def _delete_file(name: str) -> None:
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    if not name or BookProduct.objects.filter(social_card=name).exists():
        return
    try:
        default_storage.delete(name)
    except Exception as e:  # noqa: BLE001 — a leftover file is not worth a failure
        logger.warning('book_product: could not delete social card %s: %s', name, e)


def _record(book_id, key: str, name: str) -> bool:
    """Keep `name` as the book's card for `key`, if the book still has that key."""
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    with transaction.atomic():
        book = (
            BookProduct.objects.select_for_update(of=('self',))
            .select_related('product')
            .filter(pk=book_id)
            .first()
        )
        current = card_inputs(book) if book is not None else None
        if current is None or current.fingerprint() != key:
            return False
        previous = book.social_card.name or ''
        # update(), not save(): no post_save, and the book's updated_at stays the
        # merchant's.
        BookProduct.objects.filter(pk=book_id).update(social_card=name, social_card_key=key)
        if previous and previous != name:
            transaction.on_commit(partial(_delete_file, previous))
    return True


def render_and_store(book_id) -> str:
    """Draw and keep the book's card unless it already has one for its inputs.

    Returns 'current', 'stored', 'failed' (the cover cannot be used: recorded),
    'stale' (the book changed while drawing), 'no-card' (no cover or name) or
    'gone'. A storage error propagates, so the task can try again.
    """
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    book = BookProduct.objects.select_related('product').filter(pk=book_id).first()
    if book is None:
        return 'gone'
    inputs = card_inputs(book)
    if inputs is None:
        return 'no-card'
    key = inputs.fingerprint()
    if book.social_card_key == key and (
        not book.social_card.name or default_storage.exists(book.social_card.name)
    ):
        return 'current'
    try:
        data = draw(inputs)
    except CardError as e:
        logger.warning('book_product: no social card for %s: %s', book.product_id, e)
        return 'failed' if _record(book.pk, key, '') else 'stale'
    name = _store(book.product_id, key, data)
    if not _record(book.pk, key, name):
        _delete_file(name)
        return 'stale'
    return 'stored'


def _lock_key(book_id) -> str:
    return f'book_product:social_card:{book_id}'


def request_card(book_id) -> None:
    """Ask the worker for the book's card, at most once per LOCK_SECONDS."""
    token = uuid.uuid4().hex
    if not cache.add(_lock_key(book_id), token, LOCK_SECONDS):
        return
    try:
        from plugins.installed.book_product.tasks import render_social_card  # noqa: PLC0415

        render_social_card.delay(str(book_id), token)
    except Exception as e:  # noqa: BLE001 — no broker: the next page view asks again
        cache.delete(_lock_key(book_id))
        logger.warning('book_product: could not queue a social card: %s', e)


def release(book_id, token: str = '') -> None:
    """Free the book for the next request, unless another run holds it now
    (this run's lock ran out and a page view queued that one)."""
    key = _lock_key(book_id)
    if not token or cache.get(key) == token:
        cache.delete(key)


def _file_ok(name: str) -> bool:
    """Whether the card's file is in storage, looked up once a day per file
    (a name is one card's content, so a yes stays true until the file goes)."""
    seen = f'book_product:social_card:file:{name}'
    if cache.get(seen):
        return True
    if not default_storage.exists(name):
        return False
    cache.set(seen, 1, FILE_CHECK_SECONDS)
    return True


def delete_card_file(book) -> None:
    """post_delete: the book is gone, so is its card (after the delete commits)."""
    name = getattr(book.social_card, 'name', '') or ''
    if name:
        transaction.on_commit(partial(_delete_file, name))


# ── The product page ─────────────────────────────────────────────────────────


_PHOTO_FIELDS = ('image', 'webp_image')


def _is_product_photo(url: str, product, hosts=()) -> bool:
    """True when `url` is one of the product's photos (what seo shares by
    default), or empty. A share image picked for the page is anything else:
    another product's photo, the product form's own share images, an image on
    another site. `hosts` are the hosts the store answers on."""
    if not url:
        return True
    from morpheus.core import absolutize  # noqa: PLC0415

    parts = urlsplit(url)
    own_hosts = {h.lower() for h in hosts if h}
    own_hosts.add(urlsplit(absolutize('/')).netloc.lower())
    own_paths = set()
    model = product.images.model
    fields = [f for f in _PHOTO_FIELDS if any(x.name == f for x in model._meta.get_fields())]
    for img in product.images.all():
        for field in fields:
            name = getattr(getattr(img, field, None), 'name', '') or ''
            if name:
                own = urlsplit(absolutize(default_storage.url(name)))
                own_paths.add(own.path)
                own_hosts.add(own.netloc.lower())
    if parts.netloc and parts.netloc.lower() not in own_hosts:
        return False
    if parts.path in own_paths:
        return True
    # A former photo of the product: seo keeps the URL it copied when the
    # product was created, even after the photo is replaced. The product
    # form's own share images (products/og/, products/twitter/) were picked,
    # and so is a photo another product still has.
    media = urlsplit(settings.MEDIA_URL).path.rstrip('/') + '/'
    photos = f'{media}products/'
    if not parts.path.startswith(photos) or parts.path.startswith(
        (f'{photos}og/', f'{photos}twitter/')
    ):
        return False
    name = parts.path[len(media) :]
    others = model.objects.exclude(product_id=product.pk)
    return not any(others.filter(**{field: name}).exists() for field in fields)


def _page_book(request):
    """The active book whose product page `request` is, else None."""
    match = getattr(request, 'resolver_match', None)
    if match is None or getattr(match, 'view_name', '') != 'storefront:product_detail':
        return None
    slug = (match.kwargs or {}).get('slug')
    if not slug:
        return None
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    return (
        BookProduct.objects.filter(product__slug=slug, product__status='active')
        .select_related('product')
        .prefetch_related('product__images')
        .first()
    )


def _request_host(request) -> str:
    try:
        return request.get_host()
    except Exception:  # noqa: BLE001 — a host Django refuses is no reason to fail a page
        return ''


def apply_to_head(doc, request) -> None:
    """STOREFRONT_HEAD: share the book's card on its product page (see module doc)."""
    book = _page_book(request) if enabled() else None
    inputs = card_inputs(book) if book is not None else None
    if inputs is None:
        return
    if book.social_card_key != inputs.fingerprint():
        request_card(book.pk)
        return
    name = book.social_card.name
    if not name or not _is_product_photo(
        doc.meta_content('og:image'), book.product, hosts=(_request_host(request),)
    ):
        return
    if not _file_ok(name):
        request_card(book.pk)  # recorded, but the file is gone: draw it again
        return
    from morpheus.core import absolutize  # noqa: PLC0415

    url = absolutize(default_storage.url(book.social_card.name))
    content = inputs.content
    alt = (
        _('Cover of %(title)s by %(author)s') % {'title': content.title, 'author': content.author}
        if content.author
        else _('Cover of %(title)s') % {'title': content.title}
    )
    for prop, value in (
        ('og:image', url),
        ('og:image:secure_url', url),
        ('og:image:width', str(WIDTH)),
        ('og:image:height', str(HEIGHT)),
        ('og:image:alt', alt),
    ):
        doc.meta(value, property=prop, source='book_product')
    doc.meta(url, name='twitter:image', source='book_product')
    doc.meta(alt, name='twitter:image:alt', source='book_product')
