"""GraphQL mutations for Book Product — full create/update over the API."""

from __future__ import annotations

import strawberry

from plugins.installed.book_product.graphql._auth import check_scope
from plugins.installed.book_product.graphql.inputs import BookProductInput

_TEXT = (
    'author',
    'subtitle',
    'publisher',
    'imprint',
    'edition',
    'language',
    'series',
    'series_position',
    'synopsis',
    'binding',
)
_INT = ('page_count', 'width_mm', 'height_mm', 'spine_mm', 'weight_g')


@strawberry.type
class BookProductResult:
    ok: bool
    product_slug: str = ''
    error: str = ''


@strawberry.type
class BookProductMutationExtension:
    @strawberry.mutation(
        description='Create or update book attributes for a product (by slug). '
        'Staff-only / `catalog.write` scope.',
    )
    def set_book_product(  # noqa: PLR0911, PLR0912
        self, info: strawberry.Info, input: BookProductInput
    ) -> BookProductResult:
        err = check_scope(info, ['catalog.write'])
        if err:
            return BookProductResult(ok=False, error=err)

        from plugins.installed.book_product.models import (  # noqa: PLC0415
            BookProduct,
            PaperType,
            PrintType,
        )
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        product = Product.objects.filter(slug=input.product_slug).first()
        if product is None:
            return BookProductResult(
                ok=False, error=f'No product with slug {input.product_slug!r}.'
            )

        if input.print_type is not None and input.print_type not in PrintType.values:
            return BookProductResult(
                ok=False, error=f'invalid print_type (allowed: {sorted(PrintType.values)})'
            )
        if input.paper_type not in (None, '') and input.paper_type not in PaperType.values:
            return BookProductResult(
                ok=False, error=f'invalid paper_type (allowed: {sorted(PaperType.values)})'
            )

        book, _ = BookProduct.objects.get_or_create(product=product)
        for field in _TEXT:
            val = getattr(input, field, None)
            if val is not None:
                setattr(book, field, val.strip())
        for field in (*_INT,):
            val = getattr(input, field, None)
            if val is not None:
                setattr(book, field, val)
        if input.print_type is not None:
            book.print_type = input.print_type
        if input.paper_type is not None:
            book.paper_type = input.paper_type
        if input.publication_date is not None:
            raw = input.publication_date.strip()
            if not raw:
                book.publication_date = None
            else:
                from datetime import datetime  # noqa: PLC0415

                try:
                    book.publication_date = datetime.strptime(raw, '%Y-%m-%d').date()
                except ValueError:
                    return BookProductResult(ok=False, error='publication_date must be YYYY-MM-DD.')

        try:
            book.save()
        except Exception as e:  # noqa: BLE001
            return BookProductResult(ok=False, error=f'Could not save: {e}')
        return BookProductResult(ok=True, product_slug=product.slug)
