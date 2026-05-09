"""Storefront-facing endpoints for reviews."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


@login_required
@require_POST
def add_review(request, product_id):
    """Submit a review for a product. Auto-publishes — moderation deferred
    until the merchant actually asks for it. Redirects back to the PDP."""
    from plugins.installed.catalog.models import Product
    from plugins.installed.reviews.models import Review

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
        Review.objects.create(
            product=product, customer=request.user,
            rating=rating, body=body[:5000], status='published',
        )
    return redirect(f'/products/{product.slug}/#reviews')
