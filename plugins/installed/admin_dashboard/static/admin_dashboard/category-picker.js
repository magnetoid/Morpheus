/* Category picker for the product editor (owner's ask, 2026-10-11).
 *
 * Enhances two fields with one searchable category tree that can also add a
 * category in place:
 *   <select data-category-picker="single">  the primary category. The select
 *       stays in the form and is still what the server reads; without
 *       JavaScript it is simply shown.
 *   <div data-category-picker="multi" data-target="#hidden" data-source="#select">
 *       "Also surface under": ticks write a comma-separated id list into the
 *       hidden input; the primary category is never listed twice.
 * New categories go to data-create-url (JSON; the same validation as the
 * Categories page) and appear in both pickers at once.
 */
(function () {
  'use strict';
  window.Morph = window.Morph || {};
  if (window.Morph.CategoryPicker) return;

  var SEP = ' › ';
  var uid = 0;
  var openPicker = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function csrf() {
    if (window.Morph && typeof window.Morph.csrf === 'function') return window.Morph.csrf();
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function fold(s) {
    return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  // ── One list of categories per page, read from the primary select ──────────
  function Store(select) {
    this.select = select;
    this.subs = [];
    this.items = this.order(Array.prototype.filter.call(select.options, function (o) {
      return o.value;
    }).map(function (o) {
      return {
        id: o.value,
        name: o.getAttribute('data-name') || o.textContent.replace(/^(—\s*)+/, '').trim(),
        parent: o.getAttribute('data-parent') || '',
      };
    }));
  }
  Store.prototype.order = function (items) {
    // Parent before children, siblings by name: the order the server uses.
    var ids = {}, byParent = {}, out = [];
    items.forEach(function (c) { ids[c.id] = true; });
    items.forEach(function (c) {
      var key = c.parent && ids[c.parent] ? c.parent : '';
      (byParent[key] = byParent[key] || []).push(c);
    });
    Object.keys(byParent).forEach(function (k) {
      byParent[k].sort(function (a, b) {
        return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
      });
    });
    (function walk(parent, depth) {
      (byParent[parent] || []).forEach(function (c) {
        if (depth > 40) return;
        c.depth = depth;
        out.push(c);
        walk(c.id, depth + 1);
      });
    })('', 0);
    return out;
  };
  Store.prototype.get = function (id) {
    for (var i = 0; i < this.items.length; i++) if (this.items[i].id === id) return this.items[i];
    return null;
  };
  Store.prototype.path = function (id) {
    var names = [], c = this.get(id), guard = 0;
    while (c && guard++ < 40) { names.unshift(c.name); c = this.get(c.parent); }
    return names;
  };
  Store.prototype.add = function (cat) {
    if (!this.get(cat.id)) {
      this.items = this.order(this.items.concat([{ id: cat.id, name: cat.name, parent: cat.parent_id || '' }]));
      this.syncSelect();
    }
    this.subs.forEach(function (fn) { fn(); });
  };
  Store.prototype.syncSelect = function () {
    // The native select keeps every category, so the form posts a valid choice.
    var select = this.select, current = select.value;
    Array.prototype.slice.call(select.options).forEach(function (o) { if (o.value) o.remove(); });
    this.items.forEach(function (c) {
      var o = el('option', null, new Array(c.depth + 1).join('— ') + c.name);
      o.value = c.id;
      o.setAttribute('data-name', c.name);
      o.setAttribute('data-depth', String(c.depth));
      o.setAttribute('data-parent', c.parent || '');
      select.appendChild(o);
    });
    select.value = current;
  };

  // ── A picker ───────────────────────────────────────────────────────────────
  function Picker(opts) {
    this.mode = opts.mode;
    this.store = opts.store;
    this.select = opts.select;      // single: the primary <select>; multi: the primary, to exclude
    this.hidden = opts.hidden;      // multi: the CSV input
    this.createUrl = opts.createUrl;
    this.label = opts.label;
    this.id = 'catpick-' + (++uid);
    this.query = '';
    this.active = -1;
    this.rows = [];
    this.build(opts.mount);
    var self = this;
    this.store.subs.push(function () { self.render(); self.renderValue(); self.fillParents(); });
    this.select.addEventListener('change', function () { self.renderValue(); if (self.isOpen()) self.render(); });
    this.renderValue();
  }

  Picker.prototype.build = function (mount) {
    var self = this;
    var root = this.root = el('div', 'catpick');
    root.setAttribute('data-mode', this.mode);

    var trigger = this.trigger = el('button', 'catpick__trigger input');
    trigger.type = 'button';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', this.id + '-panel');
    this.valueEl = el('span', 'catpick__value');
    var chevron = el('span', 'catpick__chevron');
    chevron.setAttribute('aria-hidden', 'true');
    trigger.appendChild(this.valueEl);
    trigger.appendChild(chevron);

    var panel = this.panel = el('div', 'catpick__panel');
    panel.id = this.id + '-panel';
    panel.hidden = true;

    var search = el('div', 'catpick__search');
    var input = this.input = el('input', 'catpick__input');
    input.type = 'text';
    input.placeholder = 'Search categories';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'true');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', this.id + '-list');
    input.setAttribute('aria-label', 'Search ' + this.label.toLowerCase());
    search.appendChild(input);

    var list = this.list = el('ul', 'catpick__list');
    list.id = this.id + '-list';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', this.label);
    if (this.mode === 'multi') list.setAttribute('aria-multiselectable', 'true');

    this.emptyEl = el('p', 'catpick__empty');
    this.emptyEl.hidden = true;

    var foot = el('div', 'catpick__foot');
    var newBtn = this.newBtn = el('button', 'catpick__new');
    newBtn.type = 'button';
    var plus = el('span', 'catpick__new-plus', '+');
    plus.setAttribute('aria-hidden', 'true');
    newBtn.appendChild(plus);
    newBtn.appendChild(el('span', null, 'New category'));
    foot.appendChild(newBtn);
    foot.appendChild(this.buildCreate());

    panel.appendChild(search);
    panel.appendChild(list);
    panel.appendChild(this.emptyEl);
    panel.appendChild(foot);
    root.appendChild(trigger);
    root.appendChild(panel);
    this.note = el('p', 'catpick__note');
    this.note.setAttribute('role', 'status');
    this.note.hidden = true;
    root.appendChild(this.note);
    mount.parentNode.insertBefore(root, mount.nextSibling);

    trigger.addEventListener('click', function () { self.isOpen() ? self.close(true) : self.open(); });
    trigger.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); self.open(); }
    });
    input.addEventListener('input', function () { self.query = input.value; self.active = -1; self.render(); });
    input.addEventListener('keydown', function (e) { self.onKey(e); });
    list.addEventListener('mousedown', function (e) { e.preventDefault(); }); // keep focus in the search box
    list.addEventListener('click', function (e) {
      var row = e.target.closest('.catpick__opt');
      if (row) self.choose(self.rows.indexOf(row));
    });
    list.addEventListener('mousemove', function (e) {
      var row = e.target.closest('.catpick__opt');
      var i = row ? self.rows.indexOf(row) : -1;
      if (i !== -1 && i !== self.active) self.setActive(i, false);
    });
    newBtn.addEventListener('click', function () { self.showCreate(self.query); });
    root.addEventListener('focusout', function (e) {
      if (self.isOpen() && e.relatedTarget && !root.contains(e.relatedTarget)) self.close(false);
    });
  };

  Picker.prototype.buildCreate = function () {
    var self = this;
    var box = this.createBox = el('div', 'catpick__create');
    box.hidden = true;
    var row = el('div', 'catpick__create-row');

    var nameWrap = el('label', null);
    nameWrap.appendChild(el('span', 'catpick__create-label', 'Name'));
    var name = this.createName = el('input', 'input catpick__create-name');
    name.type = 'text';
    name.maxLength = 200;
    name.placeholder = 'e.g. Essential oils';
    nameWrap.appendChild(name);

    var parentWrap = el('label', null);
    parentWrap.appendChild(el('span', 'catpick__create-label', 'Inside'));
    var parent = this.createParent = el('select', 'input catpick__create-parent');
    parentWrap.appendChild(parent);

    row.appendChild(nameWrap);
    row.appendChild(parentWrap);
    var error = this.createError = el('p', 'catpick__error');
    error.setAttribute('role', 'alert');
    error.hidden = true;
    var actions = el('div', 'catpick__create-actions');
    var cancel = el('button', 'btn btn-ghost btn-sm', 'Cancel');
    cancel.type = 'button';
    var add = this.createAdd = el('button', 'btn btn-primary btn-sm', 'Add category');
    add.type = 'button';
    actions.appendChild(cancel);
    actions.appendChild(add);
    box.appendChild(row);
    box.appendChild(error);
    box.appendChild(actions);

    this.fillParents();
    add.addEventListener('click', function () { self.create(); });
    cancel.addEventListener('click', function () { self.hideCreate(true); });
    name.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); self.create(); }
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); self.hideCreate(true); }
    });
    return box;
  };

  Picker.prototype.fillParents = function () {
    var parent = this.createParent, keep = parent.value;
    parent.innerHTML = '';
    parent.appendChild(el('option', null, 'Top level')).value = '';
    this.store.items.forEach(function (c) {
      var o = el('option', null, new Array(c.depth + 1).join('— ') + c.name);
      o.value = c.id;
      parent.appendChild(o);
    });
    parent.value = keep;
  };

  // ── State ──────────────────────────────────────────────────────────────────
  Picker.prototype.isOpen = function () { return !this.panel.hidden; };

  Picker.prototype.selectedIds = function () {
    if (this.mode === 'single') return this.select.value ? [this.select.value] : [];
    var primary = this.select.value;
    return (this.hidden.value || '').split(',').filter(function (id) { return id && id !== primary; });
  };

  Picker.prototype.writeMulti = function (ids) {
    var primary = this.select.value, store = this.store;
    this.hidden.value = ids.filter(function (id) { return id && id !== primary && store.get(id); }).join(',');
    this.hidden.dispatchEvent(new Event('change', { bubbles: true }));
    this.renderValue();
  };

  Picker.prototype.renderValue = function () {
    var v = this.valueEl, store = this.store;
    v.innerHTML = '';
    var ids = this.selectedIds();
    if (this.mode === 'multi' && this.hidden.value !== ids.join(',')) this.hidden.value = ids.join(',');
    if (!ids.length) {
      v.appendChild(el('span', 'catpick__value-empty', this.mode === 'single' ? 'No category' : 'Choose categories…'));
      this.trigger.setAttribute('aria-label', this.label + ': none');
      return;
    }
    if (this.mode === 'single') {
      var names = store.path(ids[0]);
      if (names.length > 1) v.appendChild(el('span', 'catpick__value-path', names.slice(0, -1).join(SEP) + SEP));
      v.appendChild(document.createTextNode(names[names.length - 1] || ''));
      this.trigger.setAttribute('aria-label', this.label + ': ' + names.join(SEP));
      return;
    }
    var labels = ids.map(function (id) { var c = store.get(id); return c ? c.name : ''; }).filter(Boolean);
    v.appendChild(el('span', 'catpick__value-path', labels.length + ' selected: '));
    v.appendChild(document.createTextNode(labels.join(', ')));
    this.trigger.setAttribute('aria-label', this.label + ': ' + labels.join(', '));
  };

  // ── List ───────────────────────────────────────────────────────────────────
  Picker.prototype.render = function () {
    var self = this, store = this.store;
    var q = fold(this.query.trim());
    var chosen = {};
    this.selectedIds().forEach(function (id) { chosen[id] = true; });
    var primary = this.mode === 'multi' ? this.select.value : '';
    this.root.classList.toggle('is-searching', !!q);
    this.list.innerHTML = '';
    this.rows = [];

    function addRow(row) { self.rows.push(row); self.list.appendChild(row); return row; }

    if (this.mode === 'single' && !q) {
      var none = el('li', 'catpick__opt catpick__opt--none');
      none.setAttribute('data-depth', '0');
      none.setAttribute('data-id', '');
      none.appendChild(el('span', 'catpick__name', 'No category'));
      none.appendChild(el('span', 'catpick__check'));
      none.setAttribute('aria-selected', String(!this.select.value));
      addRow(none);
    }

    var exact = false;
    store.items.forEach(function (c) {
      var hit = !q || fold(c.name).indexOf(q) !== -1;
      if (!hit) return;
      if (q && fold(c.name) === q) exact = true;
      var row = el('li', 'catpick__opt');
      row.setAttribute('data-id', c.id);
      row.setAttribute('data-depth', String(c.depth));
      row.style.setProperty('--depth', String(c.depth));
      var name = el('span', 'catpick__name');
      var at = q ? fold(c.name).indexOf(q) : -1;
      if (at > -1) {
        name.appendChild(document.createTextNode(c.name.slice(0, at)));
        name.appendChild(el('mark', null, c.name.slice(at, at + q.length)));
        name.appendChild(document.createTextNode(c.name.slice(at + q.length)));
      } else {
        name.textContent = c.name;
      }
      row.appendChild(name);
      if (q && c.parent) row.appendChild(el('span', 'catpick__meta', store.path(c.parent).join(SEP)));
      if (c.id === primary) {
        row.appendChild(el('span', 'catpick__tag', 'Primary'));
        row.setAttribute('aria-disabled', 'true');
      }
      row.appendChild(el('span', 'catpick__check'));
      row.setAttribute('aria-selected', String(!!chosen[c.id]));
      addRow(row);
    });

    if (q && !exact) {
      var create = el('li', 'catpick__opt catpick__opt--create');
      create.setAttribute('data-depth', '0');
      create.setAttribute('data-create', '1');
      create.appendChild(el('span', 'catpick__name', 'Create “' + this.query.trim() + '”'));
      addRow(create);
    }

    this.rows.forEach(function (row, i) {
      row.id = self.id + '-opt-' + i;
      row.setAttribute('role', 'option');
    });
    var matches = this.rows.filter(function (r) { return r.hasAttribute('data-id') && r.getAttribute('data-id'); }).length;
    this.emptyEl.hidden = !(q && !matches);
    this.emptyEl.textContent = q ? 'No category matches “' + this.query.trim() + '”.' : '';
    if (this.active >= this.rows.length) this.active = this.rows.length - 1;
    if (this.active === -1 && q && this.rows.length) this.active = 0;
    this.setActive(this.active, false);
  };

  Picker.prototype.setActive = function (i, scroll) {
    this.rows.forEach(function (r) { r.classList.remove('is-active'); });
    this.active = i;
    var row = this.rows[i];
    if (!row) { this.input.removeAttribute('aria-activedescendant'); return; }
    row.classList.add('is-active');
    this.input.setAttribute('aria-activedescendant', row.id);
    if (scroll !== false) row.scrollIntoView({ block: 'nearest' });
  };

  Picker.prototype.onKey = function (e) {
    var n = this.rows.length;
    if (e.key === 'ArrowDown') { e.preventDefault(); if (n) this.setActive((this.active + 1) % n); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (n) this.setActive(this.active <= 0 ? n - 1 : this.active - 1); }
    else if (e.key === 'Enter') { e.preventDefault(); if (this.active > -1) this.choose(this.active); }
    else if (e.key === 'Escape') { e.preventDefault(); this.close(true); }
    else if (e.key === 'Tab') { this.close(false); }
  };

  Picker.prototype.choose = function (i) {
    var row = this.rows[i];
    if (!row || row.getAttribute('aria-disabled') === 'true') return;
    if (row.hasAttribute('data-create')) { this.showCreate(this.query.trim()); return; }
    var id = row.getAttribute('data-id') || '';
    if (this.mode === 'single') {
      this.select.value = id;
      this.select.dispatchEvent(new Event('change', { bubbles: true }));
      this.close(true);
      return;
    }
    var ids = this.selectedIds();
    var at = ids.indexOf(id);
    if (at === -1) ids.push(id); else ids.splice(at, 1);
    this.writeMulti(ids);
    this.setActive(i, false);
    this.render();
  };

  // ── Open / close ───────────────────────────────────────────────────────────
  Picker.prototype.open = function () {
    if (openPicker && openPicker !== this) openPicker.close(false);
    openPicker = this;
    this.hideCreate(false);
    this.query = '';
    this.input.value = '';
    this.active = -1;
    this.render();
    this.panel.hidden = false;
    this.root.classList.add('is-open');
    this.trigger.setAttribute('aria-expanded', 'true');
    var chosen = this.list.querySelector('[aria-selected="true"]');
    if (chosen) this.setActive(this.rows.indexOf(chosen));
    this.input.focus();
  };

  Picker.prototype.close = function (refocus) {
    if (!this.isOpen()) return;
    this.panel.hidden = true;
    this.root.classList.remove('is-open');
    this.trigger.setAttribute('aria-expanded', 'false');
    if (openPicker === this) openPicker = null;
    if (refocus) this.trigger.focus();
  };

  // ── New category ───────────────────────────────────────────────────────────
  Picker.prototype.showCreate = function (name) {
    this.createBox.hidden = false;
    this.newBtn.hidden = true;
    this.createError.hidden = true;
    this.createName.value = name || '';
    // A new subcategory most often belongs beside the category in view.
    if (this.mode === 'single' && this.select.value && !this.createParent.value) {
      var current = this.store.get(this.select.value);
      this.createParent.value = current ? (current.parent || current.id) : '';
    }
    this.createName.focus();
  };

  Picker.prototype.hideCreate = function (refocus) {
    this.createBox.hidden = true;
    this.newBtn.hidden = false;
    this.createError.hidden = true;
    this.createAdd.disabled = false;
    if (refocus) this.input.focus();
  };

  Picker.prototype.create = function () {
    var self = this;
    var name = this.createName.value.trim();
    if (!name) { this.fail('Give the category a name.'); this.createName.focus(); return; }
    var body = new FormData();
    body.append('name', name);
    body.append('parent', this.createParent.value);
    this.createAdd.disabled = true;
    fetch(this.createUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' },
      body: body,
    })
      .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        self.createAdd.disabled = false;
        if (!data || !data.ok) { self.fail((data && data.error) || 'That category could not be added.'); return; }
        self.store.add(data);
        self.hideCreate(false);
        self.say(data.existing ? '“' + data.path + '” already existed, so it is selected.' : 'Added “' + data.path + '”.');
        if (self.mode === 'single') {
          self.select.value = data.id;
          self.select.dispatchEvent(new Event('change', { bubbles: true }));
          self.close(true);
        } else {
          var ids = self.selectedIds();
          if (ids.indexOf(data.id) === -1 && data.id !== self.select.value) ids.push(data.id);
          self.writeMulti(ids);
          self.query = '';
          self.input.value = '';
          self.render();
          self.input.focus();
        }
      })
      .catch(function () {
        self.createAdd.disabled = false;
        self.fail('No connection. The category was not added.');
      });
  };

  Picker.prototype.fail = function (message) {
    this.createError.textContent = message;
    this.createError.hidden = false;
  };

  Picker.prototype.say = function (message) {
    var note = this.note;
    note.textContent = message;
    note.hidden = false;
    clearTimeout(this.noteTimer);
    this.noteTimer = setTimeout(function () { note.hidden = true; }, 5000);
  };

  // ── Wiring ─────────────────────────────────────────────────────────────────
  document.addEventListener('pointerdown', function (e) {
    if (openPicker && !openPicker.root.contains(e.target)) openPicker.close(false);
  });

  function init(scope) {
    var root = scope || document;
    var single = root.querySelector('select[data-category-picker="single"]');
    if (!single || single.hasAttribute('data-catpick-ready')) return;
    single.setAttribute('data-catpick-ready', '');
    var store = new Store(single);
    var createUrl = single.getAttribute('data-create-url');
    new Picker({
      mode: 'single', store: store, select: single, createUrl: createUrl, mount: single,
      label: single.getAttribute('data-label') || 'Category',
    });
    single.classList.add('catpick-native');
    root.querySelectorAll('[data-category-picker="multi"]').forEach(function (mount) {
      var hidden = document.querySelector(mount.getAttribute('data-target'));
      if (!hidden) return;
      new Picker({
        mode: 'multi', store: store, select: single, hidden: hidden, createUrl: createUrl, mount: mount,
        label: mount.getAttribute('data-label') || 'Also surface under',
      });
    });
  }

  window.Morph.CategoryPicker = { init: init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { init(); });
  else init();
})();
