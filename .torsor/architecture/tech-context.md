---
type: tech-context
status: active
tags: [architecture]
---

# Tech Context

## Stack & versions
Exact pins live in `requirements.txt` / `pyproject.toml` (source of truth — not
duplicated here, since version numbers rot).

- **Backend:** Python + Django (Django 6), Postgres (behind pgbouncer), Redis.
- **Async:** Celery worker + beat; transactional outbox → NATS JetStream.
- **APIs:** Strawberry GraphQL (depth/alias-guarded, masked errors) + DRF REST;
  an agent-only GraphQL endpoint; MCP server cluster (JSON-RPC 2.0).
- **Money/data:** `djmoney` (`Money`, cents-quantized), `django-mptt` (category
  tree), `Pillow` (image variants), `bleach` (HTML sanitize on CMS save).
- **Tooling:** `uv` (deps + `uv tool install`), `ruff` (lint/format), `mypy`;
  enforced via pre-commit + PostToolUse hooks.
- **Storefront theme (`dot_books`):** vanilla HTML5 + plain CSS variables
  (Fraunces + Inter), **no Tailwind, no build step**, ~2 KB CSS. Sprinkles:
  Motion One, AMP for web stories, speculation rules.
- **Dashboard (`admin_dashboard`):** Tailwind via CDN + vanilla JS + lucide +
  htmx + TipTap (ESM from esm.sh); `data-ajax` forms expect JSON.
- **Deploy:** Docker Compose on Coolify (web + worker + beat + postgres + redis +
  pgbouncer); `git push origin main` auto-triggers a build (~3–8 min). Live at
  dotbooks.store via Cloudflare → Plesk → Coolify Traefik.

## Constraints
- **Migrations are mandatory** — a model without one fails the prod boot system
  check.
- **Plugin set** = `MORPHEUS_DEFAULT_PLUGINS` (currently ~64 active); never trust
  a count hard-coded in prose.
- **`data-ajax` views must answer JSON** (`{ok, errors}`) on success *and*
  failure.
- **Storefront stays build-stepless** — no bundler; CSS hand-written in the theme
  base; new dashboard inline `<style>` blocks are blocked by pre-commit (except
  base/layout templates).
- **CSP:** the dashboard whitelists esm.sh (script-src + connect-src) for TipTap;
  storefront uses inline `<script>`/`<style>` within the theme base only.
- **Batch before push** — rapid pushes thrash the Coolify deploy; commit locally,
  push at logical boundaries.
- **Lint/type/forbidden-import hooks are the enforcement layer**, not the
  advisory rules in `CLAUDE.md`.
