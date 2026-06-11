"""CMS template tags — `{% cms_block "key" %}` and `{% cms_menu "key" %}`."""

from __future__ import annotations

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def cms_block(context, key: str):
    from plugins.installed.cms.services import render_block

    block = render_block(key)
    if block is None:
        return ''
    try:
        return render_to_string('cms/_block.html', {'block': block}, request=context.get('request'))
    except Exception:  # noqa: BLE001
        from django.utils.html import escape

        return mark_safe(escape(block.get('body', '')))  # noqa: S308


@register.simple_tag(takes_context=True)
def cms_menu(context, key: str):
    from plugins.installed.cms.services import get_menu

    menu = get_menu(key)
    if menu is None:
        return ''
    return render_to_string('cms/_menu.html', {'menu': menu}, request=context.get('request'))


@register.simple_tag(takes_context=True)
def cms_form(context, key: str):
    from plugins.installed.cms.models import Form

    form = Form.objects.filter(key=key, is_active=True).first()
    if form is None:
        return ''
    return render_to_string('cms/_form.html', {'form': form}, request=context.get('request'))


@register.simple_tag(takes_context=True)
def render_page_sections(context, page):
    """Render every visible PageSection on a page, in sort order.

    Returns the merged HTML so the calling template can drop the result
    inline. If the page has no sections (or sections aren't installed),
    returns an empty string and the caller falls through to legacy
    `page.body` rendering.
    """
    from themes.sections import section_registry

    try:
        rows = list(page.sections.filter(is_visible=True).order_by('sort_order', 'created_at'))
    except Exception:  # noqa: BLE001 — page may not have a sections related manager
        return ''
    if not rows:
        return ''
    out: list[str] = []
    request = context.get('request')
    for row in rows:
        section = section_registry.get(row.section_id)
        if section is None:
            # Stale section_id — render a tiny placeholder in DEBUG only.
            from django.conf import settings as dj_settings

            if dj_settings.DEBUG:
                out.append(
                    f'<!-- missing section "{row.section_id}" -->\n'
                    f'<div style="padding:1rem; background:#fde7e9; color:#b3261e; '
                    f'font-family:monospace; font-size:.85rem;">'
                    f'Missing section: <code>{row.section_id}</code></div>'
                )
            continue
        try:
            ctx = section.render_context(page=page, settings=row.settings or {})
            out.append(render_to_string(section.template, ctx, request=request))
        except Exception as exc:  # noqa: BLE001 — never break the page on one bad section
            from django.conf import settings as dj_settings

            if dj_settings.DEBUG:
                out.append(
                    f'<!-- section "{row.section_id}" failed: {exc} -->\n'
                    f'<div style="padding:1rem; background:#fde7e9; color:#b3261e;">'
                    f'Section render error: {exc}</div>'
                )
    return mark_safe(''.join(out))  # noqa: S308
