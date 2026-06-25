"""Storefront home page."""

from __future__ import annotations

from api.client import internal_graphql
from morpheus.views import render


def home(request):
    data = (
        internal_graphql(
            """
        query Home {
          featuredProducts: products(first: 8, featured: true) {
            id name slug productType
            price { amount currency } priceStartsFrom
            primaryImage { url altText }
            isOnSale discountPercentage
          }
          collections(featured: true, first: 6) {
            id name slug image { url }
          }
          categories(topLevel: true, first: 8) {
            id name slug image { url }
          }
        }
    """,
            request=request,
        )
        or {}
    )
    # Templates use snake_case; GraphQL returns camelCase. Normalise.
    data.setdefault('featured_products', data.get('featuredProducts', []) or [])
    
    # Advanced Personalization: Reorder home page products for the individual visitor
    # This turns the static featured grid into a hyper-personalized storefront.
    try:
        from plugins.installed.personalisation.services import rank_for_visitor
        data['featured_products'] = rank_for_visitor(
            request, 
            data['featured_products'], 
            surface='home_featured'
        )
    except Exception:
        pass
        
    data.setdefault('seasonal_products', data.get('featured_products', []))

    # Staff picks rail — same fallback chain as the dedicated /staff-picks/ page.
    try:
        from plugins.installed.catalog.models import Collection, Product

        sp_collection = (
            Collection.objects.filter(slug='staff-picks', is_active=True).first()
            or Collection.objects.filter(slug='editors-pick-april', is_active=True).first()
        )
        sp_products = (
            list(
                Product.objects.filter(status='active', collections=sp_collection).order_by(
                    '-is_featured', '-created_at'
                )[:8]
            )
            if sp_collection
            else []
        )
    except Exception:  # noqa: BLE001
        sp_collection, sp_products = None, []
    data['staff_picks_collection'] = sp_collection
    data['staff_picks'] = sp_products

    return render(request, 'storefront/home.html', data)
