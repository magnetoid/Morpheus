# Contributing to Morpheus

Thanks for taking a look. Morpheus is built mostly out in the open — this
file is the short version of how to get a working setup, what to send in
a PR, and where the lines are.

## Local setup

```bash
git clone https://github.com/magnetoid/morpheus.git
cd morpheus
docker compose up -d        # postgres + redis + web + worker + beat
docker compose exec web python manage.py migrate
docker compose exec web python manage.py demo_seed
open http://localhost:8000
```

Default admin login: create one with `manage.py createsuperuser`.

## Repository layout

- `core/` — engine. Auth, hooks bus, request lifecycle, observability,
  i18n kernel. Touch sparingly; new features almost never live here.
- `plugins/installed/<name>/` — every feature. `apps.py` + `app.py` +
  `models.py` + `migrations/`. The way the platform is meant to grow.
- `themes/library/<name>/` — storefront templates + section components.
  `dot_books` is the reference theme.
- `morph/` — Django project (settings, root URLs, ASGI/WSGI).
- `api/` — GraphQL schema + REST shims.

If you're adding a feature, **build it as a plugin** unless you can defend
why it has to be in `core`. CLAUDE.md spells out the modular contract.

## Pull request checklist

- The PR description explains *why* (motivation), not just *what*.
- New tables ship with a migration in the same commit.
- Touched files have a passing `python -m py_compile` check.
- Storefront UI changes include a screenshot or a `curl` smoke check.
- New plugins added to `MORPHEUS_DEFAULT_APPS` in `morph/settings.py`.
- No drive-by refactors of unrelated code.
- One feature per PR. Split if it grew.

## Style

- Python: match the existing style. Snake-case for files + functions,
  type hints where they actually help, docstrings on anything non-obvious.
- Templates: Django template language, no JS framework. Tailwind CDN is
  fine for storefront themes; the dashboard uses a hand-built component
  library under `plugins/installed/admin_dashboard/templates/`.
- No emojis in code or commits unless we already use them in that file.
- Comments explain *why*, not *what*. The well-named identifier is the
  *what*.

## Tests

```bash
docker compose exec web python manage.py test
docker compose exec web python manage.py test plugins.installed.reviews
```

A new plugin should ship with at least one smoke test covering the
happy path (model save → service call → assert side-effect). The
existing tests under `plugins/installed/<name>/tests/test_smoke.py`
are the pattern to copy.

## AI-assisted contributions

This repo welcomes AI-assisted code, with one rule: **the PR author
verified it works.** That means a passing test suite *and* a smoke
check against a running instance. Generated code that ships untested
is not accepted.

Read `CLAUDE.md` for the house rules on AI-assisted work — they apply
to humans too.

## License

Business Source License 1.1 — see [LICENSE](LICENSE). Non-production use
(evaluation, development, testing) is free; production use needs a commercial
licence from the licensor; each version converts to Apache 2.0 four years
after it is published (ADR 0038). Versions up to v0.76.0 were Apache 2.0.

By submitting a contribution you agree that it is licensed under the same
terms as the rest of the repo, and you grant Marko Tiosavljevic the right to
relicense it — including under the Change License — because the licence's
conversion to Apache 2.0 depends on the licensor holding that right. Future
enterprise features may ship as separate, separately licensed packages.
