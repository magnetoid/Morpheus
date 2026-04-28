"""Importer dashboard views — CSV products import/export."""
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
