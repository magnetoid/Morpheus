"""Linda's book tools.

`books.render_social_card` draws a book's social card now (social_cards.py),
the same run a product page would queue. It stores a file and records it on
the book, so it is a write and waits for the merchant's yes. Switching the
feature on or changing its look is `settings.set` on the `book_product` app.
"""

from __future__ import annotations

from core.assistant.tools.ecommerce_writes import _require_confirmed
from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='books.render_social_card',
    description=(
        "Draw a book's social card (the 1200x630 image a shared product page shows: "
        'cover, title, author, start of the description) now, by product slug. Nothing is '
        "drawn when the book's card is already current. Shows on the page only while the "
        "book app's `social_cards` setting is on. confirmed=True after the user approves."
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['slug'],
    },
    requires_approval=True,
)
def render_social_card_tool(*, slug: str, confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    from django.core.files.storage import default_storage

    from morpheus.core import absolutize
    from plugins.installed.book_product import social_cards
    from plugins.installed.book_product.models import BookProduct

    book = BookProduct.objects.select_related('product').filter(product__slug=slug).first()
    if book is None:
        raise ToolError(f'No book with the product slug {slug!r}')
    outcome = social_cards.render_and_store(book.pk)
    book.refresh_from_db(fields=['social_card', 'social_card_key'])
    url = absolutize(default_storage.url(book.social_card.name)) if book.social_card else ''
    shown = social_cards.enabled()
    return ToolResult(
        output={'product': slug, 'outcome': outcome, 'url': url, 'shown_on_page': shown},
        display=f'Social card for {slug}: {outcome}' + ('' if shown else ' (feature off)'),
    )
