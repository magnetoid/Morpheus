/* The travel store's search bar (booking_marketplace/_search.html).
 *
 * Suggestions while a visitor types (GET data-suggest-url?q=, 150 ms after the last key),
 * the date's label, the clear buttons and, on a phone, the full-screen panel the summary
 * line opens. The form works without this file. Text from the server is set with
 * textContent and a link must be a path on this site: nothing here is parsed as HTML.
 */
(function () {
  'use strict';

  var DEBOUNCE_MS = 150;
  var MIN_CHARS = 2;
  var MAX_CHARS = 80;
  var PHONE = window.matchMedia('(max-width: 767px)');

  function sitePath(url) {
    return typeof url === 'string' && url.charAt(0) === '/' && url.charAt(1) !== '/' ? url : '';
  }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function initWhat(root) {
    var input = root.querySelector('[data-sb-q]');
    var clear = root.querySelector('[data-sb-clear-q]');
    if (!input || !clear) return;
    function sync() { clear.hidden = !input.value; }
    input.addEventListener('input', sync);
    clear.addEventListener('click', function () {
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.focus();
    });
    sync();
  }

  function initWhen(root) {
    var input = root.querySelector('[data-sb-date]');
    var text = root.querySelector('[data-sb-date-text]');
    var clear = root.querySelector('[data-sb-clear-date]');
    if (!input || !text) return;
    var anyDate = text.getAttribute('data-any') || '';
    var format = null;
    try {
      format = new Intl.DateTimeFormat(root.getAttribute('data-date-locale') || undefined, {
        weekday: 'short', day: 'numeric', month: 'short'
      });
    } catch (error) {
      format = null;
    }
    function label() {
      var parts = input.value.split('-');
      if (parts.length !== 3) return anyDate;
      var day = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      return format && !isNaN(day.getTime()) ? format.format(day) : input.value;
    }
    function sync() {
      text.textContent = label();
      text.classList.toggle('is-set', Boolean(input.value));
      if (clear) clear.hidden = !input.value;
    }
    input.addEventListener('change', sync);
    input.addEventListener('click', function () {
      if (typeof input.showPicker === 'function') {
        try { input.showPicker(); } catch (error) { /* the native control still opens */ }
      }
    });
    if (clear) {
      clear.addEventListener('click', function () {
        input.value = '';
        sync();
        input.focus();
      });
    }
    sync();
  }

  function initSuggest(root) {
    var input = root.querySelector('[data-sb-q]');
    var list = root.querySelector('[data-sb-list]');
    var url = sitePath(root.getAttribute('data-suggest-url'));
    if (!input || !list || !url) return;
    var groups = [
      ['experiences', root.getAttribute('data-label-experiences') || ''],
      ['places', root.getAttribute('data-label-places') || ''],
      ['categories', root.getAttribute('data-label-categories') || '']
    ];
    var answers = new Map();
    var timer = 0;
    var pending = null;
    var options = [];
    var active = -1;

    function close() {
      list.hidden = true;
      list.textContent = '';
      options = [];
      active = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    }

    function select(index) {
      if (options[active]) options[active].setAttribute('aria-selected', 'false');
      active = index;
      var option = options[active];
      if (!option) {
        input.removeAttribute('aria-activedescendant');
        return;
      }
      option.setAttribute('aria-selected', 'true');
      input.setAttribute('aria-activedescendant', option.id);
      option.scrollIntoView({ block: 'nearest' });
    }

    function optionFor(item, group) {
      var href = sitePath(item && item.url);
      if (!href || !item.name) return null;
      var node = make('div', 'mx-sb__opt');
      node.id = list.id + '-' + options.length;
      node.setAttribute('role', 'option');
      node.setAttribute('aria-selected', 'false');
      node.setAttribute('data-href', href);
      if (group === 'experiences') {
        var thumb = make('span', 'mx-sb__thumb');
        var image = String(item.image || '');
        var src = sitePath(image) || (/^https:\/\//.test(image) ? image : '');
        if (src) {
          var img = make('img');
          img.src = src;
          img.alt = '';
          img.loading = 'lazy';
          thumb.appendChild(img);
        }
        node.appendChild(thumb);
      }
      var body = make('span', 'mx-sb__opt-body');
      body.appendChild(make('span', 'mx-sb__opt-name', String(item.name)));
      var meta = '';
      if (group === 'experiences') meta = [item.location, item.price].filter(Boolean).join(' · ');
      if (group === 'categories' && item.count) meta = String(item.count);
      if (meta) body.appendChild(make('span', 'mx-sb__opt-meta', meta));
      node.appendChild(body);
      options.push(node);
      return node;
    }

    function render(data) {
      list.textContent = '';
      options = [];
      active = -1;
      input.removeAttribute('aria-activedescendant');
      groups.forEach(function (group) {
        var items = (data && data[group[0]]) || [];
        if (!items.length) return;
        var box = make('div', 'mx-sb__group');
        box.setAttribute('role', 'group');
        var title = make('div', 'mx-sb__group-label', group[1]);
        title.id = list.id + '-' + group[0];
        box.setAttribute('aria-labelledby', title.id);
        box.appendChild(title);
        items.forEach(function (item) {
          var node = optionFor(item, group[0]);
          if (node) box.appendChild(node);
        });
        list.appendChild(box);
      });
      if (!options.length) {
        close();
        return;
      }
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }

    function ask(q) {
      if (answers.has(q)) {
        render(answers.get(q));
        return;
      }
      if (pending) pending.abort();
      pending = typeof AbortController === 'function' ? new AbortController() : null;
      fetch(url + '?q=' + encodeURIComponent(q), {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        signal: pending ? pending.signal : undefined
      })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (data) {
          if (!data) return;
          answers.set(q, data);
          if (input.value.trim() === q && document.activeElement === input) render(data);
        })
        .catch(function () { /* aborted or offline: the form still submits */ });
    }

    input.addEventListener('input', function () {
      window.clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < MIN_CHARS || q.length > MAX_CHARS) {
        close();
        return;
      }
      timer = window.setTimeout(function () { ask(q); }, DEBOUNCE_MS);
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        if (list.hidden || !options.length) return;
        event.preventDefault();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        if (active < 0) select(step > 0 ? 0 : options.length - 1);
        else select((active + step + options.length) % options.length);
      } else if (event.key === 'Enter' && !list.hidden && options[active]) {
        event.preventDefault();
        window.location.assign(options[active].getAttribute('data-href'));
      } else if (event.key === 'Escape' && !list.hidden) {
        event.preventDefault();
        close();
      }
    });
    input.addEventListener('blur', close);
    list.addEventListener('mousedown', function (event) { event.preventDefault(); });
    list.addEventListener('click', function (event) {
      var node = event.target.closest('[role="option"]');
      if (node) window.location.assign(node.getAttribute('data-href'));
    });
  }

  function initPanel(root) {
    var open = root.querySelector('[data-sb-open]');
    var form = root.querySelector('[data-sb-form]');
    var shut = root.querySelector('[data-sb-close]');
    if (!open || !form) return;
    var title = form.querySelector('.mx-sb__panel-title');

    function show() {
      root.classList.add('is-open');
      open.setAttribute('aria-expanded', 'true');
      form.setAttribute('role', 'dialog');
      form.setAttribute('aria-modal', 'true');
      if (title) form.setAttribute('aria-labelledby', title.id);
      document.documentElement.classList.add('mx-sb-locked');
      var first = form.querySelector('[data-sb-q]');
      if (first) first.focus();
    }

    function hide(restoreFocus) {
      if (!root.classList.contains('is-open')) return;
      root.classList.remove('is-open');
      open.setAttribute('aria-expanded', 'false');
      form.setAttribute('role', 'search');
      form.removeAttribute('aria-modal');
      form.removeAttribute('aria-labelledby');
      document.documentElement.classList.remove('mx-sb-locked');
      if (restoreFocus) open.focus();
    }

    function focusable() {
      return Array.prototype.filter.call(form.querySelectorAll('button, input, select'), function (node) {
        return !node.disabled && !node.hidden && node.type !== 'hidden' && node.offsetParent !== null;
      });
    }

    open.addEventListener('click', show);
    if (shut) shut.addEventListener('click', function () { hide(true); });
    form.addEventListener('keydown', function (event) {
      if (!root.classList.contains('is-open')) return;
      if (event.key === 'Escape' && !event.defaultPrevented) {
        hide(true);
        return;
      }
      if (event.key !== 'Tab') return;
      var nodes = focusable();
      if (!nodes.length) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    // Turned to a wider screen with the panel open: the page must scroll again.
    var widened = function (query) { if (!query.matches) hide(false); };
    if (PHONE.addEventListener) PHONE.addEventListener('change', widened);
  }

  function init(root) {
    if (root.hasAttribute('data-enhanced')) return;
    root.setAttribute('data-enhanced', '');
    initWhat(root);
    initWhen(root);
    initSuggest(root);
    initPanel(root);
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-mx-search]'), init);
})();
