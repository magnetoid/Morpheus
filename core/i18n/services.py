"""Translation services: the rows, which content is translatable, and what a page may claim.

A `Translation` row holds one field of one object in one language. A row is
**reviewed** when a person wrote or approved its text; an AI draft is not, and a
draft is never shown to a shopper nor counted for a language.

Which content is translatable is answered by the app that owns each model through
the `TRANSLATABLE_CONTENT` filter (`translatable_specs`). A page about one such
object exists in a language only when the object has a reviewed translation there
of every registered field it fills (`content_languages`); the store's default
language always counts. A view showing the object in another language overlays the
reviewed text on the instance (`overlay_translation`), and a `pre_save` receiver
puts the original text back before any save, so a translated instance can never
write its translation into the default-language columns.
"""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger('morpheus.i18n')

FIELD_TEXT = 'text'
FIELD_HTML = 'html'


def _ct(obj_or_model):
    from django.contrib.contenttypes.models import ContentType

    model = obj_or_model if isinstance(obj_or_model, type) else type(obj_or_model)
    return ContentType.objects.get_for_model(model)


# -- languages -----------------------------------------------------------------
def default_language() -> str:
    """The store's default language (`LANGUAGE_CODE`), as `LANGUAGES` names it."""
    from django.conf import settings

    code = (getattr(settings, 'LANGUAGE_CODE', '') or 'en').lower()
    return _configured(code) or code


def store_languages() -> list[str]:
    """Every language the store is served in: the default first.

    These come from the deployment (`MORPHEUS_LANGUAGES` → `settings.LANGUAGES`);
    nothing in the dashboard changes them.
    """
    from django.conf import settings

    codes = [code.lower() for code, _name in (getattr(settings, 'LANGUAGES', None) or [])]
    default = default_language()
    return list(dict.fromkeys([default, *codes]))


def target_languages() -> list[str]:
    """The languages content can be translated into: every store language but the default."""
    default = default_language()
    return [code for code in store_languages() if code != default]


def language_name(code: str) -> str:
    from django.conf import settings

    names = {c.lower(): str(n) for c, n in (getattr(settings, 'LANGUAGES', None) or [])}
    return names.get((code or '').lower(), code)


def _configured(code: str) -> str:
    """`code` as `LANGUAGES` writes it (`sr`, or `en` for `en-us`), else ''."""
    from django.conf import settings

    code = (code or '').lower()
    codes = [c.lower() for c, _name in (getattr(settings, 'LANGUAGES', None) or [])]
    if code in codes:
        return code
    base = code.split('-')[0]
    return next((c for c in codes if c == base or c.split('-')[0] == base), '')


def active_language() -> str:
    """The language of the page being served, as `LANGUAGES` writes it."""
    from django.utils.translation import get_language

    return _configured(get_language() or '') or default_language()


# -- which content is translatable --------------------------------------------
def translatable_specs() -> list[dict]:
    """The registered content kinds (`TRANSLATABLE_CONTENT`), each well formed.

    A disabled app's handler is skipped by the hook bus, so its content leaves
    the registry with it.
    """
    from core.hooks import MorpheusEvents, hook_registry

    try:
        value = hook_registry.filter(MorpheusEvents.TRANSLATABLE_CONTENT, [])
    except Exception:  # noqa: BLE001 — a bad answer must not break a page
        logger.warning('i18n: TRANSLATABLE_CONTENT failed', exc_info=True)
        return []
    specs: list[dict] = []
    seen: set[str] = set()
    for spec in value or []:
        if not isinstance(spec, dict):
            continue
        key, model, fields = spec.get('key'), spec.get('model'), spec.get('fields')
        if not key or key in seen or not isinstance(model, type) or not isinstance(fields, dict):
            continue
        seen.add(key)
        specs.append(spec)
    return specs


def spec_by_key(key: str) -> dict | None:
    return next((s for s in translatable_specs() if s['key'] == key), None)


def spec_for(obj_or_model) -> dict | None:
    """The spec registered for this object's model, or None."""
    if obj_or_model is None or isinstance(obj_or_model, dict):
        return None
    model = obj_or_model if isinstance(obj_or_model, type) else type(obj_or_model)
    meta = getattr(model, '_meta', None)
    if meta is None:
        return None
    concrete = meta.concrete_model
    for spec in translatable_specs():
        if spec['model']._meta.concrete_model is concrete:
            return spec
    return None


def _max_length(model, field: str) -> int | None:
    try:
        return model._meta.get_field(field).max_length
    except Exception:  # noqa: BLE001 — a field the model does not have
        return None


def clean_value(model, field: str, kind: str, value: str) -> str:
    """A translation as it may be stored: sanitised HTML, or plain text cut to its column."""
    from django.utils.html import strip_tags

    value = (value or '').strip()
    if not value:
        return ''
    if kind == FIELD_HTML:
        from core.utils.html import sanitize_richtext

        return (sanitize_richtext(value) or '').strip()
    value = strip_tags(value).strip()
    limit = _max_length(model, field)
    if limit and len(value) > limit:
        value = value[:limit].rstrip()
    return value


# -- the object's own text ----------------------------------------------------
def source_values(obj, spec: dict | None = None) -> dict[str, str]:
    """The object's registered fields in the default language.

    Reads the originals an overlay set aside, and loads deferred fields in one
    query rather than one per field.
    """
    spec = spec or spec_for(obj)
    if spec is None:
        return {}
    originals = obj.__dict__.get('_morph_untranslated') or {}
    fields = list(spec['fields'])
    deferred = set(obj.get_deferred_fields()) if hasattr(obj, 'get_deferred_fields') else set()
    out: dict[str, str] = {}
    missing: list[str] = []
    for field in fields:
        if field in originals:
            out[field] = originals[field] or ''
        elif field in deferred:
            missing.append(field)
        else:
            out[field] = getattr(obj, field, '') or ''
    if missing and obj.pk is not None:
        row = type(obj)._base_manager.filter(pk=obj.pk).values(*missing).first() or {}
        out.update({field: row.get(field) or '' for field in missing})
    return {field: str(out.get(field) or '') for field in fields}


def filled_fields(values: dict[str, str]) -> set[str]:
    return {field for field, value in values.items() if (value or '').strip()}


def reviewed_values(obj_or_objs, language: str) -> dict[str, dict[str, str]]:
    """`{pk: {field: value}}` of the reviewed, non-empty translations in `language`.

    One query for a list of objects of one model. Drafts are left out.
    """
    from core.i18n.models import Translation

    objs = list(obj_or_objs) if isinstance(obj_or_objs, (list, tuple, set)) else [obj_or_objs]
    objs = [o for o in objs if o is not None and getattr(o, 'pk', None) is not None]
    if not objs or not language:
        return {}
    spec = spec_for(objs[0])
    qs = Translation.objects.filter(
        content_type=_ct(objs[0]),
        object_id__in={str(o.pk) for o in objs},
        language_code=language,
        reviewed=True,
    )
    if spec is not None:
        qs = qs.filter(field__in=list(spec['fields']))
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for object_id, field, value in qs.values_list('object_id', 'field', 'value'):
        if (value or '').strip():
            out[object_id][field] = value
    return dict(out)


def _applies(spec: dict, obj) -> bool:
    check = spec.get('applies')
    if not callable(check):
        return True
    try:
        return bool(check(obj))
    except Exception:  # noqa: BLE001 — unsure means the object stays in its own language
        logger.warning('i18n: applies() failed for %s', spec.get('key'), exc_info=True)
        return False


def content_languages(obj) -> set[str] | None:
    """The languages a page about `obj` exists in, or None when no app registered it.

    None also for an object its owner's `applies` leaves out (a CMS page built from
    sections). The default language always counts. Another language counts when every
    registered field the object fills has a reviewed, non-empty translation there.
    """
    spec = spec_for(obj)
    if spec is None or getattr(obj, 'pk', None) is None or not _applies(spec, obj):
        return None
    languages = {default_language()}
    targets = target_languages()
    if not targets:
        return languages
    needed = filled_fields(source_values(obj, spec))
    from core.i18n.models import Translation

    have: dict[str, set[str]] = defaultdict(set)
    rows = Translation.objects.filter(
        content_type=_ct(obj),
        object_id=str(obj.pk),
        language_code__in=targets,
        reviewed=True,
        field__in=list(needed) or ['-'],
    ).values_list('language_code', 'field', 'value')
    for language, field, value in rows:
        if (value or '').strip():
            have[language].add(field)
    languages.update(lang for lang in targets if needed <= have[lang])
    return languages


# -- showing a translation ----------------------------------------------------
def overlay(obj, values: dict[str, str], language: str) -> None:
    """Show `values` on the in-memory instance; the originals go to `_morph_untranslated`."""
    if not values:
        return
    originals = obj.__dict__.get('_morph_untranslated') or {}
    spec = spec_for(obj)
    source = source_values(obj, spec) if spec is not None else {}
    for field, value in values.items():
        if field not in originals:
            originals[field] = source.get(field, getattr(obj, field, ''))
        setattr(obj, field, value)
    obj.__dict__['_morph_untranslated'] = originals
    obj.__dict__['_morph_translated'] = language


def overlay_translation(obj_or_objs, language: str = ''):
    """Overlay the reviewed translation on each object complete in `language`.

    `language` defaults to the page's. Nothing happens in the default language, for
    an unregistered model, or for an object that is not fully translated (it is
    shown as it is). One translation query per list. Returns its argument.
    """
    language = language or active_language()
    if not obj_or_objs or language == default_language():
        return obj_or_objs
    objs = list(obj_or_objs) if isinstance(obj_or_objs, (list, tuple)) else [obj_or_objs]
    by_model: dict[type, list] = defaultdict(list)
    for obj in objs:
        if obj is not None and not isinstance(obj, dict) and spec_for(obj) is not None:
            by_model[type(obj)._meta.concrete_model].append(obj)
    for group in by_model.values():
        spec = spec_for(group[0])
        values = reviewed_values(group, language)
        for obj in group:
            got = values.get(str(obj.pk)) or {}
            if not got or not _applies(spec, obj):
                continue
            source = source_values(obj, spec)
            needed = filled_fields(source)
            if not needed or not needed <= set(got):
                continue
            overlay(obj, {field: got[field] for field in needed}, language)
    return obj_or_objs


def restore_untranslated(sender, instance, **kwargs) -> None:
    """`pre_save`, every model: put the default-language text back before a save.

    A view shows a translation on the instance it renders; a later save of that
    instance (a `PRODUCT_VIEWED` subscriber, a form in the same request) would
    otherwise write the Serbian text into the English columns.
    """
    state = getattr(instance, '__dict__', None)
    if not state or '_morph_untranslated' not in state:
        return
    originals = state.pop('_morph_untranslated') or {}
    state.pop('_morph_translated', None)
    for field, value in originals.items():
        setattr(instance, field, value)


# -- writing ------------------------------------------------------------------
def set_translation(
    obj,
    field: str,
    language_code: str,
    value: str,
    *,
    machine_translated: bool = False,
    reviewed: bool = True,
):
    """Store one field's translation. A person's text is reviewed; an AI draft is not.

    A draft never replaces a reviewed translation. When an app registered the
    field, HTML is sanitised and plain text has its tags stripped and is cut to the
    source column's length.
    """
    from core.i18n.models import Translation

    ct = _ct(obj)
    field = field[:80]
    language_code = (language_code or '')[:10].lower()
    spec = spec_for(obj)
    if spec is not None and field in spec['fields']:
        value = clean_value(type(obj), field, spec['fields'][field], value)
    lookup = {
        'content_type': ct,
        'object_id': str(obj.pk),
        'field': field,
        'language_code': language_code,
    }
    if not reviewed:
        existing = Translation.objects.filter(**lookup).first()
        if existing is not None and existing.reviewed:
            return existing
    tr, _ = Translation.objects.update_or_create(
        **lookup,
        defaults={
            'value': value,
            'is_machine_translated': machine_translated,
            'reviewed': reviewed,
        },
    )
    return tr


def delete_translation(obj, field: str, language_code: str) -> int:
    from core.i18n.models import Translation

    deleted, _ = Translation.objects.filter(
        content_type=_ct(obj),
        object_id=str(obj.pk),
        field=field,
        language_code=(language_code or '').lower(),
    ).delete()
    return deleted


def approve_drafts(obj, language_code: str) -> int:
    """Mark the object's drafts in a language reviewed. They keep their AI provenance."""
    from django.utils import timezone

    from core.i18n.models import Translation

    return Translation.objects.filter(
        content_type=_ct(obj),
        object_id=str(obj.pk),
        language_code=(language_code or '').lower(),
        reviewed=False,
    ).update(reviewed=True, updated_at=timezone.now())


def get_translation(obj, field: str, language_code: str) -> str | None:
    """The reviewed translation of one field, or None."""
    from core.i18n.models import Translation

    if not language_code:
        return None
    row = Translation.objects.filter(
        content_type=_ct(obj),
        object_id=str(obj.pk),
        field=field,
        language_code=language_code,
        reviewed=True,
    ).first()
    return row.value if row else None


def translated(obj, field: str, language_code: str = '') -> str:
    """Return the reviewed translation if present, else the model value."""
    if language_code:
        val = get_translation(obj, field, language_code)
        if val:
            return val
    return getattr(obj, field, '') or ''


def translations_for(obj, *, language_code: str = '') -> dict[str, str]:
    """All translations for `obj`, drafts included (optionally filtered by language)."""
    from core.i18n.models import Translation

    qs = Translation.objects.filter(content_type=_ct(obj), object_id=str(obj.pk))
    if language_code:
        qs = qs.filter(language_code=language_code)
    return {f'{r.field}@{r.language_code}': r.value for r in qs}


def bulk_set_translations(obj, language_code: str, mapping: dict) -> int:
    """Set multiple reviewed field translations at once: `mapping = {field: value}`."""
    n = 0
    for field, val in (mapping or {}).items():
        if val is None or val == '':
            continue
        set_translation(obj, field, language_code, str(val))
        n += 1
    return n


# -- the work left ------------------------------------------------------------
STATUS_TRANSLATED = 'translated'
STATUS_DRAFT = 'draft'
STATUS_MISSING = 'missing'
STATUSES = (STATUS_MISSING, STATUS_DRAFT, STATUS_TRANSLATED)


def object_statuses(spec: dict, language: str) -> dict[str, str]:
    """`{pk: status}` for every object of a kind shoppers can see, in one language.

    translated: a reviewed translation of every filled field; draft: not that, but
    an AI draft waits for review; missing: neither. Two queries. A kind whose
    objects are not all covered by its fields (`applies`) keeps the others out of
    its queryset.
    """
    from core.i18n.models import Translation

    fields = list(spec['fields'])
    try:
        rows = list(spec['queryset']().values_list('pk', *fields))
    except Exception:  # noqa: BLE001 — an owner's queryset that fails lists nothing
        logger.warning('i18n: queryset failed for %s', spec.get('key'), exc_info=True)
        return {}
    reviewed: dict[str, set[str]] = defaultdict(set)
    drafts: dict[str, set[str]] = defaultdict(set)
    for object_id, field, is_reviewed, value in Translation.objects.filter(
        content_type=_ct(spec['model']), language_code=language, field__in=fields
    ).values_list('object_id', 'field', 'reviewed', 'value'):
        if (value or '').strip():
            (reviewed if is_reviewed else drafts)[object_id].add(field)
    out: dict[str, str] = {}
    for row in rows:
        pk = str(row[0])
        needed = {f for f, v in zip(fields, row[1:], strict=True) if str(v or '').strip()}
        if needed <= reviewed[pk]:
            out[pk] = STATUS_TRANSLATED
        elif drafts[pk] - reviewed[pk]:
            out[pk] = STATUS_DRAFT
        else:
            out[pk] = STATUS_MISSING
    return out


def status_summary(spec: dict, language: str) -> dict:
    statuses = object_statuses(spec, language)
    counts = {status: 0 for status in STATUSES}
    for status in statuses.values():
        counts[status] += 1
    return {
        'key': spec['key'],
        'label': str(spec.get('label') or spec['key']),
        'language': language,
        'language_name': language_name(language),
        'total': len(statuses),
        **counts,
    }
