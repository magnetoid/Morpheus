/* Morpheus motion runtime — opt-in enhancements.
 * Skips itself when prefers-reduced-motion is set. The CSS handles
 * the animations; the runtime just sets the right classnames. */
(function () {
  'use strict';
  var prefersReduced =
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) return;

  // Page-enter on initial paint
  document.documentElement.classList.add('morpheus-page-enter');

  // Skeleton shimmer replacement: any element with data-skeleton will
  // get the .morpheus-skeleton class until its children have loaded.
  document.querySelectorAll('[data-skeleton]').forEach(function (el) {
    el.classList.add('morpheus-skeleton');
  });

  // Button press class
  document.querySelectorAll('button, .morpheus-cta').forEach(function (b) {
    b.classList.add('morpheus-press');
  });
})();
