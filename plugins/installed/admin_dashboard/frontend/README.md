# Dashboard stylesheet (Tailwind)

`../static/admin_dashboard/tailwind.css` is the dashboard's Tailwind stylesheet,
built from every app's templates, Python and scripts (`tailwind.config.js`
lists them). The dashboard shell and the media picker load it. Production
serves the committed file, because the image has no Node.

It replaced the Tailwind Play CDN in v0.136.0. The CDN compiled classes in the
browser, which needed `'unsafe-eval'` in the dashboard's CSP. The build uses the
same version (3.4.17) and the default theme, so classes render as they did.

## Rebuild

Rebuild and commit the stylesheet whenever a template, a Python file or a
script gains a Tailwind class it did not use before. CI rebuilds it and fails
when the committed file differs (`dashboard-css` in `.github/workflows/ci.yml`).

    cd plugins/installed/admin_dashboard/frontend
    npm ci               # dev-only; node_modules is gitignored
    npm run build        # → ../static/admin_dashboard/tailwind.css

## Rules

- Write every class whole. Tailwind finds a class only where it appears in full,
  so `'bg-' + tone` or `text-{{ colour }}-600` gets no CSS. Map each value to a
  whole class name instead.
- A class that arrives only from the database (a merchant's HTML, a setting)
  gets no CSS either.
- An app outside this repository is not scanned. Its dashboard pages can use
  the shell's own classes (`btn`, `card`, `pill`, …) and any utility already in
  the stylesheet, or ship a stylesheet of their own.
