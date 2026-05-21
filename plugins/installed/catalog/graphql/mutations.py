"""Catalog GraphQL mutations.

Staff-only. The single mutation today (`publish_digital_product`)
mirrors the MCP tool of the same name — both delegate to
``plugins.installed.catalog.services.publish_digital_product`` so
shape, validation, and side-effects stay in sync across the two
agent-facing surfaces.
"""
from __future__ import annotations

import strawberry


@strawberry.type
class PublishDigitalProductResult:
    id: strawberry.ID
    slug: str
    sku: str
    name: str
    url: str
    error: str


@strawberry.input
class PublishDigitalProductInput:
    title: str
    pdf_url: str
    price_amount: str
    price_currency: str = 'USD'
    description: str = ''
    short_description: str = ''
    author: str = ''
    cover_image_url: str = ''
    category_slug: str = ''
    sku: str = ''
    slug: str = ''
    status: str = 'active'


def _is_staff(info) -> bool:
    request = getattr(info.context, 'request', None) or (
        info.context.get('request') if isinstance(info.context, dict) else None
    )
    user = getattr(request, 'user', None) if request else None
    return bool(user and getattr(user, 'is_staff', False))


def _err(msg: str) -> PublishDigitalProductResult:
    return PublishDigitalProductResult(
        id=strawberry.ID(''), slug='', sku='', name='', url='', error=msg,
    )


@strawberry.type
class CatalogMutationExtension:

    @strawberry.mutation(
        description='Publish a digital product (PDF book) from URLs. Staff-only.',
    )
    def publish_digital_product(
        self,
        info: strawberry.Info,
        input: PublishDigitalProductInput,
    ) -> PublishDigitalProductResult:
        if not _is_staff(info):
            return _err('Forbidden — staff only.')
        from plugins.installed.catalog.services import (
            PublishError,
            publish_digital_product as _publish,
        )
        try:
            r = _publish(
                title=input.title,
                pdf_url=input.pdf_url,
                price_amount=input.price_amount,
                price_currency=input.price_currency,
                description=input.description,
                short_description=input.short_description,
                author=input.author,
                cover_image_url=input.cover_image_url,
                category_slug=input.category_slug,
                sku=input.sku,
                slug=input.slug,
                status=input.status,
            )
        except PublishError as e:
            return _err(str(e))
        return PublishDigitalProductResult(
            id=strawberry.ID(r['id']), slug=r['slug'], sku=r['sku'],
            name=r['name'], url=r['url'], error='',
        )
