/* dot_books all-books filters: apply a panel when it closes, one panel open at a
   time, type-to-narrow inside long panels, and a bottom sheet under 720px.
   Without this file the form still works: <details> panels + the Apply button. */
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

  panels.forEach(function (panel) {
    var before = snapshot(panel);
    panel.addEventListener('toggle', function () {
      if (panel.open) {
        panels.forEach(function (p) { if (p !== panel) p.open = false; });
        before = snapshot(panel);
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
