"""Settings → General → Translations: the translation work, and its editor.

Which content can be translated comes from the apps that own it
(`core.i18n.services.translatable_specs`). A person's save is reviewed and shown to
shoppers; an AI draft waits for review (`drafting.py`).
"""

# ruff: noqa: PLC0415 — sibling and model imports are lazy (load-order safe).
from __future__ import annotations

from django.contrib import messages
from django.http import Http404

from core.authz import enforce, require_capability
from morpheus.app import dashboard_trail
from morpheus.app.views import redirect, render, staff_member_required

INDEX_URL = '/dashboard/apps/localization/translations/'
_STATUS_LABELS = {'missing': 'Missing', 'draft': 'Draft', 'translated': 'Translated'}


def editor_url(kind: str, pk, language: str) -> str:
    return f'{INDEX_URL}{kind}/{pk}/{language}/'


def _label(spec: dict, obj) -> str:
    from core.i18n.services import source_values

    values = source_values(obj, spec)
    first = next(iter(spec['fields']), '')
    return (values.get(first) or str(obj))[:120]


def _choice(value: str, allowed, default: str) -> str:
    return value if value in allowed else default


@staff_member_required
@require_capability('system.read')
def translations_index(request):
    """Per language and kind: how much is translated; then the objects, filtered."""
    from core.i18n import services as i18n
    from plugins.installed.admin_dashboard.views_split._shared import paginate_and_sort
    from plugins.installed.localization.drafting import BATCH_LIMIT, DraftError, last_run

    languages = i18n.target_languages()
    specs = i18n.translatable_specs()
    trail = dashboard_trail('Settings', '/dashboard/settings/', 'Translations')
    if not languages:
        return render(
            request,
            'localization/translations.html',
            {
                'single_language': True,
                'default_name': i18n.language_name(i18n.default_language()),
                'breadcrumb_trail': trail,
            },
        )
    kinds = {s['key']: s for s in specs}
    kind = _choice(request.GET.get('kind') or request.POST.get('kind') or '', kinds, '')
    kind = kind or (specs[0]['key'] if specs else '')
    language = _choice(
        request.GET.get('language') or request.POST.get('language') or '', languages, languages[0]
    )

    if request.method == 'POST':
        if (denied := enforce(request, 'system.write')) is not None:
            return denied
        if request.POST.get('action') == 'draft_missing' and kind:
            try:
                queued = i18n_queue(kind, language)
            except DraftError as e:
                messages.error(request, str(e))
            else:
                if queued:
                    messages.success(
                        request,
                        f'{queued} queued for an AI draft. Drafts are not shown to shoppers '
                        'until you review and save them.',
                    )
                else:
                    messages.info(request, 'Nothing is missing a translation here.')
        return redirect(f'{INDEX_URL}?kind={kind}&language={language}')

    summary = []
    for code in languages:
        for spec in specs:
            row = i18n.status_summary(spec, code)
            row['last_run'] = last_run(spec['key'], code)
            summary.append(row)

    status = _choice(request.GET.get('status') or '', _STATUS_LABELS, '')
    rows, paging_ctx = [], {}
    spec = kinds.get(kind)
    if spec is not None:
        statuses = i18n.object_statuses(spec, language)
        ids = [pk for pk, s in statuses.items() if not status or s == status]
        first = next(iter(spec['fields']))
        qs = spec['model']._base_manager.filter(pk__in=ids)
        page, paging_ctx = paginate_and_sort(
            request, qs, default_sort=first, allowed_sorts=(first,)
        )
        rows = [
            {
                'label': _label(spec, obj),
                'status': statuses.get(str(obj.pk), 'missing'),
                'status_label': _STATUS_LABELS.get(statuses.get(str(obj.pk), 'missing')),
                'edit_url': editor_url(kind, obj.pk, language),
            }
            for obj in page.object_list
        ]
    return render(
        request,
        'localization/translations.html',
        {
            **paging_ctx,
            'summary': summary,
            'languages': [(code, i18n.language_name(code)) for code in languages],
            'kinds': [(s['key'], str(s.get('label') or s['key'])) for s in specs],
            'kind': kind,
            'language': language,
            'status': status,
            'status_choices': list(_STATUS_LABELS.items()),
            'rows': rows,
            'batch_limit': BATCH_LIMIT,
            'default_name': i18n.language_name(i18n.default_language()),
            'breadcrumb_trail': trail,
        },
    )


def i18n_queue(kind: str, language: str, object_ids=None) -> int:
    from plugins.installed.localization.drafting import queue_drafts

    return queue_drafts(kind, language, object_ids)['queued']


@staff_member_required
@require_capability('system.read')
def translation_edit(request, kind: str, pk: str, language: str):
    """One object in one language: the source beside its translation."""
    from django.core.exceptions import ValidationError

    from core.i18n import services as i18n
    from core.i18n.models import Translation
    from plugins.installed.localization.drafting import DraftError, last_run

    spec = i18n.spec_by_key(kind)
    if spec is None or language not in i18n.target_languages():
        raise Http404('No such translation.')
    try:
        obj = spec['model']._base_manager.filter(pk=pk).first()
    except (ValidationError, ValueError) as e:
        raise Http404('No such object.') from e
    if obj is None:
        raise Http404('No such object.')
    rows = {
        r.field: r
        for r in Translation.objects.filter(
            content_type=i18n._ct(obj),
            object_id=str(obj.pk),
            language_code=language,
            field__in=list(spec['fields']),
        )
    }
    here = editor_url(kind, obj.pk, language)

    if request.method == 'POST':
        if (denied := enforce(request, 'system.write')) is not None:
            return denied
        if request.POST.get('action') == 'draft':
            try:
                queued = i18n_queue(kind, language, [str(obj.pk)])
            except DraftError as e:
                messages.error(request, str(e))
            else:
                if queued:
                    messages.success(request, 'An AI draft was requested for this item.')
            return redirect(here)
        for field, field_kind in spec['fields'].items():
            value = (request.POST.get(f'f-{field}') or '').replace('\r\n', '\n').strip()
            if not value:
                i18n.delete_translation(obj, field, language)
                continue
            row = rows.get(field)
            # Saving a draft as it stands publishes the AI's text; it keeps saying so.
            machine = bool(
                row
                and row.is_machine_translated
                and i18n.clean_value(type(obj), field, field_kind, value) == row.value
            )
            i18n.set_translation(obj, field, language, value, machine_translated=machine)
        messages.success(request, 'Translation saved.')
        return redirect(here)

    source = i18n.source_values(obj, spec)
    fields = [
        {
            'name': field,
            'label': field.replace('_', ' ').capitalize(),
            'html': field_kind == i18n.FIELD_HTML,
            'source': source.get(field, ''),
            'value': rows[field].value if field in rows else '',
            'draft': field in rows and not rows[field].reviewed,
        }
        for field, field_kind in spec['fields'].items()
    ]
    back = f'{INDEX_URL}?kind={kind}&language={language}'
    return render(
        request,
        'localization/translation_edit.html',
        {
            'spec_label': str(spec.get('label') or kind),
            'object_label': _label(spec, obj),
            'language_name': i18n.language_name(language),
            'default_name': i18n.language_name(i18n.default_language()),
            'fields': fields,
            'has_draft': any(f['draft'] for f in fields),
            'last_run': last_run(kind, language),
            'back_url': back,
            'breadcrumb_trail': dashboard_trail(
                'Settings',
                '/dashboard/settings/',
                {'label': 'Translations', 'url': back},
                _label(spec, obj)[:40],
            ),
        },
    )
