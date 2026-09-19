"""Seed ServiceReview rows for every bookable experience + sync the
denormalised `rating` / `review_count` fields — idempotent (skips any
experience that already has reviews).

Deterministic per experience: seeded with `random.Random(slug)` so re-runs
and CI produce byte-identical review sets. Only the review *dates* vary
with real time (`timezone.now()` is the spread anchor, not seeded content).

    python manage.py seed_reviews
"""

from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.utils import timezone

# Diverse, international first-name + last-initial pool — matches the
# theme's existing testimonial style ("Sarah M.").
REVIEWER_NAMES = [
    'Sarah M.',
    'James O.',
    'Elena K.',
    'Marco R.',
    'Ana P.',
    'Thomas B.',
    'Ingrid S.',
    'Luca F.',
    'Nina D.',
    'David H.',
    'Katarina J.',
    'Michael T.',
    'Sophie L.',
    'Andrei V.',
    'Claire W.',
    'Stefan G.',
    'Maria C.',
    'Peter N.',
    'Yuki S.',
    'Olga R.',
    'Daniel K.',
    'Isabelle M.',
    'Marko P.',
    'Hannah B.',
    'Viktor L.',
    'Rachel A.',
    'Nikolai P.',
    'Charlotte E.',
    'Ahmed F.',
    'Julia W.',
]

TITLES = {
    5: ['Highlight of our trip', 'Unforgettable', 'Worth every penny', 'Absolutely loved it'],
    4: ['Really enjoyable', 'Great experience', 'Would recommend', 'Good day out'],
    3: ['Decent, with a few hiccups', 'It was okay', 'Good but not great', 'Mixed feelings'],
}

# ~40 grounded fragment templates, keyed by category name (lower-cased) —
# 'positive' fragments back 4/5-star reviews, 'critical' back 3-star ones
# (mildly critical, not glowing — honest realism).
FRAGMENTS = {
    'adventure': {
        'positive': [
            'Our guide knew every trail and kept the pace right for the whole group.',
            'The canyon views from the ridge were unreal — worth every uphill step.',
            'Good safety gear and a guide who clearly loves these mountains.',
        ],
        'critical': [
            'The hike was fine but the pace felt rushed near the end.',
            'Good scenery, though the group was bigger than expected and it felt crowded.',
        ],
    },
    'water sports': {
        'positive': [
            'The boat crew handled the swell like pros and still found us a quiet cove.',
            'Snorkeling gear was clean and well-fitted, and the skipper found calm, clear water.',
            'Kayaking along the cliffs at sunset was the highlight of our whole trip.',
        ],
        'critical': [
            'Water was choppier than advertised so we spent less time snorkeling than planned.',
            'Life jackets were a bit tight, otherwise a decent afternoon on the water.',
        ],
    },
    'culture': {
        'positive': [
            "Our guide brought the old town's history to life with stories you won't find in a guidebook.",
            'Loved wandering the stone lanes with someone who actually grew up here.',
            'The fortress views over the bay were breathtaking and the pace let us take photos.',
        ],
        'critical': [
            "Interesting history, but the walking pace was slower than I'd like.",
            'A bit too much time at the souvenir stop for my taste.',
        ],
    },
    'dining': {
        'positive': [
            'Every course was better than the last — the seafood risotto alone was worth it.',
            'Portions were generous and the chef came out to explain each dish.',
            'Cozy konoba setting with a view that matched the food.',
        ],
        'critical': [
            'Food was good but service was slow between courses.',
            'Nice setting, though a couple of dishes were a bit salty for my taste.',
        ],
    },
    'wine': {
        'positive': [
            'The cellar tour was fascinating and the vranac was the best we tried in Montenegro.',
            'Our host poured generously and paired each wine with local cheese and prosciutto.',
            'Beautiful vineyard views and a host who clearly loves what he does.',
        ],
        'critical': [
            'Good wines, but the tasting felt rushed toward the end.',
            'A bit pricey for the pours, though the setting was lovely.',
        ],
    },
    'wellness': {
        'positive': [
            'Left feeling completely reset — the massage therapist was excellent.',
            "The treatment room's sea view made it even better.",
            'Quiet, professional, and exactly the reset we needed mid-trip.',
        ],
        'critical': [
            'Relaxing overall, though the room was a little cold.',
            'Good treatment but the schedule ran about twenty minutes behind.',
        ],
    },
    'books': {
        'positive': [
            "Our guide's knowledge of Njegoš and Montenegro's literary history felt like a private lecture.",
            'Seeing the first printing press up close was worth the trip alone.',
            'A quieter, more thoughtful experience than the usual tours — loved it.',
        ],
        'critical': [
            'Fascinating subject, but a lot of dense detail packed into a short visit.',
            "Interesting stop, though it's clearly a niche interest for our group.",
        ],
    },
    'generic': {
        'positive': [
            'Everything ran smoothly from booking to the day itself.',
            'Friendly host, would recommend to anyone visiting Montenegro.',
            'Great value for the price and exactly as described.',
        ],
        'critical': [
            'Solid experience overall, just a little pricier than we expected.',
            'Good but nothing that stood out compared to other things we did.',
        ],
    },
}


def _category_key(service) -> str:
    name = (service.category.name if service.category_id else '').strip().lower()
    return name if name in FRAGMENTS else 'generic'


def _rating(rng: random.Random) -> int:
    return rng.choices([5, 4, 3], weights=[0.6, 0.3, 0.1], k=1)[0]


def _body(rng: random.Random, bucket: dict, rating: int) -> str:
    positive, critical = bucket['positive'], bucket['critical']
    if rating >= 4:
        n = rng.randint(1, 3)
        chosen = rng.sample(positive, min(n, len(positive)))
        if rating == 4 and critical and rng.random() < 0.3:
            chosen.append(rng.choice(critical))
    else:
        n = rng.randint(1, 2)
        chosen = rng.sample(critical, min(n, len(critical)))
        if positive and rng.random() < 0.4:
            chosen.insert(0, rng.choice(positive))
    rng.shuffle(chosen)
    return ' '.join(chosen)


class Command(BaseCommand):
    help = 'Seed guest reviews for every experience + sync denormalised rating (idempotent).'

    def handle(self, *args, **options):
        from plugins.installed.booking_marketplace.models import BookableService, ServiceReview

        created = 0
        for svc in BookableService.objects.filter(listing_kind='experience'):
            if svc.reviews.exists():
                continue

            rng = random.Random(svc.slug)  # noqa: S311 — deterministic seed content, not crypto
            bucket = FRAGMENTS[_category_key(svc)]
            n_reviews = rng.randint(3, 8)
            reviewers = rng.sample(REVIEWER_NAMES, min(n_reviews, len(REVIEWER_NAMES)))

            used_bodies = set()
            reviews = []
            for i in range(n_reviews):
                rating = _rating(rng)
                body = _body(rng, bucket, rating)
                for _attempt in range(10):
                    if body not in used_bodies:
                        break
                    body = _body(rng, bucket, rating)
                used_bodies.add(body)
                author = reviewers[i] if i < len(reviewers) else rng.choice(REVIEWER_NAMES)
                reviews.append(
                    ServiceReview(
                        service=svc,
                        author_name=author,
                        rating=rating,
                        title=rng.choice(TITLES[rating]),
                        body=body,
                    )
                )

            ServiceReview.objects.bulk_create(reviews)
            # auto_now_add stamps 'now' at insert time — spread dates after
            # the fact so reviews don't all land on the same day.
            for review in reviews:
                review.created_at = timezone.now() - timedelta(days=rng.randint(3, 240))
            ServiceReview.objects.bulk_update(reviews, ['created_at'])
            created += len(reviews)

        for svc in BookableService.objects.filter(listing_kind='experience'):
            agg = svc.reviews.aggregate(n=Count('id'), avg=Avg('rating'))
            BookableService.objects.filter(pk=svc.pk).update(
                review_count=agg['n'] or 0,
                rating=round(agg['avg'] or 0, 1),
            )

        if options.get('verbosity', 1) > 0:
            self.stdout.write(self.style.SUCCESS(f'Seeded {created} reviews.'))
