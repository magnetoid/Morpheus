# Morpheus Dashboard — UI Style Guide

> The patterns we landed in the May 2026 chaos cleanup, codified so the
> next plugin author doesn't reinvent them. Pre-commit hooks in
> `.githooks/pre-commit` enforce the most-violated of these — the rest
> are advisory, with citations so you can see how the canonical pages
> use them.

This guide is **prescriptive**: when you write a new dashboard page,
match the patterns below. When you have a strong reason to break one,
say so in the commit message.

---

## 1. Page shell

Every admin page extends `admin_dashboard/base.html` and wraps its
content in this shell:

```django
{% extends "admin_dashboard/base.html" %}
{% block title %}<page title> · Morpheus{% endblock %}

{% block content %}
<div class="max-w-5xl mx-auto space-y-4">
  {% include "admin_dashboard/_breadcrumb_trail.html" with trail=breadcrumb_trail %}

  <div class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 class="text-xl font-semibold tracking-tight">{{ page_title }}</h1>
      <p class="text-sm text-[color:var(--text-muted)]">{{ subtitle }}</p>
    </div>
    {# optional right-aligned actions here #}
  </div>

  {# page content #}
</div>
{% endblock %}
```

**Max-width choice:**
- `max-w-4xl` — single-column forms (settings)
- `max-w-5xl` — most list pages, dashboards
- `max-w-6xl` — wide tables (vendor orders, conversions)
- `max-w-7xl` — only top-level lists with many columns (products, orders)

Never use no max-width on a list page — it overflows wide monitors.

**Header h1:** always `text-xl font-semibold tracking-tight`. Don't use
the deprecated `.h1` semantic class.

**Subtitle:** always `text-sm text-[color:var(--text-muted)]` so the
contrast stays consistent across pages.

See canonical examples:
- `plugins/installed/admin_dashboard/templates/admin_dashboard/products.html`
- `plugins/installed/affiliates/templates/affiliates/dashboard/analytics.html`
- `plugins/installed/marketplace/templates/marketplace/dashboard/reports.html`

---

## 2. Breadcrumb trail

Every page that's two clicks or deeper passes `breadcrumb_trail` in
context and includes the shared partial at the top of the content block:

```python
return render(request, '...', {
    'breadcrumb_trail': [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Products',  'url': '/dashboard/products/'},
        {'label': product.name[:60]},  # last item has NO url
    ],
    ...
})
```

```django
{% include "admin_dashboard/_breadcrumb_trail.html" with trail=breadcrumb_trail %}
```

The partial renders nothing when `trail` is empty, so it's safe to drop
into top-level pages too — they just don't show a trail.

**Convention:** the last item is always the current page and has no
`url`. Intermediate items always have `url`. Truncate long labels at
60 chars (product names, customer names).

---

## 3. Semantic CSS classes

We have a small vocabulary of utility classes that work across pages.
Use them; don't reinvent.

| Class | Purpose | Avoid |
|---|---|---|
| `.input` | Text inputs, selects, textareas | Bare `<input>` |
| `.btn` | Default button | `<button>` with raw Tailwind |
| `.btn-primary` | Primary CTA | Inline `style="background:…"` |
| `.btn-ghost` | Secondary action, table-row buttons | — |
| `.card` | Container with border + bg | `<div style="border:1px…">` |
| `.card-padded` | `.card` with internal padding | — |
| `.pill` | Status tag base | — |
| `.pill-success` / `.pill-warn` / `.pill-neutral` / `.pill-info` | Coloured pills | Custom colour spans |
| `.morph-table` | Dashboard data tables | Raw `<table>` |
| `.morph-table-zebra` | Add zebra striping | Custom `:nth-child(odd)` rules |
| `.field-error` | Form error messages | Red inline styles |

**Inline `<style>` blocks in templates are blocked by the pre-commit
hook** (added 2026-05-23 after the `settings_category.html` form-widget
cascade hack). If you need new utility classes, add them to the
admin_dashboard base CSS, not inline.

---

## 4. Django forms — `DashboardFormMixin`

Any form rendered with `{{ field }}` on a dashboard page should inherit
`DashboardFormMixin` so its widgets pick up `.input` automatically:

```python
from plugins.installed.admin_dashboard.forms import DashboardFormMixin

class MyForm(DashboardFormMixin, forms.Form):
    name = forms.CharField()
    # ...
```

The mixin auto-attaches `class="input"` to every visible widget except
checkboxes / radios (those have their own dashboard styles).

Don't override `widget=forms.TextInput(attrs={'class': '...'})` on
every field — the mixin handles it.

---

## 5. Plugin URL pattern

**Canonical:** each plugin owns `dashboard/<plugin>/<slug>/` via
`register_urls()`.

```python
class FooPlugin(Plugin):
    def ready(self):
        self.register_urls(
            'plugins.installed.foo.urls',
            prefix='dashboard/foo/',
            namespace='foo',
        )
```

**Legacy** `/dashboard/apps/<plugin>/<slug>/` via the plugin_page_router
still works for backward compatibility but new pages should use the
modern pattern.

When you contribute `DashboardPage` entries for sidebar surfacing,
**set `url=` to the canonical path** so the sidebar doesn't link
through the legacy router:

```python
DashboardPage(
    label='Overview', slug='overview',
    view='plugins.installed.foo.views.overview',
    icon='gauge', section='analytics', order=10,
    url='/dashboard/foo/',   # ← sidebar uses this
)
```

---

## 6. SettingsPanel — schema-driven plugin config

Plugin settings live at `/dashboard/settings/<plugin>/` automatically.
Add a `SettingsPanel` with a JSON schema:

```python
from morpheus import SettingsPanel

def contribute_settings_panel(self) -> SettingsPanel:
    return SettingsPanel(
        label='My Plugin',
        description='Short description.',
        schema=self.get_config_schema(),
        category='channels',  # or general / payments / shipping / taxes /
                              # ai / marketing / notifications / developer / apps
    )

def get_config_schema(self) -> dict:
    return {
        'type': 'object',
        'properties': {
            'enabled': {
                'type': 'boolean',
                'title': 'Enable thing',
                'default': True,
            },
            'threshold': {
                'type': 'integer',
                'title': 'Threshold',
                'default': 5,
            },
            # ...
        },
    }
```

Read at runtime via `plugin.get_config_value('enabled', True)`.

No model, no migration. The merchant gets a Save button for free, and
the values land in the shared `PluginConfig` table.

---

## 7. Agents — there is ONE Worker

After the 2026-05-23 pivot, Morpheus ships exactly one agent class:
`core.agents.builtin.Worker`. Don't subclass `MorpheusAgent`; the
pre-commit hook blocks it. Specialization happens via **Skills**:

```python
from core.agents import Skill

def contribute_skills(self) -> list:
    return [Skill(
        name='my_skill',
        label='My Skill',
        description='What it does in one sentence.',
        tools=(some_tool, another_tool),
        system_prompt_prelude='You are working on … . Standard workflow: …',
    )]
```

Linda spawns a Worker targeted at the skill via:

```
delegate.spawn_workers(jobs=[{
    'objective': 'do the thing',
    'skills': ['my_skill'],
}])
```

See `plugins/installed/seo/app.py:contribute_skills` for a real example.

---

## 8. Email templates

Every transactional email has BOTH `.txt` and `.html` versions in
`core/emails/templates/emails/`. The HTML extends the shared layout:

```django
{% extends "emails/_layout.html" %}
{% block title %}<subject line>{% endblock %}
{% block preheader %}<one-line inbox preview text>{% endblock %}
{% block body %}
  <p>Hi{% if customer.first_name %} {{ customer.first_name }}{% endif %},</p>
  <p>…body content…</p>
{% endblock %}
```

Use the shared utility classes from `_layout.html`:
`.btn`, `.pill`, `.items`, `.totals`, `.muted`.

Inline styles ARE necessary in email HTML (Outlook strips `<style>`
tags) — this is the one place the no-inline-style rule doesn't apply.

The `_send()` helper attaches the `.html` automatically — adding a new
file is the whole wiring.

---

## 9. Variant types

Every `ProductVariant` has `variant_type`: `physical` / `digital` / `virtual`.

- **Physical** — ships, requires shipping address at checkout
- **Digital** — has a `digital_file`, customer gets a `DownloadToken` on
  payment, no shipping address needed
- **Virtual** — service / gift card / booking, no fulfillment, no shipping

The dashboard form auto-flips `requires_shipping` based on the type.
The checkout flow skips the shipping-address step when the cart only
contains digital + virtual variants.

A single product can mix variant types:
- "Hardcover" — physical
- "PDF"       — digital, hamlet.pdf
- "EPUB"      — digital, hamlet.epub
- "Audiobook" — digital, hamlet.mp3

See `plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html`
(inline variant edit row) and `variant_form.html` (full-page editor)
for the UI patterns.

---

## 10. Multi-line `{# … #}` Django comments DON'T WORK

Django's `{# … #}` comment is **single-line only**. The pre-commit
hook blocks multi-line forms because we shipped this bug 8+ times.
Use `{% comment %}…{% endcomment %}` for anything that wraps:

```django
{% comment %}
This comment spans multiple lines safely.
{% endcomment %}
```

Single-line `{# short note #}` is still fine.

---

## Pre-commit hooks enforce the load-bearing rules

The `.githooks/pre-commit` hook (install once with `git config
core.hooksPath .githooks`) blocks commits that:

1. Have multi-line `{# … #}` Django comments
2. Have Python syntax errors (`py_compile` check)
3. Add a new `MorpheusAgent` subclass outside `core/agents/builtin/`
4. (May 2026 addition) Have inline `<style>` tags in new admin templates

Override with `SKIP_HOOK=1 git commit …` only when you have a real
reason and have read this guide.

---

## When in doubt

- Read the canonical examples cited above.
- Match the patterns the most-recent commits use.
- If you find yourself writing a `<style>` tag, stop and add the
  utility class to the base CSS instead.
- If you find yourself writing a `MorpheusAgent` subclass, you almost
  certainly want a Skill instead.
- If you find yourself writing custom HTML for a status pill, use
  `.pill .pill-success` etc.

Drift caught early is one commit. Drift caught after a year is a
six-week refactor.
