"""Redirect middleware: keep old URLs working, and watch what 404s.

Registered in `morph/settings.py` rather than contributed by the plugin, so it
runs even when the seo app is disabled — hence the explicit active check below.
A disabled app must not keep rewriting the merchant's URLs.

Three things here are not obvious and each one was a bug:

* **The language prefix.** `LocaleMiddleware` runs first but leaves
  `/fr/old-page/` in `path_info`, so a rule stored as `/old-page/` never fired
  for anyone browsing in a non-default language.
* **The query string.** A redirect that drops `?utm_source=…` breaks campaign
  attribution for every link that was ever shared.
* **The destination.** `to_path` is merchant- *and assistant*-writable and went
  straight into a `Location` header, which is an open redirect: a rule pointing
  at `https://evil.example` turns the store into a phishing hop.

It also enforces one rule that needs no stored row: `?page=1` is the clean URL
wearing a second name, so it is 301'd rather than merely canonicalised. That
belongs here because it applies to every paginated listing any app publishes,
not just the ones the storefront happens to own.
"""

from __future__ import annotations

from django.http import (
    HttpResponseGone,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)

# Status → response class. 307/308 preserve the request method, which matters
# for a POST endpoint that moved; Django has no dedicated classes for them.
_REDIRECT_CLASSES = {
    301: HttpResponsePermanentRedirect,
    302: HttpResponseRedirect,
}


class SeoRedirectMiddleware:
    """Resolve `request.path_info` against the redirect rules before the view runs."""

    SKIP_PREFIXES = (
        '/static/',
        '/media/',
        '/admin/',
        '/dashboard/',
        '/graphql',
        '/api/',
        '/v1/',
        '/healthz',
        '/readyz',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or '/'
        if any(path.startswith(prefix) for prefix in self.SKIP_PREFIXES) or not _seo_active():
            return self.get_response(request)
        # Explicit `is None` rather than `or`: an empty-bodied redirect response
        # is truthy only because Django's HttpResponse defines neither __bool__
        # nor __len__, and a redirect rule silently stopping at that detail is
        # not a thing to leave to chance.
        response = self._redirect_for(request, path)
        if response is None:
            response = _page_one_redirect(request)
        return response if response is not None else self._passthrough(request, path)

    def _redirect_for(self, request, path: str):
        """The redirect/gone response for ``path``, or None to let the view run."""
        prefix, bare_path = _split_language_prefix(path)
        from plugins.installed.seo.services import resolve_redirect

        match = resolve_redirect(bare_path)
        if match is None and prefix:
            # A merchant may have stored the language-prefixed form by hand.
            match = resolve_redirect(path)
        if match is None:
            return None

        to_path, status = match
        _count_hit(bare_path)
        if status == 410:
            return HttpResponseGone(
                'This page has been permanently removed.', content_type='text/plain'
            )
        target = _safe_target(to_path, prefix=prefix, query=request.META.get('QUERY_STRING', ''))
        if not target:
            return None
        cls = _REDIRECT_CLASSES.get(status)
        if cls is not None:
            return cls(target)
        response = HttpResponseRedirect(target)
        response.status_code = status  # 307 / 308
        return response

    def _passthrough(self, request, path: str):
        response = self.get_response(request)
        if response.status_code == 404 and not _is_pagination_404(request):
            try:
                from plugins.installed.seo.services import record_404

                record_404(path=path, referrer=request.META.get('HTTP_REFERER', '') or '')
            except Exception:  # noqa: BLE001, S110 — logging a 404 can't cost the 404
                pass
        return response


def _is_pagination_404(request) -> bool:
    """A page number past the end of a REAL listing is not a broken address.

    `record_404` stores `path_info` with the query string stripped, so a 404
    caused by `?page=999` would be filed as a broken `/products/` — a URL that
    answers 200 — and the 404 log offers a one-click "redirect this path
    somewhere". A merchant acting on that entry would 301 their entire product
    listing away. The log is for addresses that stopped working; a valid
    address with an out-of-range page number is not one.

    Only when the path itself routes: any 404 that merely CARRIED `?page=` used
    to be skipped, so a dead address linked as `/old-listing/?page=2` never
    reached the log at all.
    """
    try:
        from django.urls import Resolver404, resolve

        from plugins.installed.seo.rules.params import RESERVED_PARAMS

        if not any(key.lower() in RESERVED_PARAMS for key in request.GET):
            return False
        try:
            resolve(request.path_info)
        except Resolver404:
            return False
        return True
    except Exception:  # noqa: BLE001 — never let this decide the response
        return False


def _page_one_redirect(request):
    """301 `?page=1` onto the clean URL.

    `/shop/` and `/shop/?page=1` are the same page under two names. A canonical
    would tell an engine which one to keep and leave the other being fetched
    forever; a 301 removes it. Every other page number is a real page and is
    left alone (see `rules/pagination.py`).
    """
    from plugins.installed.seo.rules import page_one_redirect_target

    target = page_one_redirect_target(request)
    return HttpResponsePermanentRedirect(target) if target else None


def _seo_active() -> bool:
    try:
        from plugins.registry import app_registry

        return app_registry.is_active('seo')
    except Exception:  # noqa: BLE001 — registry not ready during boot
        return True


def _split_language_prefix(path: str) -> tuple[str, str]:
    """`('/fr', '/old/')` for `/fr/old/` — or `('', path)` when there is none."""
    from django.conf import settings

    codes = {code for code, _ in (getattr(settings, 'LANGUAGES', None) or [])}
    if not codes:
        return '', path
    head, _, rest = path.lstrip('/').partition('/')
    if head in codes:
        return f'/{head}', f'/{rest}' if rest else '/'
    return '', path


def _safe_target(to_path: str, *, prefix: str, query: str) -> str:
    """Refuse anything that would send a visitor off-site.

    Redirect rows are written by staff, by CSV import and by an assistant, and
    an assistant writes what it read somewhere. Restricting the destination to
    a site-relative path is the one check that makes that safe; a merchant who
    genuinely needs an off-site 301 can do it at the edge.
    """
    target = (to_path or '').strip()
    if not target or target.startswith('//') or '://' in target or '\\' in target:
        return ''
    if not target.startswith('/'):
        target = '/' + target
    # Keep the visitor in the language they were browsing.
    if prefix and not target.startswith(f'{prefix}/'):
        target = f'{prefix}{target}'
    if query and '?' not in target:
        target = f'{target}?{query}'
    return target


def _count_hit(path: str) -> None:
    try:
        from plugins.installed.seo.services.redirects import record_redirect_hit

        record_redirect_hit(path)
    except Exception:  # noqa: BLE001, S110 — a counter must never cost the redirect
        pass
