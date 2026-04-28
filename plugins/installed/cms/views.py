"""CMS storefront views — page resolver + form submission."""
from __future__ import annotations

from morpheus.views import messages
from morpheus.views import Http404
from morpheus.views import get_object_or_404, redirect, render
from morpheus.views import csrf_protect
from morpheus.views import require_http_methods


def page_view(request, slug: str):
    from plugins.installed.cms.services import get_live_page

    page = get_live_page(slug)
    if page is None:
        raise Http404
    return render(request, 'cms/page.html', {'page': page})


@csrf_protect
@require_http_methods(['POST'])
def form_submit(request, key: str):
    from plugins.installed.cms.models import Form
    from plugins.installed.cms.services import submit_form

    form = get_object_or_404(Form, key=key, is_active=True)
    submit_form(form=form, payload=dict(request.POST.items()), request=request)
    messages.success(request, form.success_message)
    return redirect(request.META.get('HTTP_REFERER', '/'))
