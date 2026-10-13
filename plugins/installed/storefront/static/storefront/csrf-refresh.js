/* Forms on edge-cached storefront pages.
 *
 * A page the CDN caches carries the CSRF token of whoever filled the cache and
 * sets no cookie, so a visitor's form posts answered 403 (Montenegro's cookie
 * banner, 2026-10-13). On load this makes sure the visitor has their own CSRF
 * cookie (from the never-cached /csrf/) and writes its value into every form's
 * token; Django accepts the cookie's value as the token. A form submitted before
 * that finishes waits for it, then submits again.
 */
(function () {
  'use strict';

  function cookieToken() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  var pending = null;
  function ensureToken() {
    var token = cookieToken();
    if (token) return Promise.resolve(token);
    if (!pending) {
      // The query keeps a CDN rule that caches everything from caching this too.
      pending = fetch('/csrf/?t=' + Date.now(), { credentials: 'same-origin', cache: 'no-store' })
        .then(function (r) { return r.ok ? r.json() : {}; })
        .then(function (d) { return cookieToken() || (d && d.token) || ''; })
        .catch(function () { return ''; });
    }
    return pending;
  }

  function apply(token) {
    if (!token) return;
    var inputs = document.querySelectorAll('input[name="csrfmiddlewaretoken"]');
    for (var i = 0; i < inputs.length; i++) inputs[i].value = token;
  }

  function postsHere(form) {
    if ((form.getAttribute('method') || '').toLowerCase() !== 'post') return false;
    if (!form.querySelector('input[name="csrfmiddlewaretoken"]')) return false;
    try {
      return new URL(form.getAttribute('action') || location.href, location.href).origin === location.origin;
    } catch (e) {
      return false;
    }
  }

  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!(form instanceof HTMLFormElement) || !postsHere(form)) return;
    var token = cookieToken();
    if (token) {
      apply(token);
      return;
    }
    ev.preventDefault();
    ev.stopImmediatePropagation();
    var submitter = ev.submitter && ev.submitter.form === form ? ev.submitter : undefined;
    ensureToken().then(function (t) {
      apply(t);
      if (form.requestSubmit) form.requestSubmit(submitter);
      else form.submit();
    });
  }, true);

  function init() { ensureToken().then(apply); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
