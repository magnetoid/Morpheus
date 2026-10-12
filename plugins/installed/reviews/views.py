"""Storefront-facing endpoints for reviews — operates on catalog.Review."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


def _bought(user, product) -> bool:
    """Whether ``user`` has a paid order holding ``product``, not refunded or cancelled."""
    from plugins.installed.orders.models import OrderItem

    return (
        OrderItem.objects.filter(
            order__customer=user, product=product, order__payment_status='paid'
        )
        .exclude(order__status__in=('cancelled', 'refunded'))
        .exists()
    )


@login_required
@require_POST
def add_review(request, product_id):
    """Submit a review for a product. Redirects back to the PDP.

    Approved reviews feed the product's rating in structured data, a public
    claim, so a review is published at once only from a buyer (and marked a
    verified purchase); anyone else's waits for the merchant's approval.
    """
    from plugins.installed.catalog.models import Product, Review

    product = Product.objects.filter(id=product_id).first()
    if product is None:
        return redirect('/products/')

    body = (request.POST.get('body') or '').strip()
    rating_raw = (request.POST.get('rating') or '5').strip()
    try:
        rating = max(1, min(5, int(rating_raw)))
    except ValueError:
        rating = 5

    if body:
        verified = _bought(request.user, product)
        review, created = Review.objects.get_or_create(
            product=product,
            customer=request.user,
            defaults={
                'rating': rating,
                'body': body[:5000],
                'is_approved': verified,
                'is_verified_purchase': verified,
            },
        )
        if not created:
            # An edit keeps the merchant's moderation decision: a review the
            # dashboard hid (is_approved=False) must not re-publish itself
            # because its author posted the form again.
            review.rating = rating
            review.body = body[:5000]
            review.save(update_fields=['rating', 'body', 'updated_at'])
        if created and not verified:
            from django.contrib import messages
            from django.utils.translation import gettext

            messages.info(
                request, gettext('Thank you. Your review will appear once the shop approves it.')
            )
    return redirect(f'/products/{product.slug}/#reviews')
