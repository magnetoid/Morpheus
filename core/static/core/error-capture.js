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
 * Detailed capture (the switch on the dashboard's error log; the server marks
 * this script's tag with data-detailed="1") also reports, as warnings: an
 * image, script or stylesheet that failed to load, console.error calls, and a
 * fetch or XHR request answered with a 5xx or lost to the network. Those
 * payloads carry `detail: true`; the server drops them once the switch is off.
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
  var SELF = document.currentScript;
  var DETAILED = !!(SELF && SELF.getAttribute('data-detailed') === '1');
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
    // Resource-load errors (img/script src 404) arrive here with no `.error`
    // and a `target` that is an element: reported only in detailed capture.
    var t = ev.target;
    if (!ev.error && !ev.message && t && t !== window && t.tagName) {
      if (!DETAILED) return;
      var url = t.currentSrc || t.src || t.href || '';
      if (url) {
        ship({
          message: 'Failed to load ' + t.tagName.toLowerCase() + ': ' + url,
          name: 'ResourceError', source: url, lineno: 0, colno: 0, stack: '',
          level: 'warning', detail: true,
        });
      }
      return;
    }
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
    // The browser's own View Transition abort (a navigation interrupted a
    // transition in flight) is not an error; the server drops it too.
    if (name === 'InvalidStateError' && msg.indexOf('Transition was aborted') === 0) return;
    if (name === 'AbortError' && msg.indexOf('Skipping view transition') === 0) return;  // Safari
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
        if (DETAILED && level === 'error') {
          ship({
            message: parts.join(' ').slice(0, 500), name: 'ConsoleError',
            source: '', lineno: 0, colno: 0, stack: '', level: 'warning', detail: true,
          });
        }
      } catch (e) { /* never break a console call */ }
      return original.apply(console, arguments);
    };
  });

  // ── Failed requests (detailed capture) ────────────────────────────────────
  // A 5xx or a lost connection on fetch or XHR (htmx uses XHR). Aborted
  // requests are a navigation, not a failure; the capture endpoint is skipped.
  if (!DETAILED) return;

  function shipRequest(method, url, status) {
    var where = String(url || '').split('?')[0];
    if (!where || where.indexOf(ENDPOINT) !== -1) return;
    ship({
      message: method + ' ' + where + ' failed: ' + (status ? 'HTTP ' + status : 'network error'),
      name: 'RequestError', source: where, lineno: status || 0, colno: 0, stack: '',
      level: 'warning', detail: true,
    });
  }

  if (window.fetch) {
    var originalFetch = window.fetch;
    window.fetch = function (input, init) {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      var method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
      return originalFetch.apply(this, arguments).then(function (res) {
        if (res && res.status >= 500) shipRequest(method, url, res.status);
        return res;
      }, function (err) {
        if (!err || err.name !== 'AbortError') shipRequest(method, url, 0);
        throw err;
      });
    };
  }

  if (window.XMLHttpRequest) {
    var xhrOpen = XMLHttpRequest.prototype.open;
    var xhrSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__morphRequest = [String(method || 'GET').toUpperCase(), String(url || '')];
      return xhrOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
      var xhr = this;
      try {
        xhr.addEventListener('abort', function () { xhr.__morphAborted = true; });
        xhr.addEventListener('loadend', function () {
          var r = xhr.__morphRequest || ['GET', ''];
          if (xhr.status >= 500 || (xhr.status === 0 && !xhr.__morphAborted)) {
            shipRequest(r[0], r[1], xhr.status);
          }
        });
      } catch (e) { /* never break a request */ }
      return xhrSend.apply(this, arguments);
    };
  }
})();
