"""One reading of an app's settings schema (v0.173.0).

What a value must be, how a typed-in value becomes one, which settings are
secret and which an agent may change. The dashboard's settings save, its panel
fields, `Plugin.set_config`, Linda's `settings.*` tools and the MCP edge's
argument check all read it; until v0.173.0 each had its own partial copy.

The schema is the JSON Schema an app returns from `get_config_schema()`, plus
the one its settings panel renders. Keywords read here: `type` (string,
boolean, integer, number, array, object), `enum`, `minimum`, `maximum`,
`minLength`, `maxLength`, `items`, `format: password`, and `x-agent-writable`.

`x-agent-writable: false` on a property, or on the whole schema, keeps an agent
from changing it: only the merchant can, on the dashboard. A secret
(`format: password`) is not agent-writable unless its property says so. When
both schemas declare a key, either one can make it secret or merchant-only.
A key no schema declares is judged by its name: one that reads like a secret or
an address the store sends to (`gemini_base_url`) is the merchant's.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# What the AI settings page shows for a stored key; posting it back keeps the key.
PASSWORD_MASK = '********'

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    'string': str,
    'integer': int,
    'number': (int, float),
    'boolean': bool,
    'array': list,
    'object': dict,
}
_TRUE = frozenset({'on', 'true', '1', 'yes'})
_FALSE = frozenset({'off', 'false', '0', 'no', ''})
# Names that suggest a secret, for a value no schema describes (an undeclared
# key, or a key inside a stored dict): an API token is a `token` inside a list.
_SECRET_NAMES = ('api_key', 'secret', 'password', 'token', 'webhook_secret')
# Names of an address the store sends data, or a key, to. ai_assistant reads
# `<provider>_base_url` for every provider and declares ten of them: an agent
# that could write `gemini_base_url` could send the store's Gemini key anywhere.
_ADDRESS_SUFFIXES = ('_url', '_endpoint', '_host')


class SettingError(ValueError):
    """A value that does not fit its setting. The message says why."""


def properties(plugin) -> dict[str, dict]:
    """Every setting `plugin` declares, keyed by name.

    Its config schema first, then any its settings panel adds. A schema-level
    `x-agent-writable` applies to each of its properties that sets none. A key
    both declare reads as the config schema says, kept secret or merchant-only
    when either one says so.
    """
    from plugins.registry import app_registry  # noqa: PLC0415

    schemas = [plugin.get_config_schema() or {}]
    panel = app_registry.settings_panel(plugin.name)
    if panel is not None:
        schemas.append(panel.schema or {})
    props: dict[str, dict] = {}
    for schema in schemas:
        for key, declared in (schema.get('properties') or {}).items():
            if not isinstance(declared, dict):
                continue
            if 'x-agent-writable' in schema and 'x-agent-writable' not in declared:
                declared = {**declared, 'x-agent-writable': schema['x-agent-writable']}  # noqa: PLW2901
            props[key] = _stricter(props[key], declared) if key in props else declared
    return props


def _stricter(first: dict, second: dict) -> dict:
    merged = dict(first)
    if second.get('format') == 'password':
        merged['format'] = 'password'
    if second.get('x-agent-writable') is False:
        merged['x-agent-writable'] = False
    return merged


def is_secret(key: str, prop: dict | None) -> bool:
    """A setting the dashboard never shows again: `format: password`, or an API
    key. An undeclared key (`prop` None) is judged by its name."""
    if prop is None:
        return looks_secret(key)
    return prop.get('format') == 'password' or key == 'api_key' or key.endswith('_api_key')


def looks_secret(name: Any) -> bool:
    return any(s in str(name).lower() for s in _SECRET_NAMES)


def looks_like_address(name: Any) -> bool:
    return str(name).lower().endswith(_ADDRESS_SUFFIXES)


def agent_writable(key: str, prop: dict | None) -> bool:
    """Whether an agent may change this setting (with the merchant's yes)."""
    if prop is not None and 'x-agent-writable' in prop:
        return bool(prop['x-agent-writable'])
    if prop is None and looks_like_address(key):
        return False
    return not is_secret(key, prop)


def redact(value: Any, secret: bool = False) -> Any:
    """`value` with every secret inside it redacted, nested ones too."""
    if isinstance(value, dict):
        return {k: redact(v, secret or looks_secret(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if not secret:
        return value
    if isinstance(value, str) and len(value) > 4:
        return value[:2] + '…(redacted)…' + value[-2:]
    return '(redacted)'


def known_type(prop: dict) -> bool:
    return prop.get('type') in _JSON_TYPES


def field_kind(prop: dict) -> str:
    """How the dashboard renders a setting: password, enum, or its type."""
    if prop.get('format') == 'password':
        return 'password'
    return 'enum' if 'enum' in prop else prop.get('type', 'string')


def coerce(prop: dict, raw: Any) -> Any:
    """`raw` as the type `prop` declares.

    A string is read the way a form or an agent writes it: "on"/"true"/"1"/"yes"
    or "off"/"false"/"0"/"no"/"" for a boolean, digits for an integer, a finite
    number, and for a list JSON (`[60, 1440]`) or comma-separated items. A value
    that is not a string passes as it is (list items are still read). Raises
    `SettingError` when a string cannot be read; `validate` checks the rest.
    """
    ptype = prop.get('type')
    if ptype == 'array':
        items = prop.get('items') if isinstance(prop.get('items'), dict) else {}
        if isinstance(raw, str):
            raw = _list_from_text(raw)
        if isinstance(raw, list):
            return [coerce(items, item) for item in raw]
        return raw
    reader = _READERS.get(ptype)
    if reader is None or not isinstance(raw, str):
        return raw
    return reader(raw.strip())


def _boolean(text: str) -> bool:
    if text.lower() in _TRUE:
        return True
    if text.lower() in _FALSE:
        return False
    raise SettingError('must be on or off (true or false)')


def _integer(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise SettingError('must be a whole number') from None


def _number(text: str) -> float:
    try:
        number = float(text)
    except ValueError:
        raise SettingError('must be a number') from None
    if not math.isfinite(number):
        raise SettingError('must be a number')
    return number


def _object(text: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError:
        raise SettingError('must be a JSON object') from None
    if not isinstance(value, dict):
        raise SettingError('must be a JSON object')
    return value


_READERS = {'boolean': _boolean, 'integer': _integer, 'number': _number, 'object': _object}


def list_text(value: list) -> str:
    """A stored list as the panel's text box shows it: `60, 1440`, or JSON when
    an item would not come back through the commas (a comma in it, a dict)."""

    def plain(item: Any) -> bool:
        if isinstance(item, bool):
            return False
        if isinstance(item, (int, float)):
            return True
        return (
            isinstance(item, str)
            and item == item.strip()
            and item
            and ',' not in item
            and item[0] != '['
        )

    return ', '.join(str(v) for v in value) if all(plain(v) for v in value) else json.dumps(value)


def _list_from_text(text: str) -> list:
    text = text.strip()
    if text.startswith('['):
        try:
            value = json.loads(text)
        except ValueError:
            raise SettingError('must be a list, like [1, 2] or 1, 2') from None
        if not isinstance(value, list):
            raise SettingError('must be a list, like [1, 2] or 1, 2')
        return value
    return [part.strip() for part in text.split(',') if part.strip()]


def validate(name: str, value: Any, spec: dict) -> str:  # noqa: PLR0911
    """'' when `value` fits `spec`, else why not (`'limit' must be integer`).

    A JSON-Schema subset: type, enum, minimum/maximum, minLength/maxLength. It
    checks the value itself; `errors` also checks a list's items.
    """
    t = spec.get('type')
    py = _JSON_TYPES.get(t)
    if py is not None:
        # bool is a subclass of int — a boolean is not a valid number.
        if t in ('integer', 'number') and isinstance(value, bool):
            return f'{name!r} must be {t}'
        if not isinstance(value, py):
            return f'{name!r} must be {t}'
    if 'enum' in spec and value not in spec['enum']:
        return f'{name!r} must be one of {spec["enum"]}'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in spec and value < spec['minimum']:
            return f'{name!r} must be >= {spec["minimum"]}'
        if 'maximum' in spec and value > spec['maximum']:
            return f'{name!r} must be <= {spec["maximum"]}'
    if isinstance(value, str):
        if 'minLength' in spec and len(value) < spec['minLength']:
            return f'{name!r} is too short'
        if 'maxLength' in spec and len(value) > spec['maxLength']:
            return f'{name!r} is too long'
    return ''


def errors(key: str, prop: dict, value: Any) -> list[str]:
    """Why `value` does not fit setting `key`; empty when it does. None clears
    a setting and always fits."""
    if value is None:
        return []
    problem = validate(key, value, prop)
    if problem:
        return [problem]
    items = prop.get('items')
    if prop.get('type') == 'array' and isinstance(items, dict) and isinstance(value, list):
        return [p for i, item in enumerate(value) if (p := validate(f'{key}[{i}]', item, items))]
    return []


def clean(key: str, prop: dict, raw: Any) -> Any:
    """`raw` read and checked against setting `key`; raises `SettingError`."""
    try:
        value = coerce(prop, raw)
    except SettingError as e:
        raise SettingError(f'{key!r} {e}') from None
    problems = errors(key, prop, value)
    if problems:
        raise SettingError(problems[0])
    return value


def report(plugin, key: str, value: Any) -> None:
    """Log a value about to be stored that its declared setting would refuse.

    Called by `Plugin.set_config`, which still stores it: this release only
    reports. The value itself is never logged (it may be a secret), and a
    schema that cannot be read never stops the write.
    """
    try:
        prop = properties(plugin).get(key)
        problems = errors(key, prop, value) if prop is not None and known_type(prop) else []
    except Exception:  # noqa: BLE001
        logger.debug('settings: could not read %s schema', plugin.name, exc_info=True)
        return
    for problem in problems:
        logger.warning('settings: %s.%s: %s (stored as given)', plugin.name, key, problem)


# ── One settings form for any target (v0.185.0) ─────────────────────────────
# A target is anything with `get_config() -> dict` and `set_config(key, value)`:
# an app, or a theme. The dashboard's app settings, the theme settings page and
# Linda's settings tools all read and write through these.


def form_fields(target, schema: dict) -> list[dict]:
    """The fields a settings form renders for `schema`, filled from `target`'s
    stored settings (the shape `admin_dashboard/plugin_settings.html` reads)."""
    config = target.get_config()
    fields = []
    for key, prop in (schema.get('properties') or {}).items():
        kind = field_kind(prop)
        value = config.get(key, prop.get('default', ''))
        if is_secret(key, prop):
            # A secret renders write-only: it never echoes the stored value into
            # page source, and a blank submit keeps it (see `save_posted`). Carry
            # a boolean so the form can say whether a secret is already stored.
            value = ''
        elif kind == 'boolean':
            value = bool(value)
        elif kind == 'array' and isinstance(value, list):
            # A list edits as comma-separated text; the save reads it back.
            value = list_text(value)
        fields.append(
            {
                'key': key,
                'title': prop.get('title') or key.replace('_', ' ').title(),
                'description': prop.get('description', ''),
                'kind': kind,
                'enum': prop.get('enum') or [],
                'value': value,
                'has_value': bool(config.get(key)),
            }
        )
    return fields


def save_posted(target, schema: dict, post, *, ajax: bool) -> list[str]:
    """Store the settings a posted form carries; return the keys it saved.

    Each declared key is read as its schema type. An unticked box submits
    nothing, so an absent boolean is saved as off only when the form rendered
    it: every AJAX panel form renders all of its booleans (`ajax`), and a regular
    post names its boxes in `_booleans`. A page that posts only some keys names
    none, so it never switches off a box it did not show. A blank or masked
    secret means "leave it unchanged", and a value its type cannot be read as is
    skipped.
    """
    saved: list[str] = []
    shown_booleans = post.getlist('_booleans')
    for key, prop in (schema.get('properties') or {}).items():
        if key not in post:
            if prop.get('type') == 'boolean' and (ajax or key in shown_booleans):
                target.set_config(key, False)
                saved.append(key)
            continue
        raw = post[key]
        if is_secret(key, prop) and (raw or '').strip() in ('', PASSWORD_MASK):
            continue
        try:
            value = coerce(prop, raw)
        except SettingError:
            continue
        target.set_config(key, value)
        saved.append(key)
    return saved


_DESCRIBED_KEYWORDS = {
    'enum': 'enum',
    'minimum': 'minimum',
    'maximum': 'maximum',
    'minLength': 'min_length',
    'maxLength': 'max_length',
    'items': 'items',
}


def describe_settings(props: dict, config: dict) -> list[dict]:
    """Each setting in `props` as an agent reads it: its type, allowed values,
    default and current value (secrets redacted), and whether an agent may
    change it."""
    entries = []
    for key, prop in props.items():
        secret = is_secret(key, prop)
        entry = {
            'key': key,
            'title': prop.get('title') or key.replace('_', ' ').capitalize(),
            'description': prop.get('description', ''),
            'type': prop.get('type', 'string'),
            'default': redact(prop.get('default'), secret),
            'value': redact(config.get(key, prop.get('default')), secret),
            'stored': key in config,
            'secret': secret,
            'agent_writable': agent_writable(key, prop),
        }
        entry.update({out: prop[kw] for kw, out in _DESCRIBED_KEYWORDS.items() if kw in prop})
        entries.append(entry)
    return entries
