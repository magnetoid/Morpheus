// The dashboard's Tailwind build. It replaces the Play CDN, which compiled
// classes in the browser and needed 'unsafe-eval' in the dashboard's CSP.
//
// Tailwind 3.4.17 with the default theme, the same version and config the CDN
// served, so every class renders as before. A class is in the stylesheet only
// when it appears whole in one of the files below: never build a class name
// from pieces ('bg-' + colour), in a template, in Python or in JavaScript.
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: {
    relative: true,
    files: [
      // Every app's templates (dashboard pages, cards, panels, partials).
      '../../*/templates/**/*.html',
      '../../../templates/**/*.html',
      '../../../../core/**/templates/**/*.html',
      '../../../../templates/**/*.html',
      // Class names written in Python (form widgets, template tags, views).
      '../../*/**/*.py',
      '../../../*.py',
      '../../../../core/**/*.py',
      '!../../*/tests/**',
      '!../../*/migrations/**',
      '!../../../../core/**/tests/**',
      '!../../../../core/**/migrations/**',
      // Scripts that add classes in the browser. Built bundles are left out.
      '../../*/static/**/*.js',
      '../../../../core/**/static/**/*.js',
      '!../../*/static/**/*.bundle.js',
    ],
  },
};
