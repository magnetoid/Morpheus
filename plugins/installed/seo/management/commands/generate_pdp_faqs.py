"""
generate_pdp_faqs — auto-generate a FAQ block per product from its reviews.

For every product with >=3 approved reviews we ask the active LLM
provider for up to 5 Q&A pairs grounded in review content, and
persist the result as a ``seo.pdp_faqs`` JSON metafield. The PDP
template reads the metafield and renders both a visible accordion
and FAQPage JSON-LD.

Idempotent: skips products whose metafield was refreshed in the
last 14 days unless --force is set.
"""
from __future__ import annotations

from core.llm_parsing import parse_llm_json
import logging
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('morpheus.seo.faq')

NAMESPACE = 'seo'
KEY = 'pdp_faqs'
SYSTEM_PROMPT = (
    "You extract frequently-asked questions a prospective buyer would ask "
    "about a book, grounded in the customer review excerpts provided. "
    "Return STRICT JSON only — no commentary, no markdown fences. "
    "Output an array of at most 5 objects each shaped {\"q\":\"...\",\"a\":\"...\"}. "
    "Answers are 1–2 sentences, drawn from the consensus across reviews. "
    "If a fact isn't supported by the reviews, omit the Q. If no Qs are well "
    "supported, return [] (empty array)."
)


class Command(BaseCommand):
    help = 'Generate PDP FAQ blocks from product reviews via the active LLM.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slugs', nargs='*', default=None,
            help='Only process these product slugs (default: all eligible).',
        )
        parser.add_argument(
            '--min-reviews', type=int, default=3,
            help='Minimum approved reviews required to attempt generation.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Regenerate even if a recent metafield exists.',
        )
        parser.add_argument(
            '--limit', type=int, default=200,
            help='Hard cap on products processed in one run.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be saved, don\'t persist.',
        )

    def handle(self, *args, **opts):
        from plugins.installed.catalog.models import Product, Review
        from plugins.installed.metafields.models import Metafield

        slugs = opts.get('slugs')
        min_reviews = opts['min_reviews']
        force = opts['force']
        limit = opts['limit']
        dry_run = opts['dry_run']

        qs = Product.objects.filter(status='active').order_by('-updated_at')
        if slugs:
            qs = qs.filter(slug__in=slugs)
        qs = qs[:limit]

        ct = ContentType.objects.get_for_model(Product)
        fresh_cutoff = timezone.now() - timedelta(days=14)

        gateway = None
        processed = saved = skipped = 0
        for product in qs:
            processed += 1
            reviews = list(
                Review.objects.filter(product=product, is_approved=True)
                .order_by('-helpful_votes', '-created_at')[:25]
            )
            if len(reviews) < min_reviews:
                continue

            existing = Metafield.objects.filter(
                content_type=ct, object_id=str(product.pk),
                namespace=NAMESPACE, key=KEY,
            ).first()
            if existing and not force and existing.updated_at >= fresh_cutoff:
                skipped += 1
                continue

            if gateway is None:
                from plugins.installed.ai_assistant.services.llm import get_llm
                gateway = get_llm()

            review_chunks = []
            for r in reviews:
                title = (r.title or '').strip()
                body = (r.body or '').strip()
                if not body:
                    continue
                review_chunks.append(
                    f'- ({r.rating}★) {title + ". " if title else ""}{body[:600]}'
                )
            if not review_chunks:
                continue

            prompt = (
                f'Book title: {product.name}\n'
                f'Short description: {(product.short_description or "")[:400]}\n\n'
                f'Customer reviews:\n' + '\n'.join(review_chunks)
            )
            try:
                raw = gateway.complete(
                    prompt=prompt, system=SYSTEM_PROMPT, temperature=0.4,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning('faq-gen: %s for product %s', e, product.slug)
                continue

            faqs = _parse_faq_payload(raw)
            if not faqs:
                continue

            if dry_run:
                self.stdout.write(self.style.NOTICE(
                    f'[dry-run] {product.slug} → {len(faqs)} FAQs'
                ))
                continue

            Metafield.objects.update_or_create(
                content_type=ct, object_id=str(product.pk),
                namespace=NAMESPACE, key=KEY,
                defaults={
                    'value': json.dumps(faqs, ensure_ascii=False),
                    'value_type': 'json',
                    'description': 'Auto-generated FAQ from approved reviews.',
                },
            )
            saved += 1
            self.stdout.write(self.style.SUCCESS(
                f'{product.slug} → {len(faqs)} FAQs'
            ))

        self.stdout.write(
            f'\nDone. processed={processed} saved={saved} '
            f'skipped_fresh={skipped}'
        )


def _parse_faq_payload(raw: str) -> list[dict]:
    """Parse an LLM response into [{q, a}, ...]. The agent is asked for
    a top-level array; the shared parser handles the JSON edges
    (code fences, repair). Per-item normalisation stays here so
    {question:..., answer:...} payloads also work."""
    data = parse_llm_json(raw or '')
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = (item.get('q') or item.get('question') or '').strip()
        a = (item.get('a') or item.get('answer') or '').strip()
        if q and a:
            out.append({'q': q[:240], 'a': a[:600]})
        if len(out) >= 5:
            break
    return out
