/* Dawnchild — the header and page behaviour the designs carry (nav panel, the
   folding header on small screens, panels easing in). The design files also hold
   their own basket and checkout; this theme uses the store's cart instead, so
   none of that is here. Everything attaches with addEventListener: the checkout
   runs under a nonce-only CSP. */
(function () {
  var root = document.documentElement;
  var site = document.querySelector('.site-head');
  var head = document.querySelector('.head-inner');
  var nav = document.querySelector('.site-head .nav');

  /* The header slims once the page has scrolled on. */
  var lastSlim = 0;
  addEventListener('scroll', function () {
    var y = window.scrollY;
    if (y > lastSlim + 6 && y > 140) root.classList.add('head-slim');
    else if (y < lastSlim - 6 || y < 140) root.classList.remove('head-slim');
    lastSlim = y;
  }, { passive: true });

  /* The titles panel under a nav entry that has children. */
  var items = Array.prototype.slice.call(document.querySelectorAll('.nav-item.has-menu'));
  function setOpen(it, open) {
    var btn = it.querySelector('.menu-toggle');
    it.classList.toggle('open', open);
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open && site) site.classList.remove('compact');
  }
  items.forEach(function (it) {
    var btn = it.querySelector('.menu-toggle');
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var open = !it.classList.contains('open');
      items.forEach(function (other) { if (other !== it) setOpen(other, false); });
      setOpen(it, open);
    });
  });
  document.addEventListener('click', function (e) {
    items.forEach(function (it) { if (!it.contains(e.target)) setOpen(it, false); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') items.forEach(function (it) { setOpen(it, false); });
  });

  if (nav && head && site) {
    /* The nav row scrolls sideways on small screens; the header shows which
       edge has more. */
    var edge = function () {
      var s = nav.scrollWidth > nav.clientWidth + 1;
      head.classList.toggle('nav-scrolls', s);
      head.classList.toggle('nav-at-end', s && nav.scrollLeft + nav.clientWidth >= nav.scrollWidth - 1);
      head.classList.toggle('nav-scrolled', s && nav.scrollLeft > 1);
    };
    nav.addEventListener('scroll', edge, { passive: true });
    addEventListener('resize', edge);
    edge();

    /* Mark the page you are on, in the nav and in the titles panel. */
    var here = location.pathname.replace(/\/?$/, '/');
    Array.prototype.forEach.call(document.querySelectorAll('.site-head .nav a[href], .site-foot nav a[href]'), function (a) {
      var href = a.getAttribute('href');
      if (!href || href.charAt(0) !== '/') return;
      if (href.replace(/\/?$/, '/') === here) a.setAttribute('aria-current', 'page');
    });
    var cur = nav.querySelector('a[aria-current]');
    if (cur && nav.scrollWidth > nav.clientWidth) { cur.scrollIntoView({ block: 'nearest', inline: 'nearest' }); edge(); }

    /* The nav row folds away while reading on small screens. */
    var lastY = window.pageYOffset;
    var mq = window.matchMedia('(max-width:1040px)');
    addEventListener('scroll', function () {
      var y = window.pageYOffset;
      var anyOpen = items.some(function (it) { return it.classList.contains('open'); });
      if (!mq.matches || anyOpen) { site.classList.remove('compact'); lastY = y; return; }
      var d = y - lastY;
      if (d > 8 && y > 140) site.classList.add('compact');
      else if (d < -8 || y < 80) site.classList.remove('compact');
      lastY = y;
    }, { passive: true });
    nav.addEventListener('focusin', function () { site.classList.remove('compact'); });
  }

  /* The page keeps the unfolded header height, so folding it never moves text. */
  if (site) {
    var setH = function () {
      if (site.classList.contains('compact')) return;
      root.style.setProperty('--head-h', site.offsetHeight + 'px');
    };
    setH();
    addEventListener('resize', setH);
    if (window.ResizeObserver) new ResizeObserver(setH).observe(site);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(setH);
  }

  /* The notice can be put away for the visit. */
  var notice = document.querySelector('.notice');
  var noticeWrap = notice && notice.querySelector('.wrap');
  if (noticeWrap) {
    try { if (sessionStorage.getItem('dc-notice') === 'closed') notice.classList.add('closed'); } catch (e) { /* private mode */ }
    var x = document.createElement('button');
    x.type = 'button'; x.className = 'notice-close'; x.setAttribute('aria-label', 'Hide this notice'); x.textContent = '×';
    x.addEventListener('click', function () {
      notice.classList.add('closed');
      try { sessionStorage.setItem('dc-notice', 'closed'); } catch (e) { /* private mode */ }
    });
    noticeWrap.appendChild(x);
  }

  /* Covers settle in on the shelf; panels, headings and pictures ease in as
     they arrive. Whatever is on screen at load shows at once. */
  var motion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: no-preference)').matches;
  var covers = Array.prototype.slice.call(document.querySelectorAll('.shop-cover, .shelf-item'));
  if (!motion || !('IntersectionObserver' in window)) {
    covers.forEach(function (e) { e.classList.add('in'); });
  } else {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); cio.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    covers.forEach(function (e) { cio.observe(e); });

    var sel = 'main .cartouche, main h2, main .facts > div, main .coming-list li, main blockquote, main .two > div, main .three > div';
    var els = Array.prototype.filter.call(document.querySelectorAll(sel), function (e) {
      return !e.closest('dialog, .book, .hero, .title-block, form');
    });
    var vh = window.innerHeight;
    els.forEach(function (e) {
      e.classList.add('rv');
      var r = e.getBoundingClientRect();
      if (r.top < vh && r.bottom > 0) e.classList.add('in');
    });
    root.classList.add('rv-on');
    var rio = new IntersectionObserver(function (en) {
      en.forEach(function (xx) { if (xx.isIntersecting) { xx.target.classList.add('in'); rio.unobserve(xx.target); } });
    }, { rootMargin: '0px 0px -6% 0px' });
    els.forEach(function (e) { if (!e.classList.contains('in')) rio.observe(e); });
    addEventListener('scroll', function () {
      if (window.innerHeight + window.pageYOffset >= root.scrollHeight - 4) els.forEach(function (e) { e.classList.add('in'); });
    }, { passive: true });
  }

  /* A link to an id inside a folded <details> opens it. */
  function reveal() {
    var id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
    var el = id && document.getElementById(id);
    if (!el) return;
    var d = el.closest('details');
    if (d) { d.open = true; requestAnimationFrame(function () { el.scrollIntoView({ block: 'start' }); }); }
  }
  addEventListener('load', reveal, { once: true });
  addEventListener('hashchange', reveal);

  /* Copy buttons (the trade address). */
  Array.prototype.forEach.call(document.querySelectorAll('[data-copy]'), function (b) {
    b.addEventListener('click', function () {
      var done = function () { var t = b.textContent; b.textContent = 'Copied'; setTimeout(function () { b.textContent = t; }, 1600); };
      if (navigator.clipboard) navigator.clipboard.writeText(b.getAttribute('data-copy')).then(done, function () {});
    });
  });

  /* A select that filters a listing submits its form on change. */
  Array.prototype.forEach.call(document.querySelectorAll('[data-autosubmit]'), function (c) {
    c.addEventListener('change', function () { if (c.form) (c.form.requestSubmit ? c.form.requestSubmit() : c.form.submit()); });
  });

  /* Signup forms post to the newsletter app and say what it answered. Nothing
     here ever prints a success the server did not give. */
  Array.prototype.forEach.call(document.querySelectorAll('form[data-dc-signup]'), function (f) {
    var msg = f.querySelector('[data-signup-msg]');
    if (!msg || !window.fetch) return;
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = f.querySelector('button[type=submit]');
      if (btn) btn.disabled = true;
      fetch(f.action, { method: 'POST', credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' }, body: new FormData(f) })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
          if (window.turnstile) { var tw = f.querySelector('.cf-turnstile'); if (tw) window.turnstile.reset(tw); }
          if (btn) btn.disabled = false;
          if (res.ok) { msg.textContent = (res.data && res.data.message) || f.getAttribute('data-ok') || ''; f.reset(); }
          else { msg.textContent = (res.data && res.data.error) || f.getAttribute('data-fail') || ''; }
        })
        .catch(function () { if (btn) btn.disabled = false; f.submit(); });
    });
  });
})();
