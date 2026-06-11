"""Private helpers shared by every forms/ module.

Money coercion, the Markdown → HTML rescuer for legacy descriptions,
and the DashboardFormMixin that auto-attaches the ``.input`` class to
text-like widgets so ``{{ field }}`` renders without inline styling.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from morpheus import forms


def _money(amount: str | Decimal | None, currency: str = 'USD'):
    """Return a djmoney `Money` from a raw string, or None if blank."""
    from djmoney.money import Money

    if amount in (None, ''):
        return None
    try:
        return Money(Decimal(str(amount)), currency)
    except (InvalidOperation, TypeError, ValueError):
        return None


_HTML_TAG_RE = re.compile(r'<\w+[\s>]')


def _md_to_html(value: str) -> str:
    """Minimal Markdown → HTML for the subset our LLM produces.

    Inlined here (not imported from core.templatetags.morph) so the form
    doesn't depend on whatever state that module is in. Handles ## / ###
    headings, paragraph blocks, [text](url) links, **bold**, *italic*.
    """
    from django.utils.html import escape as _esc

    def _safe_href(url: str) -> str:
        """Allow http(s), absolute paths, mailto, tel. Block javascript:,
        data:, vbscript:, file:, etc. — anything that could execute on click.
        """
        u = (url or '').strip()
        low = u.lower()
        if low.startswith(('http://', 'https://', '/', 'mailto:', 'tel:')):
            return _esc(u)
        return '#'  # neuter unsafe schemes

    def _inline(text: str) -> str:
        text = re.sub(
            r'\[([^\]]+)\]\(([^)\s]+)\)',
            lambda m: f'<a href="{_safe_href(m.group(2))}">{m.group(1)}</a>',
            text,
        )
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
        return text

    norm = re.sub(r'\n(#{2,3} )', r'\n\n\1', str(value))
    norm = re.sub(r'(#{2,3} [^\n]+)\n(?!#|\n)', r'\1\n\n', norm)
    out = []
    for block in re.split(r'\n\s*\n', norm.strip()):
        b = block.strip()
        if not b:
            continue
        if b.startswith('### '):
            out.append(f'<h3>{_inline(_esc(b[4:].strip()))}</h3>')
        elif b.startswith('## '):
            out.append(f'<h2>{_inline(_esc(b[3:].strip()))}</h2>')
        else:
            esc = _esc(b).replace('\n', '<br>')
            out.append(f'<p>{_inline(esc)}</p>')
    return '\n'.join(out)


def _ensure_html(value: str | None) -> str:
    """Return HTML, converting legacy Markdown when needed.

    The TipTap editor expects HTML, but `populate_descriptions` historically
    wrote Markdown to `Product.{short_description,description}`. We convert
    on read so the editor renders the saved content correctly. Idempotent:
    rows that already look like HTML pass through unchanged.
    """
    if not value:
        return value or ''
    if _HTML_TAG_RE.search(value):
        return value
    return _md_to_html(value)


class DashboardFormMixin:
    """Auto-attach the dashboard's semantic ``.input`` CSS class to every
    widget so `{{ field }}` renders without needing an inline-CSS fallback
    in the template. Inherit from this BEFORE `forms.Form` (or wrap in MRO
    after) and every text/email/number/etc. widget picks up the same look
    as the schema-driven panel widgets.

    Skips checkbox + radio widgets — those use their own dashboard styles.
    """

    _DASHBOARD_INPUT_CLASS = 'input'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for bound in self.visible_fields():
            widget = bound.field.widget
            existing = widget.attrs.get('class', '').split()
            if isinstance(
                widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)
            ):
                continue
            if self._DASHBOARD_INPUT_CLASS not in existing:
                existing.append(self._DASHBOARD_INPUT_CLASS)
                widget.attrs['class'] = ' '.join(existing).strip()
