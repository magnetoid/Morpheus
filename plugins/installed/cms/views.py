"""CMS storefront views — page resolver + form submission."""

from __future__ import annotations

from morpheus.views import (
    Http404,
    csrf_protect,
    get_object_or_404,
    messages,
    redirect,
    render,
    require_http_methods,
)


def page_view(request, slug: str):
    from plugins.installed.cms.services import get_live_page

    page = get_live_page(slug)
    if page is None:
        raise Http404
    # Staff admin-bar deep-link: edit this page in the dashboard.
    active_edit_url = ''
    if request.user.is_authenticated and request.user.is_staff:
        from django.urls import reverse

        active_edit_url = reverse('cms_dashboard:page_edit', kwargs={'page_id': page.pk})
    return render(
        request,
        'cms/page.html',
        {'page': page, 'active_edit_url': active_edit_url, 'active_edit_label': 'Edit page'},
    )


@csrf_protect
@require_http_methods(['POST'])
def form_submit(request, key: str):
    from plugins.installed.cms.models import Form
    from plugins.installed.cms.services import submit_form

    form = get_object_or_404(Form, key=key, is_active=True)
    submit_form(form=form, payload=dict(request.POST.items()), request=request)
    messages.success(request, form.success_message)
    return redirect(request.META.get('HTTP_REFERER', '/'))
