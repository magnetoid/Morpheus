"""Extra checkout fields, declared by the apps that own them.

A checkout form asks for what the apps put on CHECKOUT_FIELDS: an order note, a gift
message and the terms tick (orders), a newsletter opt-in (newsletter). `{% checkout_fields %}`
(core/templatetags/morph.py) renders them inside both checkout forms of every theme, as
inputs named ``cf_<key>``. The views pass those to GraphQL ``completeOrder(checkoutFields:)``,
which calls `clean()`: a key no app declared is dropped, text is cut to its length, and a
missing required answer refuses the order, so a headless checkout cannot skip the terms
either. The answers are stored in ``order.metadata['checkout_fields']`` and each owner acts
on its own (ORDER_PLACED). A switched-off app declares nothing, so its field leaves every
form with it.
"""

from __future__ import annotations

import logging
import re

from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from core.hooks import MorpheusEvents, hook_registry

logger = logging.getLogger(__name__)

PREFIX = 'cf_'
KINDS = ('checkbox', 'text', 'textarea')
DEFAULT_MAX_LENGTH = 500
MAX_LENGTH = 2000
_KEY = re.compile(r'^[a-z][a-z0-9_]{0,39}$')
_TICKED = ('1', 'on', 'true', 'yes')
_BORDER = 'border:1px solid var(--rule, #d4d4d4); border-radius:6px;'


def _link(url) -> str:
    """A link the form may print: http(s) or a path on this site, never ``//host``."""
    url = str(url or '').strip()
    if url.startswith(('https://', 'http://')) or (
        url.startswith('/') and not url.startswith('//')
    ):
        return url
    return ''


def _normalise(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    key = str(raw.get('key') or '')
    label = str(raw.get('label') or '').strip()
    if not _KEY.match(key) or not label:
        return None
    kind = raw.get('kind') if raw.get('kind') in KINDS else 'text'
    try:
        max_length = int(raw.get('max_length') or DEFAULT_MAX_LENGTH)
    except (TypeError, ValueError):
        max_length = DEFAULT_MAX_LENGTH
    try:
        order = int(raw.get('order') or 50)
    except (TypeError, ValueError):
        order = 50
    link_url = _link(raw.get('link_url'))
    return {
        'key': key,
        'label': label,
        'kind': kind,
        'required': bool(raw.get('required')),
        'help': str(raw.get('help') or '').strip(),
        'error': str(raw.get('error') or '').strip(),
        'link_url': link_url,
        'link_text': str(raw.get('link_text') or '').strip() if link_url else '',
        'max_length': max(1, min(max_length, MAX_LENGTH)),
        'order': order,
    }


def fields(*, user=None) -> list[dict]:
    """The fields the apps ask for this shopper, in order; [] when none answer."""
    try:
        raw = hook_registry.filter(MorpheusEvents.CHECKOUT_FIELDS, [], user=user)
    except Exception:  # noqa: BLE001 — a broken app never breaks the checkout
        logger.exception('checkout fields: could not collect them')
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        field = _normalise(item)
        if field is None or field['key'] in seen:
            continue
        seen.add(field['key'])
        out.append(field)
    out.sort(key=lambda f: f['order'])
    return out


def has_required(*, user=None) -> bool:
    """Whether the checkout asks for an answer a wallet sheet cannot give."""
    return any(f['required'] for f in fields(user=user))


def from_post(post) -> dict:
    """The ``cf_<key>`` inputs of a posted checkout form, by key."""
    return {k[len(PREFIX) :]: v for k, v in post.items() if k.startswith(PREFIX)}


def _answer(field: dict, raw):
    if field['kind'] == 'checkbox':
        return raw is True or str(raw or '').strip().lower() in _TICKED
    return raw.strip()[: field['max_length']] if isinstance(raw, str) else ''


def clean(values, *, user=None) -> tuple[dict, list[str]]:
    """The answers to keep, and why the order cannot be placed (empty when it can)."""
    values = values if isinstance(values, dict) else {}
    cleaned: dict = {}
    errors: list[str] = []
    for field in fields(user=user):
        answer = _answer(field, values.get(field['key']))
        if answer:
            cleaned[field['key']] = answer
        elif field['required']:
            errors.append(
                field['error'] or _('Please fill in: %(label)s') % {'label': field['label']}
            )
    return cleaned, errors


def _render_field(field: dict, value) -> str:
    name = PREFIX + field['key']
    link = ''
    if field['link_url']:
        link = format_html(
            ' <a href="{}" target="_blank" rel="noopener" style="text-decoration:underline;">{}</a>',
            field['link_url'],
            field['link_text'] or field['link_url'],
        )
    help_text = (
        format_html(
            '<span style="display:block; font-size:.8rem; opacity:.75; margin-top:.25rem;">{}</span>',
            field['help'],
        )
        if field['help']
        else ''
    )
    if field['kind'] == 'checkbox':
        return format_html(
            '<label style="display:flex; align-items:flex-start; gap:.6rem; margin:0 0 1rem;'
            ' padding:.85rem 1rem; {} font-size:.88rem; line-height:1.4;">'
            '<input type="checkbox" name="{}" value="1"{}{} style="margin-top:.2rem;">'
            '<span>{}{}{}</span></label>',
            mark_safe(_BORDER),  # noqa: S308 — a constant
            name,
            mark_safe(' checked') if _answer(field, value) else '',  # noqa: S308
            mark_safe(' required') if field['required'] else '',  # noqa: S308
            field['label'],
            link,
            help_text,
        )
    optional = (
        ''
        if field['required']
        else format_html(' <span style="opacity:.7;">{}</span>', _('(optional)'))
    )
    text = value if isinstance(value, str) else ''
    if field['kind'] == 'textarea':
        control = format_html(
            '<textarea name="{}" rows="3" maxlength="{}"{} style="width:100%; padding:.75rem; {}">'
            '{}</textarea>',
            name,
            field['max_length'],
            mark_safe(' required') if field['required'] else '',  # noqa: S308
            mark_safe(_BORDER),  # noqa: S308
            text,
        )
    else:
        control = format_html(
            '<input type="text" name="{}" value="{}" maxlength="{}"{} style="width:100%;'
            ' padding:.75rem; {}">',
            name,
            text,
            field['max_length'],
            mark_safe(' required') if field['required'] else '',  # noqa: S308
            mark_safe(_BORDER),  # noqa: S308
        )
    return format_html(
        '<label style="display:block; margin:0 0 1rem;">'
        '<span style="display:block; font-size:.85rem; margin-bottom:.25rem;">{}{}{}</span>'
        '{}{}</label>',
        field['label'],
        optional,
        link,
        control,
        help_text,
    )


def render(context) -> str:
    """The checkout form's extra fields, with what the shopper typed on a re-render."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    found = fields(user=user)
    if not found:
        return ''
    posted = from_post(request.POST) if request is not None and request.method == 'POST' else {}
    return format_html(
        '<div class="checkout-fields">{}</div>',
        mark_safe(''.join(_render_field(f, posted.get(f['key'])) for f in found)),  # noqa: S308
    )
