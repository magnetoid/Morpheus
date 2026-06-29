# Linda per-page AI helper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "Guided UX & Micro-animations" toggle with an opt-in per-page Linda helper card that explains the current dashboard page and advises on its numbers.

**Architecture:** A new `ai_page_help` store setting gates a Linda card injected into the dashboard shell. Client JS reads the visible page text and POSTs it to a new staff-only `core.assistant` endpoint, which asks the configured LLM (no tools → auto-cached 1h) for a structured `{summary, numbers, actions}` payload rendered into the card. Micro-animations become always-on.

**Tech Stack:** Django, Django templates, vanilla JS (no build step), Tailwind CDN, the existing `core.assistant` runtime + `core.agents` LLM layer.

## Global Constraints

- New dep policy: **no new packages** — uses existing `core.assistant` / `core.agents` only.
- Run tests with: `DATABASE_URL='sqlite:///:memory:' python manage.py test <path>`.
- Migrations must pass `python manage.py makemigrations --check --dry-run` and apply on Postgres (CI gate). This change is an additive `BooleanField` + a `RemoveField` — both Postgres-safe.
- Dashboard AJAX endpoints **must return JSON on success AND failure** (never a 500/HTML) — false "saved/loaded" otherwise.
- New staff-facing view requires the **3 permission-boundary tests** (anon blocked, authed-non-staff blocked, staff allowed).
- LLM call must be **tools=None** so the existing `@_llm_breaker` 1h cache applies (`core/agents/llm.py:75`).
- Toggle default is **OFF** (opt-in). Endpoint + service live in `core.assistant`; `admin_dashboard` only contributes the settings row, the templatetag, the `{% include %}`, and the animations decoupling. No plugin→plugin imports.

---

### Task 1: `ai_page_help` store setting (model + migration)

**Files:**
- Modify: `core/models.py:36-39` (the `guided_ux_mode` field)
- Create: `core/migrations/00NN_ai_page_help.py` (generated)
- Test: `core/tests/test_store_settings_ai_help.py`

**Interfaces:**
- Produces: `StoreSettings.ai_page_help: bool` (default `False`); readable via `StoreSettings.get('ai_page_help', False)`.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_store_settings_ai_help.py
from django.test import TestCase
from core.models import StoreSettings


class AiPageHelpSettingTests(TestCase):
    def test_default_is_off(self):
        StoreSettings.objects.create(store_name='Test')
        self.assertFalse(StoreSettings.get('ai_page_help', False))

    def test_can_enable(self):
        StoreSettings.objects.create(store_name='Test', ai_page_help=True)
        self.assertTrue(StoreSettings.get('ai_page_help', False))

    def test_guided_ux_mode_removed(self):
        self.assertFalse(
            any(f.name == 'guided_ux_mode' for f in StoreSettings._meta.get_fields())
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_store_settings_ai_help -v 2`
Expected: FAIL — `TypeError: 'ai_page_help' is an invalid keyword` / `guided_ux_mode` still present.

- [ ] **Step 3: Swap the model field**

In `core/models.py`, replace the `guided_ux_mode` block:

```python
    # AI-assisted tips & help — when on, Linda explains each dashboard page.
    ai_page_help = models.BooleanField(
        default=False,
        help_text='Show Linda on every dashboard page to explain what you are '
        'looking at and advise what to do. Uses your configured AI provider.',
    )
```

- [ ] **Step 4: Generate the migration**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py makemigrations core`
Expected: a new migration with `RemoveField(guided_ux_mode)` + `AddField(ai_page_help)`. Open it and confirm exactly those two ops.

- [ ] **Step 5: Run tests + migration check**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_store_settings_ai_help -v 2 && DATABASE_URL='sqlite:///:memory:' python manage.py makemigrations --check --dry-run`
Expected: PASS, and "No changes detected".

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ core/tests/test_store_settings_ai_help.py
git commit -m "feat(core): ai_page_help store setting; drop guided_ux_mode"
```

---

### Task 2: Settings form, templatetag, animations always-on

**Files:**
- Modify: `plugins/installed/admin_dashboard/forms/settings.py:24-28` (field) + `:30-50` (`__init__` initial tuple)
- Modify: `plugins/installed/admin_dashboard/templatetags/morph_dashboard.py:269-285`
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/base.html:887-888`
- Test: `plugins/installed/admin_dashboard/tests/test_ai_page_help_form.py`

**Interfaces:**
- Consumes: `StoreSettings.ai_page_help` (Task 1).
- Produces: template tag `{% get_ai_page_help as ai_help %}` (default `False`); `<body>` always carries `guided-ux`.

- [ ] **Step 1: Write the failing test**

```python
# plugins/installed/admin_dashboard/tests/test_ai_page_help_form.py
from django.test import TestCase
from core.models import StoreSettings
from plugins.installed.admin_dashboard.forms.settings import StoreGeneralForm


class AiPageHelpFormTests(TestCase):
    def test_form_saves_ai_page_help(self):
        s = StoreSettings.objects.create(store_name='T')
        form = StoreGeneralForm(
            data={'store_name': 'T', 'primary_currency': 'USD',
                  'country': 'US', 'timezone': 'UTC', 'ai_page_help': 'on'},
            instance=s,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        s.refresh_from_db()
        self.assertTrue(s.ai_page_help)

    def test_templatetag_default_off(self):
        from plugins.installed.admin_dashboard.templatetags.morph_dashboard import (
            get_ai_page_help,
        )
        self.assertFalse(get_ai_page_help())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.admin_dashboard.tests.test_ai_page_help_form -v 2`
Expected: FAIL — `ImportError: cannot import name 'get_ai_page_help'` / form has no `ai_page_help`.

- [ ] **Step 3: Swap the form field + initial tuple**

In `forms/settings.py`, replace the `guided_ux_mode` form field with:

```python
    ai_page_help = forms.BooleanField(
        required=False,
        label='AI-assisted tips & help',
        help_text='Show Linda on every dashboard page to explain what you are '
        'looking at and advise what to do. Uses your configured AI provider.',
    )
```

and in `__init__`, change `'guided_ux_mode',` in the initial-field tuple to `'ai_page_help',`.

- [ ] **Step 4: Swap the templatetag**

In `templatetags/morph_dashboard.py`, replace `get_guided_ux_mode` with:

```python
@register.simple_tag
def get_ai_page_help():
    try:
        from core.models import StoreSettings

        return StoreSettings.get('ai_page_help', False)
    except Exception:
        import logging

        logging.getLogger('morpheus.admin').warning(
            'get_ai_page_help: StoreSettings load failed; defaulting off',
            exc_info=True,
        )
        return False
```

- [ ] **Step 5: Decouple animations (always-on) in base.html**

Replace lines 887-888:

```django
{% get_guided_ux_mode as guided_ux %}
<body class="min-h-screen flex {% if guided_ux %}guided-ux{% endif %}" hx-boost="true" ...>
```

with (drop the tag call; `guided-ux` always present):

```django
<body class="min-h-screen flex guided-ux" hx-boost="true" hx-target="#main-content" hx-select="#main-content" hx-swap="outerHTML show:window:top" hx-push-url="true" hx-indicator="#htmx-progress">
```

- [ ] **Step 6: Run tests + ruff**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.admin_dashboard.tests.test_ai_page_help_form -v 2 && ruff check plugins/installed/admin_dashboard core`
Expected: PASS, ruff clean. Confirm no remaining `guided_ux_mode` / `get_guided_ux_mode` refs: `grep -rn "guided_ux_mode\|get_guided_ux_mode" plugins core` returns nothing.

- [ ] **Step 7: Commit**

```bash
git add plugins/installed/admin_dashboard/forms/settings.py plugins/installed/admin_dashboard/templatetags/morph_dashboard.py plugins/installed/admin_dashboard/templates/admin_dashboard/base.html plugins/installed/admin_dashboard/tests/test_ai_page_help_form.py
git commit -m "feat(dashboard): AI-help settings row + templatetag; animations always-on"
```

---

### Task 3: `build_page_help` service (LLM → structured dict)

**Files:**
- Create: `core/assistant/page_help.py`
- Test: `core/assistant/tests/test_page_help.py`

**Interfaces:**
- Consumes: `core.assistant.providers.get_default_provider`, `core.agents.llm.LLMMessage`.
- Produces:
  - `build_page_help(context: dict, provider=None) -> dict` → `{'ok': bool, 'summary': str, 'numbers': list[dict], 'actions': list[str], 'message': str}`. `context` keys: `page_title: str`, `page_url: str`, `page_text: str`, `structured: dict | None`.
  - `_parse_json(text: str) -> dict | None` (defensive — there is NO shared repair util).

- [ ] **Step 1: Write the failing tests**

```python
# core/assistant/tests/test_page_help.py
import json
from django.test import TestCase
from core.assistant.page_help import build_page_help, _parse_json


class _FakeProvider:
    def __init__(self, text):
        self._text = text

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        class R:  # minimal LLMResponse stand-in
            pass
        r = R()
        r.text = self._text
        return r


GOOD = json.dumps({
    'summary': 'This is your Orders page.',
    'numbers': [{'label': 'Orders', 'reading': '42, up 12%'}],
    'actions': ['Fulfill the 3 pending orders'],
})


class PageHelpTests(TestCase):
    def test_parses_clean_json(self):
        out = build_page_help(
            {'page_title': 'Orders', 'page_url': '/dashboard/orders/',
             'page_text': '42 orders', 'structured': None},
            provider=_FakeProvider(GOOD),
        )
        self.assertTrue(out['ok'])
        self.assertEqual(out['summary'], 'This is your Orders page.')
        self.assertEqual(out['numbers'][0]['label'], 'Orders')
        self.assertIn('Fulfill', out['actions'][0])

    def test_parses_json_wrapped_in_prose(self):
        wrapped = 'Sure!\n```json\n' + GOOD + '\n```\nHope that helps.'
        self.assertIsNotNone(_parse_json(wrapped))

    def test_empty_page_text_skips_llm(self):
        out = build_page_help(
            {'page_title': 'X', 'page_url': '/x/', 'page_text': '  ', 'structured': None},
            provider=_FakeProvider(GOOD),
        )
        self.assertFalse(out['ok'])

    def test_malformed_json_returns_not_ok(self):
        out = build_page_help(
            {'page_title': 'Orders', 'page_url': '/o/', 'page_text': 'x' * 50,
             'structured': None},
            provider=_FakeProvider('not json at all'),
        )
        self.assertFalse(out['ok'])
        self.assertTrue(out['message'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant.tests.test_page_help -v 2`
Expected: FAIL — `ModuleNotFoundError: core.assistant.page_help`.

- [ ] **Step 3: Implement the service**

```python
# core/assistant/page_help.py
"""Linda's per-page helper: turn what's on a dashboard page into a short
explanation + advice. No tools → the LLM layer's 1h cache applies, so repeat
views of unchanged pages are free."""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger('morpheus.assistant')

_SYSTEM = (
    "You are Linda, the in-dashboard assistant for a Morpheus e-commerce store. "
    "A merchant is looking at a dashboard page. Using ONLY the page content given, "
    "explain it plainly and advise. Be concise, warm, and concrete. "
    "Respond with STRICT JSON, no prose, in this shape: "
    '{"summary": "1-2 sentences on what this page is for", '
    '"numbers": [{"label": "metric name", "reading": "what the value means in plain words"}], '
    '"actions": ["a concrete next step", "..."]}. '
    "Use at most 4 numbers and 3 actions. If the page has no meaningful data, "
    'return {"summary": "", "numbers": [], "actions": []}.'
)

_MIN_TEXT = 20  # below this the page is effectively empty — skip the LLM


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{.*\}', text, re.DOTALL)  # first {...} block
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def build_page_help(context: dict, provider=None) -> dict:
    fail = {'ok': False, 'summary': '', 'numbers': [], 'actions': [], 'message': ''}
    page_text = (context.get('page_text') or '').strip()
    if len(page_text) < _MIN_TEXT:
        return {**fail, 'message': 'Not enough on this page to explain.'}

    if provider is None:
        from core.assistant.providers import get_default_provider

        provider = get_default_provider()

    from core.agents.llm import LLMMessage

    user = (
        f"Page title: {context.get('page_title') or 'Dashboard'}\n"
        f"Page URL: {context.get('page_url') or ''}\n"
    )
    structured = context.get('structured')
    if structured:
        user += f"Structured data: {json.dumps(structured)[:2000]}\n"
    user += f"Visible page text:\n{page_text[:4000]}"

    try:
        resp = provider.respond(
            messages=[
                LLMMessage(role='system', content=_SYSTEM),
                LLMMessage(role='user', content=user),
            ],
            tools=None,
            temperature=0.2,
            max_tokens=700,
        )
    except Exception as e:  # noqa: BLE001 — provider/breaker safety net
        logger.warning('page_help: provider call failed: %s', e, exc_info=True)
        return {**fail, 'message': "Linda is unavailable right now."}

    data = _parse_json(getattr(resp, 'text', '') or '')
    if not isinstance(data, dict):
        return {**fail, 'message': "Linda could not read this page."}

    return {
        'ok': True,
        'summary': str(data.get('summary') or ''),
        'numbers': [
            {'label': str(n.get('label', '')), 'reading': str(n.get('reading', ''))}
            for n in (data.get('numbers') or [])[:4]
            if isinstance(n, dict)
        ],
        'actions': [str(a) for a in (data.get('actions') or [])[:3]],
        'message': '',
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant.tests.test_page_help -v 2`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core/assistant/page_help.py core/assistant/tests/test_page_help.py
git commit -m "feat(assistant): build_page_help service (page text → structured tips)"
```

---

### Task 4: Endpoint + URL + permission boundary tests

**Files:**
- Modify: `core/assistant/views.py` (add `assistant_page_help`)
- Modify: `core/assistant/urls.py:11-16` (add route)
- Test: `core/assistant/tests/test_page_help_view.py`

**Interfaces:**
- Consumes: `build_page_help` (Task 3).
- Produces: `POST /dashboard/assistant/page-help/` (name `assistant:page_help`) → JSON `{ok, summary, numbers, actions, message}`, always status 200 for authenticated staff; 302/403 for non-staff.

- [ ] **Step 1: Write the failing tests**

```python
# core/assistant/tests/test_page_help_view.py
import json
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()
OK = {'ok': True, 'summary': 'Hi', 'numbers': [], 'actions': ['do x'], 'message': ''}


class PageHelpViewTests(TestCase):
    def setUp(self):
        self.url = reverse('assistant:page_help')

    def _post(self):
        return self.client.post(
            self.url,
            data=json.dumps({'page_title': 'Orders', 'page_url': '/dashboard/orders/',
                             'page_text': 'x' * 60}),
            content_type='application/json',
        )

    def test_anonymous_blocked(self):
        self.assertIn(self._post().status_code, (302, 403))

    def test_authed_non_staff_blocked(self):
        User.objects.create_user('bob', password='p')
        self.client.login(username='bob', password='p')
        self.assertIn(self._post().status_code, (302, 403))

    @patch('core.assistant.views.build_page_help', return_value=OK)
    def test_staff_allowed(self, _m):
        User.objects.create_user('amy', password='p', is_staff=True)
        self.client.login(username='amy', password='p')
        r = self._post()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    @patch('core.assistant.views.build_page_help', side_effect=RuntimeError('boom'))
    def test_returns_json_on_error(self, _m):
        User.objects.create_user('amy', password='p', is_staff=True)
        self.client.login(username='amy', password='p')
        r = self._post()
        self.assertEqual(r.status_code, 200)  # JSON contract: never 500
        self.assertFalse(r.json()['ok'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant.tests.test_page_help_view -v 2`
Expected: FAIL — `NoReverseMatch: 'page_help'`.

- [ ] **Step 3: Add the view**

In `core/assistant/views.py`, add the import near the top:

```python
from core.assistant.page_help import build_page_help
```

and append the view (mirrors `assistant_invoke`'s decorators + always-JSON pattern):

```python
@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def assistant_page_help(request):
    """POST page context → JSON {ok, summary, numbers, actions, message}.
    Always responds 200 with JSON (dashboard AJAX contract)."""
    try:
        body = (
            json.loads(request.body or b'{}')
            if request.content_type == 'application/json'
            else dict(request.POST.items())
        )
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')

    context = {
        'page_title': (body.get('page_title') or '')[:200],
        'page_url': (body.get('page_url') or '')[:512],
        'page_text': (body.get('page_text') or '')[:8000],
        'structured': body.get('structured') if isinstance(body.get('structured'), dict) else None,
    }
    try:
        result = build_page_help(context)
    except Exception as e:  # noqa: BLE001 — last-resort safety net
        logger.error('assistant: page_help crashed: %s', e, exc_info=True)
        return JsonResponse(
            {'ok': False, 'summary': '', 'numbers': [], 'actions': [],
             'message': 'Linda is unavailable right now.'},
            status=200,
        )
    return JsonResponse(result, status=200)
```

- [ ] **Step 4: Add the route**

In `core/assistant/urls.py`, add inside `urlpatterns`:

```python
    path('page-help/', views.assistant_page_help, name='page_help'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant.tests.test_page_help_view -v 2`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add core/assistant/views.py core/assistant/urls.py core/assistant/tests/test_page_help_view.py
git commit -m "feat(assistant): staff-only page-help endpoint (always-JSON)"
```

---

### Task 5: Helper card partial + shell include + client JS

**Files:**
- Create: `core/assistant/templates/assistant/_page_helper.html`
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/base.html:1150-1167` (inside `#main-content`, above `{% block content %}`)
- Test: `core/assistant/tests/test_page_helper_render.py`

**Interfaces:**
- Consumes: `assistant:page_help` endpoint (Task 4), `get_ai_page_help` tag (Task 2).
- Produces: a `#linda-page-helper` container with init that runs on load + `htmx:afterSwap`.

- [ ] **Step 1: Write the failing test**

```python
# core/assistant/tests/test_page_helper_render.py
from django.test import TestCase
from django.template import Context, Template


class PageHelperRenderTests(TestCase):
    def test_partial_renders_container_and_endpoint(self):
        html = Template('{% include "assistant/_page_helper.html" %}').render(Context({}))
        self.assertIn('id="linda-page-helper"', html)
        self.assertIn('/dashboard/assistant/page-help/', html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant.tests.test_page_helper_render -v 2`
Expected: FAIL — `TemplateDoesNotExist: assistant/_page_helper.html`.

- [ ] **Step 3: Create the partial**

```django
{# core/assistant/templates/assistant/_page_helper.html #}
{% load static %}
<section id="linda-page-helper" class="card card-padded" data-endpoint="/dashboard/assistant/page-help/"
         style="margin-bottom:1rem; display:flex; gap:.85rem; align-items:flex-start;">
  <img src="{% static 'assistant/linda-avatar.jpg' %}" alt="Linda" width="36" height="36"
       style="border-radius:50%; object-fit:cover; flex-shrink:0;">
  <div style="flex:1; min-width:0;">
    <div style="display:flex; align-items:center; gap:.5rem;">
      <strong style="font-size:.875rem;">Linda's take on this page</strong>
      <button type="button" id="linda-help-toggle" class="btn btn-ghost p-1"
              style="margin-left:auto; font-size:.75rem;" aria-expanded="true">Hide</button>
    </div>
    <div id="linda-help-body" style="font-size:.8125rem; color:var(--text-muted); margin-top:.35rem;">
      <div class="skeleton" style="height:1rem; width:60%; border-radius:4px;"></div>
    </div>
  </div>
</section>
<script>
(function () {
  var root = document.getElementById('linda-page-helper');
  if (!root || root.dataset.bound) return;
  root.dataset.bound = '1';
  var body = document.getElementById('linda-help-body');
  var toggle = document.getElementById('linda-help-toggle');

  function hash(s) { var h = 5381, i = s.length; while (i) h = (h * 33) ^ s.charCodeAt(--i); return (h >>> 0).toString(36); }
  function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

  toggle.addEventListener('click', function () {
    var open = body.style.display !== 'none';
    body.style.display = open ? 'none' : '';
    toggle.textContent = open ? 'Show' : 'Hide';
    toggle.setAttribute('aria-expanded', String(!open));
    try { localStorage.setItem('linda-help-collapsed', open ? '1' : '0'); } catch (_) {}
  });
  if (localStorage.getItem('linda-help-collapsed') === '1') {
    body.style.display = 'none'; toggle.textContent = 'Show'; toggle.setAttribute('aria-expanded', 'false');
  }

  function render(d) {
    if (!d || !d.ok || (!d.summary && !(d.actions || []).length)) {
      body.innerHTML = '<em>' + esc((d && d.message) || 'Nothing to explain here.') + '</em>';
      return;
    }
    var h = '';
    if (d.summary) h += '<p style="margin:0 0 .4rem; color:var(--text);">' + esc(d.summary) + '</p>';
    if ((d.numbers || []).length) {
      h += '<ul style="margin:.2rem 0 .4rem; padding-left:1rem;">';
      d.numbers.forEach(function (n) {
        h += '<li><strong>' + esc(n.label) + ':</strong> ' + esc(n.reading) + '</li>';
      });
      h += '</ul>';
    }
    if ((d.actions || []).length) {
      h += '<div style="font-weight:600; color:var(--text); margin-top:.3rem;">What to do next</div><ul style="margin:.2rem 0 0; padding-left:1rem;">';
      d.actions.forEach(function (a) { h += '<li>' + esc(a) + '</li>'; });
      h += '</ul>';
    }
    body.innerHTML = h;
  }

  function collectText() {
    var main = document.getElementById('main-content');
    var t = main ? (main.innerText || '') : '';
    return t.replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, '').replace(/\s+/g, ' ').trim().slice(0, 4000);
  }
  function structured() {
    var el = document.getElementById('page-context');
    if (!el) return null;
    try { return JSON.parse(el.textContent || 'null'); } catch (_) { return null; }
  }

  function load() {
    var text = collectText();
    var ctx = {
      page_title: document.title || '',
      page_url: location.pathname,
      page_text: text,
      structured: structured(),
    };
    var sig = location.pathname + '|' + hash(text);
    var key = 'linda-help:' + sig;
    try {
      var cached = sessionStorage.getItem(key);
      if (cached) { render(JSON.parse(cached)); return; }
    } catch (_) {}
    var csrf = (document.cookie.split(';').map(function (c) { return c.trim(); })
      .find(function (c) { return c.indexOf('csrftoken=') === 0; }) || '').split('=')[1];
    fetch(root.dataset.endpoint, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
      body: JSON.stringify(ctx),
    }).then(function (r) { return r.json(); })
      .then(function (d) { try { sessionStorage.setItem(key, JSON.stringify(d)); } catch (_) {} render(d); })
      .catch(function () { body.innerHTML = '<em>Linda is unavailable right now.</em>'; });
  }
  load();
})();
</script>
```

- [ ] **Step 4: Include it in the shell**

In `base.html`, inside `<main id="main-content" ...>` and immediately **before** `{% block content %}{% endblock %}` (around line 1167):

```django
  {% get_ai_page_help as ai_help %}
  {% if ai_help %}{% include "assistant/_page_helper.html" %}{% endif %}
  {% block content %}{% endblock %}
```

Note: it sits inside `#main-content`, which htmx-boost swaps on navigation, so the `<script>` re-runs and re-inits per page (the `data-bound` guard prevents double-binding within a single DOM).

- [ ] **Step 5: Run test + tag-balance check**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant.tests.test_page_helper_render -v 2`
Expected: PASS. Also confirm base.html has balanced `{% block %}`/`{% endblock %}` and the new `{% if %}`/`{% endif %}`.

- [ ] **Step 6: Commit**

```bash
git add core/assistant/templates/assistant/_page_helper.html plugins/installed/admin_dashboard/templates/admin_dashboard/base.html core/assistant/tests/test_page_helper_render.py
git commit -m "feat(assistant): per-page Linda helper card (gated by ai_page_help)"
```

---

### Task 6: Full verification + deploy

**Files:** none (verification only)

- [ ] **Step 1: Run the full affected suites**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.assistant core.tests plugins.installed.admin_dashboard -v 1`
Expected: all PASS.

- [ ] **Step 2: Lint + migration + check gates**

Run: `ruff check . && ruff format --check . && DATABASE_URL='sqlite:///:memory:' python manage.py makemigrations --check --dry-run && DATABASE_URL='sqlite:///:memory:' python manage.py check`
Expected: all clean.

- [ ] **Step 3: Manual smoke (local or post-deploy)**

In Settings → General, enable **AI-assisted tips & help**. Load Home, Orders, Products. Confirm: Linda card appears above content with a relevant summary + numbers + actions; collapse persists; revisiting a page renders instantly (sessionStorage). Disable the toggle → card gone, micro-animations still work.

- [ ] **Step 4: Commit any fixups, then deploy**

```bash
git push origin main   # triggers Coolify; watch health through the container swap
```

Expected: brief 503 swap window, then stable 200. The migration is additive + RemoveField (Postgres-safe).

---

## Self-review

- **Spec coverage:** setting swap (T1/T2), animations always-on (T2), card partial + placement (T5), DOM+structured sensing (T5 JS), proactive+cached via sessionStorage + 1h LLM cache (T3/T5), staff-only always-JSON endpoint (T4), 3 permission-boundary tests (T4), JSON-repair-equivalent parser (T3 `_parse_json`), tests + Postgres-safe migration (T1/T6). All covered.
- **Placeholder scan:** none — every code step has full code.
- **Type consistency:** `build_page_help(context, provider=None) -> dict` with keys `ok/summary/numbers/actions/message` is produced in T3 and consumed verbatim by the T4 view and T5 JS `render()`. Endpoint name `assistant:page_help` consistent T4↔T5. Setting `ai_page_help` + tag `get_ai_page_help` consistent T1↔T2↔T5.
- **Correction vs spec:** spec referenced an "existing JSON-repair util" — none is public, so T3 ships a local `_parse_json` instead (documented in the task).
