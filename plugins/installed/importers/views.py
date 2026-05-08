"""Importer dashboard views — CSV products import/export + Shopify migration."""
from __future__ import annotations

import io
import logging

from morpheus.views import staff_member_required
from morpheus.views import HttpResponse
from morpheus.views import redirect, render

logger = logging.getLogger('morpheus.importers.views')


@staff_member_required
def csv_index(request):
    if request.method == 'POST' and request.FILES.get('csv'):
        from plugins.installed.importers.adapters.csv_products import CsvProductImporter
        text = io.TextIOWrapper(request.FILES['csv'].file, encoding='utf-8', errors='ignore')
        importer = CsvProductImporter(file=text)
        try:
            summary = importer.run(started_by=request.user.email if request.user.is_authenticated else '')
        except Exception as e:  # noqa: BLE001
            return render(request, 'importers/csv.html', {'error': str(e), 'summary': None})
        return render(request, 'importers/csv.html', {'summary': summary, 'error': None})
    return render(request, 'importers/csv.html', {'summary': None, 'error': None})


@staff_member_required
def csv_export(request):
    from plugins.installed.importers.adapters.csv_products import export_products_csv
    body = export_products_csv()
    resp = HttpResponse(body, content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="morpheus-products.csv"'
    return resp


@staff_member_required
def shopify_index(request):
    """One-click Shopify migration: shop + admin API token → import.

    Synchronous for now — works for stores with up to a few thousand
    products. Larger stores should run via the management command in
    a Celery task; this view is the friction-free path for everything
    smaller. Fail-soft: any exception is captured and shown in the UI
    so the merchant always sees an outcome.
    """
    summary = None
    error = ''
    form_data = {
        'shop': request.POST.get('shop', '') if request.method == 'POST' else '',
        'token': '',
        'import_products': True,
        'import_customers': True,
        'import_orders': True,
    }
    if request.method == 'POST':
        from plugins.installed.importers.adapters.shopify import ShopifyImporter
        shop = (request.POST.get('shop') or '').strip()
        token = (request.POST.get('token') or '').strip()
        what_products = request.POST.get('import_products') == 'on'
        what_customers = request.POST.get('import_customers') == 'on'
        what_orders = request.POST.get('import_orders') == 'on'
        form_data.update({
            'shop': shop,
            'import_products': what_products,
            'import_customers': what_customers,
            'import_orders': what_orders,
        })

        if not shop or not token:
            error = 'Shop name and admin API token are required.'
        elif not (what_products or what_customers or what_orders):
            error = 'Pick at least one entity type to import.'
        else:
            shop = shop.replace('https://', '').replace('http://', '')
            shop = shop.split('.myshopify.com')[0].rstrip('/')
            try:
                importer = ShopifyImporter(shop=shop, token=token)
                # Honour the merchant's checkboxes by short-circuiting
                # the iterators they don't want to run.
                if not what_products:
                    importer.iter_products = lambda: iter([])
                if not what_customers:
                    importer.iter_customers = lambda: iter([])
                if not what_orders:
                    importer.iter_orders = lambda: iter([])
                summary = importer.run(
                    started_by=(request.user.email
                                if request.user.is_authenticated else 'shopify-import'),
                )
            except Exception as e:  # noqa: BLE001 — surface everything in the UI
                logger.warning('shopify import failed: %s', e, exc_info=True)
                error = str(e)
    return render(request, 'importers/shopify.html', {
        'summary': summary,
        'error': error,
        'form_data': form_data,
    })
