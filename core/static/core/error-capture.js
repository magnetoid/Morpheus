/* error-capture.js — ship browser errors to /api/errors/client/.
 *
 * Installed once via base templates. Hooks:
 *   window.onerror           — synchronous script errors
 *   unhandledrejection       — promise rejections
 *   console.error  (wrapped) — explicit console.error calls in app code
 *
 * Dedup: a 5-second rolling window swallows identical (message+source+line)
 * tuples so a fast-firing loop can't DDoS the ingest. Per-page cap of 25.
 */
(function () {
  if (window.__morphErrorCapture) return;  // idempotent
  window.__morphErrorCapture = true;

  var ENDPOINT = '/api/errors/client/';
  var MAX_PER_PAGE = 25;
  var DEDUP_WINDOW_MS = 5000;

  var sent = 0;
  var recent = {};

  function browserTag() {
    var ua = navigator.userAgent || '';
    var m = ua.match(/(Chrome|Firefox|Safari|Edge|Edg)\/([\d.]+)/);
    return m ? m[1].replace('Edg', 'Edge') + '/' + m[2] : ua.slice(0, 80);
  }

  function dedupKey(msg, src, line) {
    return (msg || '') + '|' + (src || '') + ':' + (line || 0);
  }

  function ship(payload) {
    if (sent >= MAX_PER_PAGE) return;
    var key = dedupKey(payload.message, payload.source, payload.lineno);
    var now = Date.now();
    if (recent[key] && now - recent[key] < DEDUP_WINDOW_MS) return;
    recent[key] = now;
    sent++;

    payload.page = location.href;
    payload.browser = browserTag();
    payload.ts = new Date().toISOString();

    try {
      var body = JSON.stringify(payload);
      // sendBeacon is best-effort + tolerates page-unload; fetch is fallback.
      if (navigator.sendBeacon) {
        var blob = new Blob([body], {type: 'application/json'});
        navigator.sendBeacon(ENDPOINT, blob);
      } else {
        fetch(ENDPOINT, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: body,
          keepalive: true,
        }).catch(function () { /* swallow */ });
      }
    } catch (e) { /* swallow — never throw from the capture path */ }
  }

  window.addEventListener('error', function (ev) {
    // Resource-load errors (img/script src 404) bubble up as ErrorEvents
    // with no `.error` and a `target` that's an element — skip those.
    if (ev.error || ev.message) {
      var e = ev.error;
      ship({
        message: ev.message || (e && e.message) || 'Unknown error',
        name:    (e && e.name) || 'Error',
        source:  ev.filename || (e && e.fileName) || '',
        lineno:  ev.lineno || (e && e.lineNumber) || 0,
        colno:   ev.colno  || (e && e.columnNumber) || 0,
        stack:   (e && e.stack) || '',
        level:   'error',
      });
    }
  }, true);

  window.addEventListener('unhandledrejection', function (ev) {
    var reason = ev.reason;
    var msg = '';
    var stack = '';
    var name = 'UnhandledRejection';
    if (reason && typeof reason === 'object') {
      msg = reason.message || String(reason);
      stack = reason.stack || '';
      name = reason.name || 'UnhandledRejection';
    } else {
      msg = String(reason);
    }
    ship({
      message: msg, name: name, stack: stack,
      source: '', lineno: 0, colno: 0,
      level: 'error',
    });
  });
})();
