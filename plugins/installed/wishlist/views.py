"""Wishlist storefront views."""
from __future__ import annotations

import json

from morpheus.views import login_required
from morpheus.views import HttpResponseBadRequest, JsonResponse
from morpheus.views import get_object_or_404, redirect, render
from morpheus.views import csrf_protect
from morpheus.views import require_http_methods


def _decode_body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return {}
    return dict(request.POST.items())


def _wishlist_for(request):
    from plugins.installed.wishlist.services import get_or_create_wishlist
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return get_or_create_wishlist(customer=user)
    if hasattr(request, 'session'):
        if not request.session.session_key:
            request.session.save()
        return get_or_create_wishlist(session_key=request.session.session_key)
    return None


@require_http_methods(['GET'])
def wishlist_view(request):
    wishlist = _wishlist_for(request)
    items = []
    if wishlist:
        items = list(
            wishlist.items.select_related('product', 'variant').all()
        )
    return render(request, 'wishlist/wishlist.html', {
        'wishlist': wishlist, 'items': items,
    })


@csrf_protect
@require_http_methods(['POST'])
def add_to_wishlist_view(request):
    body = _decode_body(request)
    slug = body.get('slug') or body.get('product_slug')
    if not slug:
        return HttpResponseBadRequest('Missing product slug.')
    from plugins.installed.catalog.models import Product
    from plugins.installed.wishlist.services import add_item

    product = get_object_or_404(Product, slug=slug, status='active')
    wishlist = _wishlist_for(request)
    if wishlist is None:
        return HttpResponseBadRequest('Could not resolve wishlist.')
    item = add_item(wishlist=wishlist, product=product, note=body.get('note', ''))
    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({
            'ok': True, 'wishlist_id': str(wishlist.id),
            'product_slug': product.slug, 'count': wishlist.item_count,
        })
    return redirect('wishlist:home')


@csrf_protect
@require_http_methods(['POST'])
def remove_from_wishlist_view(request, item_id):
    from plugins.installed.wishlist.models import WishlistItem
    wishlist = _wishlist_for(request)
    if wishlist is None:
        return HttpResponseBadRequest('No wishlist.')
    WishlistItem.objects.filter(wishlist=wishlist, id=item_id).delete()
    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({'ok': True, 'count': wishlist.item_count})
    return redirect('wishlist:home')


@require_http_methods(['GET'])
def shared_wishlist_view(request, token):
    from plugins.installed.wishlist.models import Wishlist
    wishlist = get_object_or_404(Wishlist, share_token=token, is_public=True)
    items = list(wishlist.items.select_related('product').all())
    return render(request, 'wishlist/shared.html', {
        'wishlist': wishlist, 'items': items,
    })


@login_required
@csrf_protect
@require_http_methods(['POST'])
def share_wishlist_view(request):
    from plugins.installed.wishlist.services import make_shareable
    wishlist = _wishlist_for(request)
    if wishlist is None:
        return HttpResponseBadRequest('No wishlist.')
    token = make_shareable(wishlist)
    return JsonResponse({'ok': True, 'token': token, 'url': f'/wishlist/shared/{token}/'})
