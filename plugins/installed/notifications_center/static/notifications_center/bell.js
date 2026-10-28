/*
 * The topbar bell: notifications_center's surface in the dashboard shell.
 *
 * The shell renders the bell's frame (#notif-bell) and includes this file only
 * while the app is on. The topbar is outside the htmx swap target, so this runs
 * once per full page load.
 *
 *   - The unread count refreshes every 30 s while the tab is visible (and at once
 *     when it becomes visible again); the badge turns red while anything urgent
 *     is unread.
 *   - The list loads each time the dropdown opens, and reloads while it is open
 *     when the inbox changed (a repeat on a stack leaves the count alone, so the
 *     poll compares the inbox revision, not the count).
 *   - A stack shows its count and expands to its earlier occurrences.
 *   - Hover actions: read / unread, snooze until tomorrow, archive, mute the kind.
 */
(function () {
  'use strict';
  const bell = document.getElementById('notif-bell');
  if (!bell || bell.dataset.bound) return;
  bell.dataset.bound = '1';

  const BASE = '/dashboard/notifications/';
  const POLL_MS = 30000;
  const list = bell.querySelector('[data-notif-list]');
  const toggle = bell.querySelector('[data-dropdown-toggle]');
  const menu = bell.querySelector('.dropdown-menu');
  const badge = bell.querySelector('[data-notif-badge]');
  const headCount = bell.querySelector('[data-notif-unread]');
  const markAll = bell.querySelector('[data-notif-mark-all]');
  let counts = {
    unread: parseInt(bell.dataset.unread || '0', 10) || 0,
    urgent: parseInt(bell.dataset.urgent || '0', 10) || 0,
  };
  let rev = null;
  let items = [];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[<>&"']/g, c => (
      { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function csrf() {
    if (window.Morph && typeof window.Morph.csrf === 'function') return window.Morph.csrf();
    return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
  }
  function ago(iso) {
    const t = Date.parse(iso);
    if (!t) return '';
    const s = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (s < 60) return 'just now';
    const m = Math.round(s / 60);
    if (m < 60) return m + ' min ago';
    const h = Math.round(m / 60);
    if (h < 24) return h + ' h ago';
    const d = Math.round(h / 24);
    return d + (d === 1 ? ' day ago' : ' days ago');
  }
  function siteRelative(url) {
    // A path on this site only: browsers read `//x` and `/\x` as another host.
    return typeof url === 'string' && /^\/(?![\/\\])/.test(url);
  }

  // `reload`: refresh an open list when the inbox changed (an action reloads it itself).
  function paintCounts(next, reload) {
    const before = counts.unread;
    const changed = typeof next.rev === 'string' && rev !== null && next.rev !== rev;
    if (typeof next.rev === 'string') rev = next.rev;
    counts = { unread: next.unread || 0, urgent: next.urgent || 0 };
    if (badge) {
      badge.hidden = counts.unread === 0;
      badge.textContent = counts.unread > 99 ? '99+' : String(counts.unread);
      badge.style.background = counts.urgent ? 'var(--danger)' : 'var(--primary)';
      badge.title = counts.urgent ? counts.urgent + ' urgent' : '';
    }
    if (headCount) {
      headCount.hidden = counts.unread === 0;
      headCount.textContent = counts.unread + ' unread';
    }
    if (markAll) markAll.hidden = counts.unread === 0;
    if (counts.unread > before) {
      toggle.classList.remove('notif-ring');
      void toggle.offsetWidth; // restart the animation
      toggle.classList.add('notif-ring');
    }
    if ((changed || counts.unread !== before) && reload !== false && !menu.hidden) load();
  }

  function poll() {
    if (document.hidden) return;
    fetch(BASE + 'api/latest/?counts=1', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data) paintCounts(data); })
      .catch(() => {});
  }

  function renderItem(n) {
    const level = n.level || 'info';
    const stacked = n.count > 1;
    const earlier = (n.occurrences || []).map(o =>
      `<li><span class="notif-b-time">${esc(ago(o.at))}</span> ${esc(o.title)}${o.body ? ' — ' + esc(o.body).slice(0, 80) : ''}</li>`
    ).join('');
    const more = n.count - 1 - (n.occurrences || []).length;
    return `
      <div class="notif-b-item level-${esc(level)}${n.read ? '' : ' is-unread'}" data-id="${esc(n.id)}" data-url="${esc(n.action_url || '')}" data-kind-label="${esc(n.kind_label)}" role="link" tabindex="0">
        <span class="notif-b-icon"><i data-lucide="${esc(n.icon || 'bell')}" class="h-3.5 w-3.5"></i></span>
        <div class="notif-b-main">
          <p class="notif-b-title">${esc(n.title)}${stacked ? ` <span class="pill pill-neutral pill-xs">×${esc(n.count)}</span>` : ''}${level === 'urgent' ? ' <span class="pill pill-danger pill-xs">Urgent</span>' : ''}</p>
          ${n.body ? `<p class="notif-b-body">${esc(n.body).slice(0, 110)}</p>` : ''}
          <p class="notif-b-meta">${esc(n.kind_label)} · ${esc(ago(n.last_at))}${stacked ? ` · <button type="button" class="notif-b-link" data-expand>Show ${esc(n.count - 1)} earlier</button>` : ''}</p>
          ${stacked ? `<ol class="notif-b-stack" hidden>${earlier}${more > 0 ? `<li>and ${esc(more)} more</li>` : ''}</ol>` : ''}
        </div>
        <div class="notif-b-actions">
          ${n.read
            ? '<button type="button" data-act="unread" title="Mark unread" aria-label="Mark unread"><i data-lucide="mail" class="h-3.5 w-3.5"></i></button>'
            : '<button type="button" data-act="read" title="Mark read" aria-label="Mark read"><i data-lucide="check" class="h-3.5 w-3.5"></i></button>'}
          <button type="button" data-act="snooze" data-until="tomorrow" title="Snooze until tomorrow" aria-label="Snooze until tomorrow"><i data-lucide="clock" class="h-3.5 w-3.5"></i></button>
          <button type="button" data-act="archive" title="Archive" aria-label="Archive"><i data-lucide="archive" class="h-3.5 w-3.5"></i></button>
          <button type="button" data-act="mute" title="Stop getting this kind" aria-label="Stop getting this kind"><i data-lucide="eye-off" class="h-3.5 w-3.5"></i></button>
        </div>
      </div>`;
  }

  function render() {
    if (!items.length) {
      list.innerHTML = '<p class="notif-b-empty">You\'re all caught up.</p>';
      return;
    }
    list.innerHTML = items.map(renderItem).join('');
    if (window.lucide && window.lucide.createIcons) window.lucide.createIcons(list);
  }

  function load() {
    fetch(BASE + 'api/latest/', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(data => {
        items = data.notifications || [];
        render();
        paintCounts(data, false);
      })
      .catch(() => {
        list.innerHTML = '<p class="notif-b-empty" style="color:var(--danger);">Couldn\'t load notifications.</p>';
      });
  }

  function act(id, action, until) {
    const body = new URLSearchParams({ action: action });
    if (until) body.set('until', until);
    return fetch(BASE + encodeURIComponent(id) + '/act/', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrf(),
      },
      body: body,
    })
      .then(r => r.json().catch(() => ({ ok: false, message: 'Something went wrong.' })))
      .then(data => {
        if (typeof data.unread === 'number') paintCounts(data, false);
        return data;
      });
  }

  function toast(message, level) {
    if (message && window.Morph && typeof window.Morph.toast === 'function') window.Morph.toast(message, level);
  }

  list.addEventListener('click', function (e) {
    // Keep the dropdown open: the re-render detaches the clicked button, and the
    // shell's outside-click handler would read that as a click outside.
    e.stopPropagation();
    const row = e.target.closest('.notif-b-item');
    if (!row) return;
    const id = row.dataset.id;
    if (e.target.closest('[data-expand]')) {
      const stack = row.querySelector('.notif-b-stack');
      if (stack) stack.hidden = !stack.hidden;
      return;
    }
    const btn = e.target.closest('[data-act]');
    if (btn) {
      const action = btn.dataset.act;
      const run = () => act(id, action, btn.dataset.until).then(data => {
        toast(data.message, data.ok ? 'success' : 'error');
        if (data.ok) load();
      });
      if (action === 'mute') {
        const kind = row.dataset.kindLabel || 'these';
        const ask = window.Morph && window.Morph.confirm
          ? window.Morph.confirm({ title: 'Stop getting these?', message: 'You will no longer get “' + kind + '” notifications. You can turn them back on in notification settings.', cta: 'Stop getting them' })
          : Promise.resolve(window.confirm('Stop getting “' + kind + '” notifications?'));
        ask.then(yes => { if (yes) run(); });
      } else {
        run();
      }
      return;
    }
    // Opening a notification reads it, then goes where it points.
    const url = row.dataset.url;
    const wasUnread = row.classList.contains('is-unread');
    const go = () => { if (siteRelative(url)) window.location.href = url; };
    if (wasUnread) act(id, 'read').finally(go); else go();
  });
  list.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.classList.contains('notif-b-item')) e.target.click();
  });

  toggle.addEventListener('click', () => {
    // Read the state once every click handler ran, the shell's toggle included.
    window.setTimeout(() => { if (!menu.hidden) load(); }, 0);
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  // An action on the list page swaps the page under the topbar: recount at once.
  document.body.addEventListener('htmx:afterSwap', poll);
  window.setInterval(poll, POLL_MS);
})();
