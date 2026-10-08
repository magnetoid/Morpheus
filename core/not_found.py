"""The 404 handler: the theme's page for a missing page, plain text for a missing file.

Django's default `page_not_found` renders `404.html` for everything, so every
missing stylesheet, image and `wp-login.php` probe paid for a full themed render
(53–120 KB, every context processor) that no browser or crawler could use. A
request for a FILE gets a tiny plain-text 404; a request for a PAGE still gets
the theme's 404, through Django's own handler — whose context
(`request_path` + `exception`) is how the seo app recognises an error render and
keeps its head bare.
"""

from __future__ import annotations

import re

from django.http import HttpResponseNotFound

# Paths that are files, never pages: anything under the asset roots, and any
# path ending in a file extension a storefront page never has.
_ASSET_PREFIXES = ('/static/', '/media/')
_FILE_SUFFIX = re.compile(
    r'\.(?:css|js|mjs|map|png|jpe?g|gif|webp|avif|svg|ico|bmp|tiff?|woff2?|ttf|otf|eot'
    r'|json|xml|txt|csv|pdf|zip|gz|tar|rar|7z|mp3|mp4|webm|mov|php\d?|aspx?|jsp|cgi|env'
    r'|ini|bak|old|sql|sh|yml|yaml|log|git)$',
    re.I,
)


def is_file_request(path: str) -> bool:
    return (path or '').startswith(_ASSET_PREFIXES) or bool(_FILE_SUFFIX.search(path or ''))


def page_not_found(request, exception=None):
    """`handler404` (morph/urls.py)."""
    if is_file_request(getattr(request, 'path', '')):
        return HttpResponseNotFound('Not found.', content_type='text/plain; charset=utf-8')
    from django.views.defaults import page_not_found as theme_page_not_found

    return theme_page_not_found(request, exception)
