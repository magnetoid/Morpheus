/**
 * Morpheus dashboard — shared client utilities.
 *
 * Exposes a single `window.Morph` namespace so templates can opt into
 * richer behaviours without importing anything. Three things live here
 * for now:
 *
 *   Morph.confirm(opts) → Promise<bool>
 *     In-page confirmation modal that replaces window.confirm(). Reads
 *     `data-confirm`, `data-confirm-title`, `data-confirm-cta`,
 *     `data-confirm-danger` from the element that triggered it.
 *
 *   Morph.bulk.init(rootEl)
 *     Wires bulk selection on a list page: a "select all" checkbox in
 *     the table head, row checkboxes (with `form="bulk-form"`), and a
 *     sticky "N selected" action bar that hides when nothing is
 *     selected.
 *
 *   Morph.toast(message, level='info')
 *     Stub here — pushed into a queue that commit 2 drains into a real
 *     fixed-position toast container. Keeps API stable so callers don't
 *     change.
 */
(function () {
  'use strict';
  const Morph = window.Morph || (window.Morph = {});

  // ── Confirm modal ─────────────────────────────────────────────────────
  Morph.confirm = function (opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      const root = document.getElementById('morph-confirm-modal');
      if (!root) {
        // Modal not rendered yet → fall back to native so the action
        // is never silently lost.
        resolve(window.confirm(opts.message || 'Are you sure?'));
        return;
      }
      root.querySelector('[data-mc-title]').textContent = opts.title || 'Are you sure?';
      root.querySelector('[data-mc-message]').textContent = opts.message || '';
      const okBtn = root.querySelector('[data-mc-confirm]');
      okBtn.textContent = opts.cta || 'Confirm';
      okBtn.classList.toggle('btn-danger', !!opts.danger);
      okBtn.classList.toggle('btn-primary', !opts.danger);

      function close(answer) {
        root.hidden = true;
        document.body.style.overflow = '';
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        backdrop.removeEventListener('click', onCancel);
        document.removeEventListener('keydown', onKey);
        resolve(answer);
      }
      const cancelBtn = root.querySelector('[data-mc-cancel]');
      const backdrop = root.querySelector('[data-mc-backdrop]');
      function onOk() { close(true); }
      function onCancel() { close(false); }
      function onKey(e) { if (e.key === 'Escape') close(false); }
      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      backdrop.addEventListener('click', onCancel);
      document.addEventListener('keydown', onKey);

      root.hidden = false;
      document.body.style.overflow = 'hidden';
      okBtn.focus();
    });
  };

  // Intercept any form / button with `data-confirm="…"` and route through
  // the modal instead of letting window.confirm fire.
  function attachConfirmDelegation() {
    document.body.addEventListener('submit', function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (!form.hasAttribute('data-confirm')) return;
      if (form.dataset.morphConfirmed === '1') return;  // already approved → let it submit
      e.preventDefault();
      Morph.confirm({
        title: form.dataset.confirmTitle || undefined,
        message: form.getAttribute('data-confirm'),
        cta: form.dataset.confirmCta || 'Confirm',
        danger: form.hasAttribute('data-confirm-danger'),
      }).then(function (ok) {
        if (!ok) return;
        form.dataset.morphConfirmed = '1';
        form.submit();
      });
    }, true);
  }

  // ── Bulk-select action bar ────────────────────────────────────────────
  Morph.bulk = {
    init: function (root) {
      root = root || document;
      const bar = root.querySelector('[data-bulk-bar]');
      if (!bar) return;
      const all = root.querySelector('[data-bulk-all]');
      const rows = Array.from(root.querySelectorAll('[data-bulk-row]'));
      const counter = bar.querySelector('[data-bulk-count]');
      const actionButtons = Array.from(bar.querySelectorAll('button[data-bulk-action]'));
      const entitySingular = bar.dataset.bulkEntity || 'item';
      const entityPlural = bar.dataset.bulkEntityPlural || (entitySingular + 's');
      const formId = bar.dataset.bulkFormId || 'bulk-form';
      const form = document.getElementById(formId);

      function update() {
        const selected = rows.filter(function (r) { return r.checked; }).length;
        bar.hidden = selected === 0;
        if (counter) {
          counter.textContent = selected + ' ' + (selected === 1 ? entitySingular : entityPlural) + ' selected';
        }
        actionButtons.forEach(function (b) { b.disabled = selected === 0; });
        if (all) {
          all.checked = selected > 0 && selected === rows.length;
          all.indeterminate = selected > 0 && selected < rows.length;
        }
      }
      rows.forEach(function (r) { r.addEventListener('change', update); });
      if (all) {
        all.addEventListener('change', function () {
          rows.forEach(function (r) { r.checked = all.checked; });
          update();
        });
      }
      actionButtons.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.preventDefault();
          if (!form) return;
          const action = btn.dataset.bulkAction;
          const danger = btn.hasAttribute('data-bulk-danger');
          const verb = btn.textContent.trim().toLowerCase();
          const selected = rows.filter(function (r) { return r.checked; });
          Morph.confirm({
            title: btn.dataset.bulkConfirmTitle || ('Apply to ' + selected.length + ' ' + (selected.length === 1 ? entitySingular : entityPlural) + '?'),
            message: btn.dataset.bulkConfirmMessage || ('You\'re about to ' + verb + ' ' + selected.length + ' ' + (selected.length === 1 ? entitySingular : entityPlural) + '.'),
            cta: btn.dataset.bulkConfirmCta || (danger ? verb : 'Apply'),
            danger: danger,
          }).then(function (ok) {
            if (!ok) return;
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'action';
            hidden.value = action;
            form.appendChild(hidden);
            form.submit();
          });
        });
      });
      update();
    },
  };

  // ── Toasts ────────────────────────────────────────────────────────────
  Morph._toastQueue = Morph._toastQueue || [];
  Morph.toast = function (message, level) {
    const entry = { message: String(message || ''), level: level || 'info' };
    const container = document.getElementById('morph-toast-container');
    if (!container) {
      // Container not in DOM yet — buffer until `_renderQueued` drains.
      Morph._toastQueue.push(entry);
      return;
    }
    const el = document.createElement('div');
    el.className = 'morph-toast morph-toast-' + entry.level;
    const text = document.createElement('div');
    text.style.flex = '1';
    text.textContent = entry.message;
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'morph-toast-close';
    close.setAttribute('aria-label', 'Dismiss');
    close.innerHTML = '&times;';
    el.appendChild(text);
    el.appendChild(close);
    container.appendChild(el);
    // Force reflow so the transition fires.
    void el.offsetWidth;
    el.classList.add('is-shown');
    function dismiss() {
      el.classList.remove('is-shown');
      setTimeout(function () { el.remove(); }, 220);
    }
    close.addEventListener('click', dismiss);
    setTimeout(dismiss, 4200);
  };

  // Drain any messages buffered before the renderer was ready.
  function drainToasts() {
    if (!document.getElementById('morph-toast-container')) return;
    const buffered = Morph._toastQueue.splice(0);
    buffered.forEach(function (m) { Morph.toast(m.message, m.level); });
  }

  // ── Cmd+K command palette ─────────────────────────────────────────────
  Morph.palette = {
    open: function () {
      const root = document.getElementById('morph-palette');
      if (!root) return;
      root.hidden = false;
      document.body.style.overflow = 'hidden';
      const input = root.querySelector('#mp-input');
      input.value = '';
      this._render([]);
      this._fetch('');
      input.focus();
    },
    close: function () {
      const root = document.getElementById('morph-palette');
      if (!root) return;
      root.hidden = true;
      document.body.style.overflow = '';
    },
    toggle: function () {
      const root = document.getElementById('morph-palette');
      if (!root) return;
      if (root.hidden) this.open(); else this.close();
    },
    _activeIdx: 0,
    _hits: [],
    _debounce: null,
    _fetch: function (q) {
      clearTimeout(this._debounce);
      const self = this;
      this._debounce = setTimeout(function () {
        fetch('/dashboard/palette/search/?q=' + encodeURIComponent(q), {
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) { self._render(data.hits || []); })
          .catch(function () { self._render([]); });
      }, 120);
    },
    _render: function (hits) {
      const root = document.getElementById('morph-palette');
      if (!root) return;
      this._hits = hits;
      this._activeIdx = 0;
      const out = root.querySelector('#mp-results');
      if (hits.length === 0) {
        out.innerHTML = '<div class="mp-empty">No matches.</div>';
        return;
      }
      // Group by kind; nav targets first.
      const order = ['nav', 'order', 'product', 'customer'];
      const titles = { nav: 'Go to', order: 'Orders', product: 'Products', customer: 'Customers' };
      const groups = {};
      hits.forEach(function (h) { (groups[h.kind] || (groups[h.kind] = [])).push(h); });
      let html = '';
      let flatIdx = 0;
      order.forEach(function (k) {
        if (!groups[k]) return;
        html += '<div class="mp-section-title">' + (titles[k] || k) + '</div>';
        groups[k].forEach(function (h) {
          html += (
            '<div class="mp-row" data-kind="' + h.kind + '" data-idx="' + flatIdx + '" data-url="' + h.url + '">'
            + '<span class="mp-icon-wrap"><i data-lucide="' + (h.icon || 'circle') + '" class="h-3.5 w-3.5"></i></span>'
            + '<div style="flex:1; min-width:0;">'
            + '<div class="mp-label">' + escapeHtml(h.label) + '</div>'
            + (h.hint ? '<div class="mp-hint">' + escapeHtml(h.hint) + '</div>' : '')
            + '</div></div>'
          );
          flatIdx++;
        });
      });
      out.innerHTML = html;
      if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
      this._highlight(0);
      const self = this;
      out.querySelectorAll('.mp-row').forEach(function (row) {
        row.addEventListener('mouseenter', function () { self._highlight(parseInt(row.dataset.idx)); });
        row.addEventListener('click', function () {
          window.location.href = row.dataset.url;
        });
      });
    },
    _highlight: function (idx) {
      const root = document.getElementById('morph-palette');
      if (!root) return;
      this._activeIdx = idx;
      const rows = root.querySelectorAll('.mp-row');
      rows.forEach(function (r, i) { r.classList.toggle('is-active', i === idx); });
      const active = rows[idx];
      if (active) active.scrollIntoView({ block: 'nearest' });
    },
    _step: function (delta) {
      if (!this._hits.length) return;
      let next = this._activeIdx + delta;
      if (next < 0) next = this._hits.length - 1;
      if (next >= this._hits.length) next = 0;
      this._highlight(next);
    },
    _activate: function () {
      const root = document.getElementById('morph-palette');
      if (!root) return;
      const rows = root.querySelectorAll('.mp-row');
      const active = rows[this._activeIdx];
      if (active) window.location.href = active.dataset.url;
    },
  };

  function escapeHtml(s) {
    return String(s).replace(/[<>&"]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c];
    });
  }

  function attachPalette() {
    const root = document.getElementById('morph-palette');
    if (!root) return;
    const input = root.querySelector('#mp-input');
    input.addEventListener('input', function () {
      Morph.palette._fetch(input.value);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); Morph.palette._step(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); Morph.palette._step(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); Morph.palette._activate(); }
      else if (e.key === 'Escape') { e.preventDefault(); Morph.palette.close(); }
    });
    root.querySelector('[data-mp-backdrop]').addEventListener('click', function () {
      Morph.palette.close();
    });
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        Morph.palette.toggle();
      }
    });
    const opener = document.getElementById('palette-open');
    if (opener) opener.addEventListener('click', function () { Morph.palette.open(); });
  }

  // ── Bootstrap on DOMContentLoaded ─────────────────────────────────────
  function boot() {
    attachConfirmDelegation();
    Morph.bulk.init();
    drainToasts();
    attachPalette();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
