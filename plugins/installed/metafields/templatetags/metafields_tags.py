"""``{% metafields_panel obj %}`` — auto-render a sidebar of custom fields.

Drop this anywhere an admin edit form needs a "Custom fields" panel:

    {% load metafields_tags %}
    ...
    <aside class="card card-padded">
      {% metafields_panel product %}
    </aside>

The tag reads every Metafield row attached to ``obj`` (via the generic FK),
groups by namespace, and renders an input per row matching its declared
``value_type`` — string/text → input or textarea, integer → number, boolean
→ checkbox, json/file_id → minimal raw view. Empty namespaces are hidden.

This is the Vendure-style "custom fields auto-render in admin" capability
adapted to Morpheus's GenericForeignKey-based metafields. Plugins that want
their fields editable inline now just write metafield rows; the admin form
panel appears automatically.

Save handler: POSTs to /dashboard/apps/metafields/save/?ct=<content_type_id>&id=<object_id>
with one form field per metafield, encoded by the partial. JSON values
edit as a multiline textarea.
"""

from __future__ import annotations

from django import template
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe

from plugins.installed.metafields.models import Metafield

register = template.Library()


_INPUT_BY_TYPE = {
    'string': 'text',
    'integer': 'number',
    'decimal': 'text',  # use text + step="any" to allow Decimal(...) values
    'boolean': 'checkbox',
    'text': 'textarea',
    'json': 'textarea',
    'file_id': 'text',  # for now — future: media picker
    'datetime': 'datetime-local',
}


def _input_for(mf: Metafield, name: str) -> str:
    """Render the appropriate HTML control for one metafield's value_type."""
    from django.utils.html import escape

    raw_value = mf.value or ''
    vt = (mf.value_type or 'string').lower()
    control = _INPUT_BY_TYPE.get(vt, 'text')

    if vt == 'boolean':
        checked = 'checked' if raw_value.lower() in ('true', '1', 'yes', 'on') else ''
        return (
            f'<label style="display:inline-flex; align-items:center; gap:.4rem;">'
            f'<input type="checkbox" name="{escape(name)}" value="true" {checked}>'
            f'<span style="font-size:.85rem;">Enabled</span>'
            f'</label>'
        )
    if control == 'textarea':
        return (
            f'<textarea name="{escape(name)}" rows="3" class="input" '
            f'style="font-family: ui-monospace, SFMono-Regular, Menlo, monospace; '
            f'font-size: .8rem;">{escape(raw_value)}</textarea>'
        )
    if vt == 'integer':
        return f'<input type="number" step="1" name="{escape(name)}" value="{escape(raw_value)}" class="input">'
    return f'<input type="text" name="{escape(name)}" value="{escape(raw_value)}" class="input">'


@register.simple_tag(takes_context=True)
def metafields_panel(context, obj, *, namespace: str = '') -> str:
    """Render an editable panel for ``obj``'s metafields, grouped by namespace.

    If ``namespace`` is provided, only rows with that namespace are shown
    (useful when a plugin wants its own scoped panel rather than the catch-all).
    """
    if obj is None or not getattr(obj, 'pk', None):
        return ''
    try:
        ct = ContentType.objects.get_for_model(type(obj))
    except Exception:  # noqa: BLE001
        return ''
    qs = Metafield.objects.filter(content_type=ct, object_id=str(obj.pk))
    if namespace:
        qs = qs.filter(namespace=namespace)
    rows = list(qs.order_by('namespace', 'key'))
    if not rows:
        return mark_safe(
            '<p class="meta" style="margin:0;">'
            'No custom fields yet. Plugins write metafields via '
            '<code>Metafield.objects.set(...)</code>; they auto-appear here.'
            '</p>'
        )

    # Group by namespace.
    by_ns: dict[str, list[Metafield]] = {}
    for r in rows:
        by_ns.setdefault(r.namespace, []).append(r)

    save_url = f'/dashboard/apps/metafields/save/?ct={ct.id}&id={obj.pk}'
    request = context.get('request')
    csrf_token = ''
    if request is not None:
        from django.middleware.csrf import get_token

        csrf_token = get_token(request)

    parts: list[str] = []
    parts.append(
        f'<form method="post" action="{save_url}" '
        'style="display: flex; flex-direction: column; gap: 1rem;">'
        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">'
    )
    for ns, fields in by_ns.items():
        parts.append(
            f'<div><p class="eyebrow" style="margin:0 0 .35rem;">{ns}</p>'
            '<div style="display: grid; gap: .65rem;">'
        )
        for mf in fields:
            field_name = f'mf__{mf.namespace}__{mf.key}'
            parts.append(
                f'<label class="block"><span class="block text-meta" '
                'style="margin-bottom: .25rem; font-size: .75rem;">'
                f'{mf.key}<span style="opacity:.5; margin-left:.4rem;">'
                f'({mf.value_type or "string"})</span></span>'
                f'{_input_for(mf, field_name)}</label>'
            )
        parts.append('</div></div>')
    parts.append(
        '<div style="display:flex; gap:.4rem;">'
        '<button type="submit" class="btn btn-primary text-xs">Save fields</button>'
        '</div></form>'
    )
    return mark_safe('\n'.join(parts))  # noqa: S308
