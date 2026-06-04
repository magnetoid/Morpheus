"""GraphQL queries for Book Product."""

from __future__ import annotations

import strawberry

from plugins.installed.book_product.graphql.types import BookProductType


@strawberry.type
class BookProductQueryExtension:
    @strawberry.field(description='Book attributes for a product, by product slug.')
    def book_product(self, info: strawberry.Info, product_slug: str) -> BookProductType | None:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        obj = (
            BookProduct.objects.select_related('product').filter(product__slug=product_slug).first()
        )
        return BookProductType.from_model(obj) if obj else None
