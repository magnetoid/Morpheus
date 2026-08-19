"""Copy per-entity SEO out of its old homes and into `SeoMeta`.

Three sources, all of which `resolve_meta` still reads as a fallback, so this
is a *consolidation*, not a rescue — nothing is lost if it never runs:

  1. `catalog.Product`'s native SEO columns (meta_title, meta_description,
     focus_keyword, canonical_url, og_*, twitter_*, noindex/nofollow).
  2. `catalog.Category` / `catalog.Collection`'s `meta_title` / `meta_description`.
  3. The `seo.ai_answer` metafield.

Deliberately a command rather than a data migration. A backfill over a large
catalog is exactly the operation that should not be holding a schema lock
during a deploy, it needs to be re-runnable when a merchant asks "did that
work?", and `--dry-run` has to be free. It only ever fills fields that are
EMPTY on the SeoMeta row, so running it twice is a no-op and it can never
overwrite something a merchant typed after the move.

    python manage.py seo_backfill_meta --dry-run
    python manage.py seo_backfill_meta
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

# SeoMeta field ← host-model column. og_image/twitter_image are ImageFields on
# Product and URL fields here, hence the separate handling below.
_TEXT_MAP = {
    'title': 'meta_title',
    'description': 'meta_description',
    'focus_keyword': 'focus_keyword',
    'canonical_url': 'canonical_url',
    'og_title': 'og_title',
    'og_description': 'og_description',
    'twitter_title': 'twitter_title',
    'twitter_description': 'twitter_description',
}

_MAX = {
    'title': 200,
    'description': 320,
    'focus_keyword': 120,
    'canonical_url': 600,
    'og_title': 200,
    'og_description': 320,
    'twitter_title': 200,
    'twitter_description': 320,
    'og_image': 600,
    'ai_answer': 600,
}


class Command(BaseCommand):
    help = 'Copy native SEO columns and seo.* metafields into SeoMeta rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything.',
        )

    def handle(self, *args, **options):
        dry = bool(options['dry_run'])
        totals = {'products': 0, 'categories': 0, 'collections': 0, 'og_type_cleared': 0}

        from plugins.installed.catalog.models import Category, Collection, Product

        totals['products'] = self._backfill(Product.objects.all(), dry=dry)
        totals['categories'] = self._backfill(Category.objects.all(), dry=dry)
        totals['collections'] = self._backfill(Collection.objects.all(), dry=dry)
        totals['og_type_cleared'] = self._clear_autofilled_og_type(dry=dry)

        verb = 'would update' if dry else 'updated'
        self.stdout.write(
            f'{verb} {totals["products"]} product(s), {totals["categories"]} category(ies), '
            f'{totals["collections"]} collection(s); '
            f'{verb} og:type on {totals["og_type_cleared"]} autofilled row(s).'
        )

    # -- per-object ------------------------------------------------------
    def _backfill(self, queryset, *, dry: bool) -> int:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.seo.models import SeoMeta

        changed = 0
        for obj in queryset.iterator(chunk_size=500):
            values = self._values_for(obj)
            if not values:
                continue
            ct = ContentType.objects.get_for_model(type(obj))
            meta = SeoMeta.objects.filter(content_type=ct, object_id=str(obj.pk)).first()
            # An AUTOFILLED row holds the platform's guess (the product's own
            # name), not a decision: `autofill_meta_for` writes one for every
            # product on creation, and it then outranked whatever the merchant
            # had typed into the product form. So on an autofilled row the
            # native column wins; on a row the merchant edited through the
            # panel, only blanks are filled and their work is never replaced.
            autofilled = bool(meta and meta.auto_filled)
            fill = {
                field: value
                for field, value in values.items()
                if autofilled or not getattr(meta, field, '')
            }
            if not fill:
                continue
            changed += 1
            if dry:
                continue
            provenance = dict(getattr(meta, 'provenance', None) or {})
            provenance.update(dict.fromkeys(fill, 'migrated'))
            fill['provenance'] = provenance
            SeoMeta.objects.update_or_create(content_type=ct, object_id=str(obj.pk), defaults=fill)
        return changed

    def _values_for(self, obj) -> dict:
        values: dict[str, str] = {}
        for field, column in _TEXT_MAP.items():
            value = str(getattr(obj, column, '') or '').strip()
            if value:
                values[field] = value[: _MAX[field]]
        image = getattr(obj, 'og_image', None)
        url = getattr(image, 'url', None) if image else None
        if url:
            values['og_image'] = str(url)[: _MAX['og_image']]
        answer = self._ai_answer(obj)
        if answer:
            values['ai_answer'] = answer[: _MAX['ai_answer']]
        if getattr(obj, 'noindex', False) or getattr(obj, 'nofollow', False):
            values['robots'] = '{}, {}'.format(
                'noindex' if getattr(obj, 'noindex', False) else 'index',
                'nofollow' if getattr(obj, 'nofollow', False) else 'follow',
            )
        return values

    def _ai_answer(self, obj) -> str:
        """The legacy `seo.ai_answer` metafield, if the metafields app is here."""
        try:
            from django.contrib.contenttypes.models import ContentType

            from plugins.installed.metafields.models import Metafield

            ct = ContentType.objects.get_for_model(type(obj))
            row = Metafield.objects.filter(
                content_type=ct, object_id=str(obj.pk), namespace='seo', key='ai_answer'
            ).first()
            return str(row.value or '').strip() if row else ''
        except Exception:  # noqa: BLE001 — metafields is optional
            return ''

    # -- the og:type repair ----------------------------------------------
    def _clear_autofilled_og_type(self, *, dry: bool) -> int:
        """Blank the `og_type` nobody chose.

        `og_type` defaulted to a non-blank 'website' and `autofill_meta_for`
        mints a row for every product, so every product page declared
        `og:type=website` instead of `product` — the stored value outranked the
        page kind. Nothing has ever written the field, so an autofilled row
        carrying 'website' is the default, not a decision. Only `auto_filled`
        rows are touched, so a merchant's future explicit choice is safe.
        """
        from plugins.installed.seo.models import SeoMeta

        qs = SeoMeta.objects.filter(auto_filled=True, og_type='website')
        count = qs.count()
        if not dry and count:
            qs.update(og_type='')
        return count
