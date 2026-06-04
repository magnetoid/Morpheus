"""GraphQL input types for Book Product mutations."""

from __future__ import annotations

import strawberry


@strawberry.input
class BookProductInput:
    """Upsert book attributes for a product. `product_slug` is required; every
    other field is optional — only fields explicitly set are written."""

    product_slug: str
    author: str | None = None
    subtitle: str | None = None
    publisher: str | None = None
    imprint: str | None = None
    publication_date: str | None = None  # ISO YYYY-MM-DD
    edition: str | None = None
    language: str | None = None
    series: str | None = None
    series_position: str | None = None
    synopsis: str | None = None
    print_type: str | None = None
    paper_type: str | None = None
    binding: str | None = None
    page_count: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    spine_mm: int | None = None
    weight_g: int | None = None
