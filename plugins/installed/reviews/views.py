"""Storefront-facing endpoints for reviews — operates on catalog.Review."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


@login_required
@require_POST
def add_review(request, product_id):
    """Submit a review for a product. Auto-approves — moderation deferred
    until the merchant actually asks for it. Redirects back to the PDP."""
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
        review, created = Review.objects.get_or_create(
            product=product,
            customer=request.user,
            defaults={'rating': rating, 'body': body[:5000], 'is_approved': True},
        )
        if not created:
            # An edit keeps the merchant's moderation decision: a review the
            # dashboard hid (is_approved=False) must not re-publish itself
            # because its author posted the form again.
            review.rating = rating
            review.body = body[:5000]
            review.save(update_fields=['rating', 'body', 'updated_at'])
    return redirect(f'/products/{product.slug}/#reviews')
