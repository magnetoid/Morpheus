/* dot_books all-books filters: apply a panel when it closes, one panel open at a
   time, type-to-narrow inside long panels, a lazy panel's whole list fetched when it
   first opens, and a bottom sheet under 720px.
   Without this file the form still works: <details> panels + the Apply button, and a
   lazy panel links to its list's page. */
(function () {
  var form = document.querySelector('[data-listing-filters]');
  if (!form) return;
  form.classList.add('js-filters');
  var panels = Array.prototype.slice.call(form.querySelectorAll('.plp-facet'));
  var sheetOpen = form.querySelector('[data-sheet-open]');
  var sheetClose = form.querySelector('[data-sheet-close]');
  var phone = window.matchMedia('(max-width: 720px)');

  function snapshot(panel) {
    return Array.prototype.map.call(
      panel.querySelectorAll('input[type=checkbox]:checked'),
      function (i) { return i.value; }
    ).join('\u0000');
  }
  function fold(s) {
    return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  // A lazy panel (data-options-url) holds only its chosen boxes until it opens; then
  // the same listing answers with the panel's whole list as JSON.
  function load(panel) {
    var url = panel.getAttribute('data-options-url');
    var box = panel.querySelector('[data-panel-options]');
    if (!url || !box || !window.fetch) return;
    if (panel.hasAttribute('data-loaded') || panel.getAttribute('aria-busy') === 'true') return;
    panel.setAttribute('aria-busy', 'true');
    fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then(function (data) {
        // A box changed while the list was on its way keeps its new state.
        var ticked = {};
        box.querySelectorAll('input[type=checkbox]').forEach(function (i) { ticked[i.value] = i.checked; });
        box.innerHTML = data.html;
        box.querySelectorAll('input[type=checkbox]').forEach(function (i) {
          if (Object.prototype.hasOwnProperty.call(ticked, i.value)) i.checked = ticked[i.value];
        });
        panel.setAttribute('data-loaded', '');
        var more = panel.querySelector('[data-panel-more]');
        if (more) more.hidden = true;
        var search = panel.querySelector('[data-panel-search]');
        if (search && search.value) search.dispatchEvent(new Event('input'));
      })
      .catch(function () { /* the chosen boxes and the link to the whole list stay */ })
      .then(function () { panel.removeAttribute('aria-busy'); });
  }

  panels.forEach(function (panel) {
    var before = snapshot(panel);
    panel.addEventListener('toggle', function () {
      if (panel.open) {
        panels.forEach(function (p) { if (p !== panel) p.open = false; });
        before = snapshot(panel);
        load(panel);
        var search = panel.querySelector('[data-panel-search]');
        if (search && !phone.matches) search.focus();
      } else if (!phone.matches && snapshot(panel) !== before) {
        form.requestSubmit();
      }
    });
    var search = panel.querySelector('[data-panel-search]');
    if (search) {
      search.addEventListener('input', function () {
        var needle = fold(search.value.trim());
        var shown = 0;
        panel.querySelectorAll('.plp-option').forEach(function (opt) {
          var hit = !needle || fold(opt.textContent).indexOf(needle) !== -1;
          opt.hidden = !hit;
          if (hit) shown += 1;
        });
        var empty = panel.querySelector('[data-panel-empty]');
        if (empty) empty.hidden = shown !== 0;
      });
      search.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') e.preventDefault();
      });
    }
  });

  document.addEventListener('click', function (e) {
    if (phone.matches) return;
    panels.forEach(function (p) { if (p.open && !p.contains(e.target)) p.open = false; });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = panels.filter(function (p) { return p.open; })[0];
    if (open) {
      open.open = false;
      open.querySelector('summary').focus();
    } else if (form.classList.contains('sheet-open')) {
      closeSheet();
    }
  });

  function openSheet() {
    form.classList.add('sheet-open');
    document.body.style.overflow = 'hidden';
    if (sheetClose) sheetClose.focus();
  }
  function closeSheet() {
    form.classList.remove('sheet-open');
    document.body.style.overflow = '';
    if (sheetOpen) sheetOpen.focus();
  }
  if (sheetOpen) sheetOpen.addEventListener('click', openSheet);
  if (sheetClose) sheetClose.addEventListener('click', closeSheet);
})();
