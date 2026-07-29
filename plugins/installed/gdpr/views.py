"""Self-service GDPR data-rights pages, owned by the gdpr plugin.

Routed at the site root via ``register_urls(prefix='')``:

  /account/privacy/      — privacy hub (tiles: export, delete, cookie prefs).
  /account/data-export/  — Art. 15: streams a ZIP of the customer's data.
  /account/delete/       — Art. 17: email-confirmed account anonymisation.

Every view runs ``gdpr_required()`` first, so all three 404 when the store
turns the GDPR master switch off. The heavy lifting (build the export dict /
scrub PII) is delegated to ``customers.services`` — this plugin only adds the
self-service surface + the ``DataRequest`` audit row.
"""

from __future__ import annotations

from morpheus.plugin.views import render
from plugins.installed.gdpr.services import gdpr_required


def _login_required(request, target):
    if not request.user.is_authenticated:
        from morpheus.plugin.views import redirect

        return redirect(f'/auth/login/?next={target}')
    return None


def account_privacy(request):
    """Privacy hub — links out to export, delete, and cookie preferences."""
    gdpr_required()
    redirect_resp = _login_required(request, '/account/privacy/')
    if redirect_resp is not None:
        return redirect_resp
    return render(request, 'gdpr/account_privacy.html', {'user': request.user})


def account_data_export(request):
    """GDPR Art. 15 — right to access.

    GET renders a confirmation page. POST builds a ZIP of JSON files (one per
    data category, assembled by ``gather_customer_data`` through the
    CUSTOMER_DATA_EXPORT filter — disabled plugins drop out) and streams it.
    """
    gdpr_required()
    redirect_resp = _login_required(request, '/account/data-export/')
    if redirect_resp is not None:
        return redirect_resp
    if request.method == 'POST':
        import io  # noqa: PLC0415
        import json  # noqa: PLC0415
        import zipfile  # noqa: PLC0415
        from datetime import date  # noqa: PLC0415

        from django.http import HttpResponse  # noqa: PLC0415
        from django.utils import timezone  # noqa: PLC0415

        from plugins.installed.customers.services import gather_customer_data  # noqa: PLC0415
        from plugins.installed.gdpr.models import DataRequest  # noqa: PLC0415

        data_by_filename = gather_customer_data(request.user)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, payload in data_by_filename.items():
                zf.writestr(filename, json.dumps(payload, indent=2, default=str))

        DataRequest.objects.create(
            kind='export',
            status='completed',
            customer=request.user,
            email=(request.user.email or '').lower(),
            completed_at=timezone.now(),
        )

        resp = HttpResponse(buf.getvalue(), content_type='application/zip')
        fname = f'my-data-{request.user.pk}-{date.today().isoformat()}.zip'
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp
    return render(request, 'gdpr/account_data_export.html', {'user': request.user})


def account_delete(request):
    """GDPR Art. 17 — right to be forgotten.

    GET renders a destructive-action confirmation page. POST requires the user
    to type their own email back, records the request, then anonymises the
    account (``anonymise_customer``), logs them out, and redirects home.
    """
    gdpr_required()
    redirect_resp = _login_required(request, '/account/delete/')
    if redirect_resp is not None:
        return redirect_resp
    error = None
    if request.method == 'POST':
        from django.contrib import messages  # noqa: PLC0415
        from django.contrib.auth import logout  # noqa: PLC0415
        from django.db import transaction  # noqa: PLC0415
        from django.shortcuts import redirect as _redirect  # noqa: PLC0415
        from django.utils import timezone  # noqa: PLC0415

        from plugins.installed.customers.services import anonymise_customer  # noqa: PLC0415
        from plugins.installed.gdpr.models import DataRequest  # noqa: PLC0415

        typed = (request.POST.get('confirm_email') or '').strip().lower()
        if typed != (request.user.email or '').lower():
            error = "That email doesn't match the one on your account."
        else:
            customer = request.user
            email = (customer.email or '').lower()
            with transaction.atomic():
                DataRequest.objects.create(
                    kind='erasure',
                    status='completed',
                    customer=customer,
                    email=email,
                    completed_at=timezone.now(),
                )
                anonymise_customer(customer)
            logout(request)
            messages.success(
                request,
                'Your account is gone. Your reviews and orders have been '
                "anonymised. We're sorry to see you go.",
            )
            return _redirect('/')
    return render(request, 'gdpr/account_delete.html', {'user': request.user, 'error': error})
