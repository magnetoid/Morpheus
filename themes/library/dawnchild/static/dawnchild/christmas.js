/* Dawnchild's Christmas look (v0.186.0): the snow, the pause, the basket's
   burst and the letter that flies.

   Runs only on a page the theme marked (body[data-christmas], the theme setting
   christmas_look) and never for a visitor who asks for reduced motion: the
   stylesheet draws every piece still without this file. The banner's snow
   waits for the banner's picture, so it never competes with it for the first
   paint; each snowfall stops while it is off screen, while the tab is hidden
   and while the visitor has paused it. Nothing here writes markup as text. */
(() => {
  'use strict';

  const body = document.body;
  if (!body || !body.hasAttribute('data-christmas')) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const root = document.documentElement;
  const rnd = (a, b) => a + Math.random() * (b - a);
  let paused = root.hasAttribute('data-christmas-paused');

  // ── Snow ────────────────────────────────────────────────────────────────
  // One soft round flake, drawn once and stamped at every size.
  const sprite = document.createElement('canvas');
  sprite.width = sprite.height = 32;
  const spriteCtx = sprite.getContext('2d');
  if (spriteCtx) {
    const g = spriteCtx.createRadialGradient(16, 16, 0, 16, 16, 16);
    g.addColorStop(0, 'rgba(255,252,246,1)');
    g.addColorStop(0.45, 'rgba(255,252,246,.85)');
    g.addColorStop(1, 'rgba(255,252,246,0)');
    spriteCtx.fillStyle = g;
    spriteCtx.fillRect(0, 0, 32, 32);
  }

  // Far, middle and near: small slow faint flakes behind larger quicker ones.
  const HERO = [
    { density: 0.9, r: [0.7, 1.4], vy: [14, 24], sway: [4, 9], alpha: 0.4, wind: 0.45 },
    { density: 0.42, r: [1.4, 2.3], vy: [30, 46], sway: [8, 15], alpha: 0.72, wind: 0.75 },
    { density: 0.11, r: [2.6, 4.0], vy: [55, 85], sway: [14, 28], alpha: 0.95, wind: 1.15 },
  ];
  const FOOTER = [{ density: 1.1, r: [0.8, 2.2], vy: [10, 26], sway: [4, 12], alpha: 0.8, wind: 0.5 }];
  const MAX_FLAKES = 600;

  const snows = [];

  function makeSnow(canvas, layers, gusts) {
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const s = { canvas, ctx, layers, gusts, w: 0, h: 0, flakes: [], visible: false, started: false, raf: 0, last: 0, clock: 0, wind: 12, windTo: 12, gustEnd: 0, nextGust: 0 };

    const flake = (l, anywhere) => {
      const L = layers[l];
      return { l, x: rnd(-20, s.w + 20), y: anywhere ? rnd(-10, s.h) : rnd(-40, -8), r: rnd(L.r[0], L.r[1]), vy: rnd(L.vy[0], L.vy[1]), a: rnd(L.sway[0], L.sway[1]), f: rnd(0.5, 1.3), p: rnd(0, 6.283) };
    };
    s.resize = () => {
      const box = canvas.getBoundingClientRect();
      if (!box.width || !box.height) return;
      s.w = box.width;
      s.h = box.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(s.w * dpr);
      canvas.height = Math.round(s.h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      s.flakes = [];
      layers.forEach((L, l) => {
        const n = Math.min(MAX_FLAKES, Math.round(((s.w * s.h) / 10000) * L.density));
        for (let k = 0; k < n; k++) s.flakes.push(flake(l, true));
      });
      s.draw();
    };
    s.step = (dt) => {
      s.clock += dt;
      if (gusts) {
        // Now and then a gust leans the whole snowfall one way, then settles.
        if (!s.nextGust) s.nextGust = s.clock + rnd(8, 12);
        if (s.clock > s.nextGust) {
          s.windTo = (Math.random() < 0.5 ? -1 : 1) * rnd(70, 130);
          s.gustEnd = s.clock + rnd(2, 3.4);
          s.nextGust = s.clock + rnd(16, 26);
        }
        if (s.clock > s.gustEnd) s.windTo = 12;
        s.wind += (s.windTo - s.wind) * Math.min(1, dt * 1.1);
      }
      for (const f of s.flakes) {
        const L = layers[f.l];
        f.y += f.vy * dt;
        f.x += s.wind * L.wind * dt + Math.cos(s.clock * f.f + f.p) * f.a * f.f * dt;
        if (f.y > s.h + 8) Object.assign(f, flake(f.l, false));
        if (f.x > s.w + 30) f.x = -30;
        else if (f.x < -30) f.x = s.w + 30;
      }
    };
    s.draw = () => {
      ctx.clearRect(0, 0, s.w, s.h);
      for (const f of s.flakes) {
        ctx.globalAlpha = layers[f.l].alpha;
        const d = f.r * 2.8;
        ctx.drawImage(sprite, f.x - d / 2, f.y - d / 2, d, d);
      }
      ctx.globalAlpha = 1;
    };
    const frame = (now) => {
      if (!running(s)) {
        s.raf = 0;
        return;
      }
      const t = now / 1000;
      const dt = s.last ? Math.min(0.05, t - s.last) : 1 / 60;
      s.last = t;
      s.step(dt);
      s.draw();
      s.raf = window.requestAnimationFrame(frame);
    };
    s.sync = () => {
      if (running(s) && !s.raf) {
        s.last = 0;
        s.raf = window.requestAnimationFrame(frame);
      }
    };
    s.start = () => {
      if (s.started) return;
      s.started = true;
      s.resize();
      if ('ResizeObserver' in window) new ResizeObserver(() => s.resize()).observe(canvas);
      if ('IntersectionObserver' in window) {
        new IntersectionObserver((entries) => {
          s.visible = entries[entries.length - 1].isIntersecting;
          s.sync();
        }).observe(canvas);
      } else {
        s.visible = true;
      }
      s.sync();
    };
    snows.push(s);
    return s;
  }

  function running(s) {
    return s.started && s.visible && !paused && !document.hidden;
  }

  document.addEventListener('visibilitychange', () => snows.forEach((s) => s.sync()));

  // The banner's snow starts once its picture has loaded (or failed), so the
  // picture keeps the first paint; a banner with no picture starts at once.
  const heroCanvas = document.querySelector('[data-xmas-snow="hero"]');
  const hero = heroCanvas ? makeSnow(heroCanvas, HERO, true) : null;
  if (hero) {
    const banner = document.getElementById('home-banner');
    const img = banner ? banner.querySelector('img') : null;
    if (img && !img.complete) {
      img.addEventListener('load', hero.start, { once: true });
      img.addEventListener('error', hero.start, { once: true });
    } else {
      hero.start();
    }
  }
  const footCanvas = document.querySelector('[data-xmas-snow="footer"]');
  const foot = footCanvas ? makeSnow(footCanvas, FOOTER, false) : null;
  if (foot) foot.start();

  // ── One pause for the whole look, remembered on this device ─────────────
  const buttons = Array.from(document.querySelectorAll('[data-xmas-pause]'));
  const showState = () => {
    for (const b of buttons) {
      const label = paused ? b.getAttribute('data-label-play') : b.getAttribute('data-label-pause');
      if (label) {
        b.setAttribute('aria-label', label);
        const text = b.querySelector('.xmas-pause__text');
        if (text) text.textContent = label;
      }
    }
  };
  const setPaused = (value) => {
    paused = value;
    root.toggleAttribute('data-christmas-paused', value);
    try { window.localStorage.setItem('dawnchild:christmas-paused', value ? '1' : '0'); } catch (e) { /* storage refused: the pause lasts this page */ }
    showState();
    snows.forEach((s) => s.sync());
  };
  for (const b of buttons) {
    b.hidden = false;
    b.addEventListener('click', () => setPaused(!paused));
  }
  showState();

  // ── A burst of flakes round the basket when its count goes up ───────────
  const basket = document.getElementById('cart-icon-link');
  const badge = document.getElementById('cart-badge');
  if (basket && badge && 'MutationObserver' in window) {
    const count = () => (badge.hidden ? 0 : parseInt(badge.textContent, 10) || 0);
    let seen = count();
    const burst = () => {
      for (let i = 0; i < 10; i++) {
        const flake = document.createElement('span');
        flake.className = i % 2 ? 'xmas-burst xmas-burst--b' : 'xmas-burst';
        flake.setAttribute('aria-hidden', 'true');
        const angle = (i / 10) * Math.PI * 2 + rnd(-0.2, 0.2);
        const reach = rnd(20, 34);
        flake.style.setProperty('--dx', `${(Math.cos(angle) * reach).toFixed(1)}px`);
        flake.style.setProperty('--dy', `${(Math.sin(angle) * reach).toFixed(1)}px`);
        flake.addEventListener('animationend', () => flake.remove(), { once: true });
        basket.append(flake);
        window.setTimeout(() => flake.remove(), 2000);
      }
    };
    new MutationObserver(() => {
      const n = count();
      if (n > seen && !paused) burst();
      seen = n;
    }).observe(badge, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });
  }

  // ── The letter flies off when the footer's letter form is sent ──────────
  const form = document.getElementById('footer-newsletter');
  const letter = document.querySelector('[data-xmas="letter"]');
  if (form && letter) {
    form.addEventListener('submit', () => {
      if (paused) return;
      letter.classList.remove('fly');
      letter.getBoundingClientRect();
      letter.classList.add('fly');
      window.setTimeout(() => letter.classList.remove('fly'), 1600);
    });
  }
})();
