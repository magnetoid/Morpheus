/* error-capture.js — ship browser errors to /api/errors/client/.
 *
 * Installed once via base templates. Hooks:
 *   window.onerror           — synchronous script errors
 *   unhandledrejection       — promise rejections
 *   console.*      (wrapped) — buffered locally, never shipped
 *
 * Dedup: a 5-second rolling window swallows identical (message+source+line)
 * tuples so a fast-firing loop can't DDoS the ingest. Per-page cap of 25.
 *
 * Read surfaces (one owner of "what happened in this browser session" —
 * consumers read these, they do NOT install their own listeners/wrappers):
 *   `window.morphClientErrors` — the shipped error payloads (same dedup/cap).
 *   `window.morphConsoleLog`   — the last 50 console lines (log/info/warn/
 *                                error/debug), message-only, 500 chars each.
 * The feedback modal pins both to tickets, including everything fired before
 * its own deferred script loaded — this file runs in <head>.
 */
(function () {
  if (window.__morphErrorCapture) return;  // idempotent
  window.__morphErrorCapture = true;

  var ENDPOINT = '/api/errors/client/';
  var MAX_PER_PAGE = 25;
  var DEDUP_WINDOW_MS = 5000;

  var sent = 0;
  var recent = {};
  var buffer = (window.morphClientErrors = []);

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
    // Drop dedup keys older than 2x the window. Without this the dict
    // accumulates a key per distinct (msg|src:line) tuple across the
    // page lifetime — a tab open all day grows it into hundreds of KB.
    for (var k in recent) {
      if (now - recent[k] > DEDUP_WINDOW_MS * 2) delete recent[k];
    }
    if (recent[key] && now - recent[key] < DEDUP_WINDOW_MS) return;
    recent[key] = now;
    sent++;

    payload.page = location.href;
    payload.browser = browserTag();
    payload.ts = new Date().toISOString();

    buffer.push(payload);
    if (buffer.length > MAX_PER_PAGE) buffer.shift();

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

  // ── Console ring buffer ───────────────────────────────────────────────────
  // The last N console lines, buffered for local consumers (feedback tickets)
  // and NEVER shipped — a shop's console chatter is diagnostic context, not an
  // error stream. Wrapping delegates to the original, so DevTools output is
  // untouched and a throwing argument can't break app code mid-log.
  var CONSOLE_MAX = 50;
  var consoleBuf = (window.morphConsoleLog = []);

  function stringifyArg(a) {
    if (typeof a === 'string') return a;
    if (a instanceof Error) return a.name + ': ' + a.message;
    try {
      return JSON.stringify(a);
    } catch (e) {
      return String(a);
    }
  }

  ['log', 'info', 'warn', 'error', 'debug'].forEach(function (level) {
    var original = console[level];
    if (typeof original !== 'function') return;
    console[level] = function () {
      try {
        var parts = [];
        for (var i = 0; i < arguments.length; i++) parts.push(stringifyArg(arguments[i]));
        consoleBuf.push({
          level: level,
          message: parts.join(' ').slice(0, 500),
          ts: new Date().toISOString(),
        });
        if (consoleBuf.length > CONSOLE_MAX) consoleBuf.shift();
      } catch (e) { /* never break a console call */ }
      return original.apply(console, arguments);
    };
  });
})();
