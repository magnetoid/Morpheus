"""GraphQL types for Book Product."""

from __future__ import annotations

import strawberry


@strawberry.type
class BookProductType:
    """Book attributes for a product. Plain type built from the BookProduct
    model via `from_model` so we control serialisation (choices → values,
    FileField → URL)."""

    product_slug: str
    author: str
    subtitle: str
    publisher: str
    imprint: str
    publication_date: str | None
    edition: str
    language: str
    series: str
    series_position: str
    synopsis: str
    print_type: str
    paper_type: str
    binding: str
    page_count: int | None
    width_mm: int | None
    height_mm: int | None
    spine_mm: int | None
    weight_g: int | None
    cover_pdf_url: str | None

    @classmethod
    def from_model(cls, book) -> BookProductType:
        cover = getattr(book.cover_pdf, 'url', None) if book.cover_pdf else None
        return cls(
            product_slug=book.product.slug,
            author=book.author,
            subtitle=book.subtitle,
            publisher=book.publisher,
            imprint=book.imprint,
            publication_date=book.publication_date.isoformat() if book.publication_date else None,
            edition=book.edition,
            language=book.language,
            series=book.series,
            series_position=book.series_position,
            synopsis=book.synopsis,
            print_type=book.print_type,
            paper_type=book.paper_type,
            binding=book.binding,
            page_count=book.page_count,
            width_mm=book.width_mm,
            height_mm=book.height_mm,
            spine_mm=book.spine_mm,
            weight_g=book.weight_g,
            cover_pdf_url=cover,
        )
