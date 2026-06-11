"""View decorators, response classes, and shortcuts for plugin authors.

A curated re-export of the Django view-layer surface plugins use day to
day. Always prefer ``from morpheus.views import ...`` over reaching into
``django.shortcuts`` / ``django.http`` / ``django.contrib.*``.

Both spellings of the staff decorator are exported:

* ``staff_required`` — preferred public name.
* ``staff_member_required`` — kept as an alias for transition.
"""

from __future__ import annotations

# Flash-message framework ────────────────────────────────────────────────────
from django.contrib import messages

# Decorators ─────────────────────────────────────────────────────────────────
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.contrib.auth.decorators import login_required

# Response objects + request type ────────────────────────────────────────────
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
    StreamingHttpResponse,
)

# Rendering shortcuts ────────────────────────────────────────────────────────
from django.shortcuts import (
    get_list_or_404,
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST

# Preferred public name for the staff decorator.
staff_required = staff_member_required

__all__ = [
    # decorators
    'staff_required',
    'staff_member_required',
    'login_required',
    'csrf_exempt',
    'csrf_protect',
    'require_http_methods',
    'require_POST',
    'require_GET',
    # responses
    'HttpRequest',
    'HttpResponse',
    'HttpResponseBadRequest',
    'HttpResponseForbidden',
    'HttpResponseNotFound',
    'HttpResponseRedirect',
    'HttpResponseServerError',
    'JsonResponse',
    'StreamingHttpResponse',
    'Http404',
    # shortcuts
    'render',
    'redirect',
    'get_object_or_404',
    'get_list_or_404',
    # messages framework
    'messages',
]
