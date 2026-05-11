---
name: plugin-skeleton
description: Scaffold a new Morpheus plugin (apps.py, plugin.py, models.py, migrations/__init__.py, tests/__init__.py + boundary-test stub) following the plugin contract in CLAUDE.md and PLUGIN_DEVELOPMENT.md.
---

# plugin-skeleton

Trigger phrase: **"scaffold a new plugin called X"** or **"new plugin X"**.

## What this skill produces

Given a plugin name `<name>` (snake_case), create
`plugins/installed/<name>/` containing exactly these files:

```
plugins/installed/<name>/
├── __init__.py          # empty
├── apps.py              # AppConfig with name = 'plugins.installed.<name>'
├── plugin.py            # Plugin manifest (name, label, version, requires, ready)
├── models.py            # empty stub with `from django.db import models`
├── migrations/
│   └── __init__.py      # empty
└── tests/
    ├── __init__.py      # empty
    └── test_<name>.py   # permission-boundary stubs (3 cases)
```

## Steps

1. Confirm `<name>` is unique under `plugins/installed/`. If not, stop
   and ask which name to use instead.
2. Create the 7 files above. **No models, no views, no URLs** — leave
   those for the actual feature work.
3. Register the plugin in `morph/settings.py:MORPHEUS_DEFAULT_PLUGINS`
   by inserting `'plugins.installed.<name>'` in alphabetical order.
4. Do NOT generate an initial migration — that comes from
   `python manage.py makemigrations <name>` once a model exists.
5. Compile-check every new `.py` file.

## File templates

**`apps.py`**:

```python
from django.apps import AppConfig


class <Name>Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.<name>'
    label = '<name>'
```

**`plugin.py`**:

```python
from morpheus import Plugin


class <Name>Plugin(Plugin):
    name = '<name>'
    label = '<Name>'
    version = '0.1.0'
    description = '<one-line purpose>'
    requires: list[str] = []

    def ready(self):
        pass
```

**`tests/test_<name>.py`** — permission-boundary scaffold (mandatory
per [PLUGIN_DEVELOPMENT.md §13](../../../docs/PLUGIN_DEVELOPMENT.md)):

```python
from django.test import TestCase
from django.urls import reverse


class <Name>BoundaryTests(TestCase):
    """Mandatory boundary tests once views land. Replace `view_name`."""

    def test_anonymous_blocked(self):
        # response = self.client.get(reverse('view_name'))
        # self.assertEqual(response.status_code, 302)
        self.skipTest('No views yet — wire on first endpoint.')

    def test_authed_without_scope_blocked(self):
        self.skipTest('No views yet — wire on first endpoint.')

    def test_authed_with_scope_allowed(self):
        self.skipTest('No views yet — wire on first endpoint.')
```

## Reuse

- Match style of existing plugins (e.g.
  [`plugins/installed/inventory/plugin.py`](../../../plugins/installed/inventory/plugin.py)).
- Follow [`vendor/vibe-skills/language-rules/python.md`](../../../vendor/vibe-skills/language-rules/python.md).
- See [`docs/SKILLS.md`](../../../docs/SKILLS.md) for the full skill catalog.
