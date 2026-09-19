"""Migrate catalog.Product rows into product-kind BookableService listings.

Montenegro-local: the site converges on the booking engine, so every physical
shop product becomes a `BookableService(listing_kind='product')`. Variable
products' variants become PricingTier rows once that model exists (Phase 2);
here we carry name/description/price/category/images. Idempotent (keyed on the
product slug, truncated to the service slug limit). The source Product is
archived (not deleted) so nothing is lost and the move is reversible.

    python manage.py migrate_products_to_bookable
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from djmoney.money import Money

FALLBACK_VENDOR = {'name': 'Montenegro Makers', 'slug': 'montenegro-makers'}


def _service_slug(product_slug: str) -> str:
    return (product_slug or 'listing')[:200]


class Command(BaseCommand):
    help = 'Copy active catalog.Product rows into product-kind BookableService listings.'

    @transaction.atomic
    def handle(self, *args, **opts):
        from plugins.installed.booking_marketplace.models import BookableService, ServiceImage
        from plugins.installed.catalog.models import Product, Vendor

        fallback = None
        created = skipped = 0
        for p in Product.objects.filter(status='active').select_related('category', 'vendor'):
            slug = _service_slug(p.slug)
            if BookableService.objects.filter(slug=slug).exists():
                skipped += 1
                continue

            vendor = p.vendor
            if vendor is None:
                if fallback is None:
                    fallback, _ = Vendor.objects.get_or_create(
                        slug=FALLBACK_VENDOR['slug'],
                        defaults={'name': FALLBACK_VENDOR['name'], 'is_active': True},
                    )
                vendor = fallback

            svc = BookableService.objects.create(
                vendor=vendor,
                name=p.name,
                slug=slug,
                listing_kind='product',
                short_description=(p.short_description or '')[:300],
                description=p.description or '',
                category=p.category,
                price=Money(p.price.amount, 'EUR'),
                is_active=True,
            )

            # Cover image + gallery from ProductImage (ordered).
            imgs = list(p.images.all().order_by('sort_order'))
            for i, pi in enumerate(imgs):
                if not pi.image:
                    continue
                if i == 0 and not svc.image:
                    svc.image.save(pi.image.name.rsplit('/', 1)[-1], pi.image, save=True)
                else:
                    si = ServiceImage(service=svc, alt=pi.alt_text or '', sort_order=i)
                    si.image.save(pi.image.name.rsplit('/', 1)[-1], pi.image, save=True)

            p.status = 'archived'
            p.save(update_fields=['status'])
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Products → bookable: {created} migrated, {skipped} already present.'
        ))
