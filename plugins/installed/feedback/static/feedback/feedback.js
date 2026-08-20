/* Feedback modal — collect a message, the page context, recent JS errors and
 * (optionally) a picture of the screen, then open a ticket.
 *
 * Screen capture uses getDisplayMedia, a native browser API, so this ships zero
 * dependencies — html2canvas would mean vendoring ~150KB into a dashboard with
 * no JS build step. The trade is that the browser shows its own picker, and the
 * user can decline. Capture is therefore best-effort in every direction, and
 * the REASON it is missing is sent with the ticket: a report that quietly lost
 * its screenshot is indistinguishable from one where sharing was refused.
 *
 * Errors come from `window.morphClientErrors` — the buffer core's
 * error-capture.js (loaded in <head> on every dashboard page) retains for
 * exactly this. One capture pipeline: the ticket's list matches what
 * /api/errors/client/ ingested, including errors fired before this deferred
 * script ran. CSRF comes from Morph.csrf (dashboard.js, always loaded first).
 */
(function () {
  'use strict';

  var modal = document.getElementById('feedback-modal');
  if (!modal) return;

  var messageEl = document.getElementById('feedback-message');
  var captureEl = document.getElementById('feedback-capture');
  var errorEl = modal.querySelector('[data-feedback-error]');
  var sendBtn = modal.querySelector('[data-feedback-send]');
  var lastFocused = null;

  function open() {
    lastFocused = document.activeElement;
    modal.hidden = false;
    errorEl.style.display = 'none';
    messageEl.focus();
  }

  function close() {
    modal.hidden = true;
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-feedback-open]')) {
      e.preventDefault();
      open();
      return;
    }
    if (e.target.closest('[data-feedback-close]')) {
      e.preventDefault();
      close();
      return;
    }
    if (e.target === modal) close();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !modal.hidden) close();
  });

  /* Grab one frame of the shared surface and downscale it. A raw PNG of a
   * 1440x900 screen is several MB, past DATA_UPLOAD_MAX_MEMORY_SIZE, so cap the
   * width and encode JPEG. Resolves {dataUrl} or {reason}. */
  function captureScreen() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
      return Promise.resolve({ reason: 'unsupported' });
    }
    return navigator.mediaDevices
      .getDisplayMedia({ video: { displaySurface: 'browser' }, audio: false })
      .then(function (stream) {
        var video = document.createElement('video');
        video.srcObject = stream;
        video.muted = true;
        return video.play().then(function () {
          // One frame can be blank if drawn before the pipeline delivers it.
          return new Promise(function (resolve) {
            requestAnimationFrame(function () {
              requestAnimationFrame(function () {
                var vw = video.videoWidth || 0;
                var vh = video.videoHeight || 0;
                if (!vw || !vh) {
                  stream.getTracks().forEach(function (t) { t.stop(); });
                  resolve({ reason: 'failed' });
                  return;
                }
                var scale = Math.min(1, 1600 / vw);
                var canvas = document.createElement('canvas');
                canvas.width = Math.round(vw * scale);
                canvas.height = Math.round(vh * scale);
                canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
                stream.getTracks().forEach(function (t) { t.stop(); });
                resolve({ dataUrl: canvas.toDataURL('image/jpeg', 0.75) });
              });
            });
          });
        });
      })
      .catch(function (err) {
        // NotAllowedError is the user dismissing the browser's own picker.
        return { reason: err && err.name === 'NotAllowedError' ? 'declined' : 'failed' };
      });
  }

  function fail(msg) {
    errorEl.textContent = msg;
    errorEl.style.display = 'block';
  }

  sendBtn.addEventListener('click', function () {
    var message = (messageEl.value || '').trim();
    if (!message) {
      fail('Tell us what happened.');
      messageEl.focus();
      return;
    }
    sendBtn.disabled = true;
    var original = sendBtn.textContent;
    sendBtn.textContent = captureEl.checked ? 'Capturing…' : 'Sending…';

    var shot = captureEl.checked
      ? captureScreen()
      : Promise.resolve({ reason: 'skipped' });

    shot
      .then(function (result) {
        sendBtn.textContent = 'Sending…';
        return fetch('/dashboard/apps/feedback/tickets/submit/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.Morph.csrf() },
          body: JSON.stringify({
            message: message,
            screenshot: result.dataUrl || '',
            screenshot_skipped_reason: result.reason || '',
            client_errors: (window.morphClientErrors || []).slice(-25),
            page_url: window.location.href,
            page_title: document.title,
            viewport: window.innerWidth + 'x' + window.innerHeight,
          }),
        });
      })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (out) {
        if (!out.ok || !out.data.ok) {
          var errs = out.data && out.data.errors ? out.data.errors : {};
          fail(errs.message || errs.__all__ || 'Could not send that. Try again.');
          return;
        }
        messageEl.value = '';
        close();
        if (window.Morph.toast) {
          window.Morph.toast('Thanks — your feedback is now a ticket.');
        }
      })
      .catch(function () {
        fail('Could not send that. Try again.');
      })
      .then(function () {
        sendBtn.disabled = false;
        sendBtn.textContent = original;
      });
  });
})();
