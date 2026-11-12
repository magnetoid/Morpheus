"""AI drafts of translations, for the merchant to review.

A draft is written `reviewed=False, is_machine_translated=True` (core.i18n): the
storefront never shows it and it counts for no language until a person saves or
approves it. One model call per object, its filled fields as JSON in and JSON out,
through the guarded provider (`core.agents.llm`), so the merchant's kill switch and
spend cap apply. A draft never replaces a reviewed translation.
"""

# ruff: noqa: PLC0415 — model and provider imports are lazy (load-order safe).
from __future__ import annotations

import json
import logging
import re

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('morpheus.localization')

#: Objects one click (or one tool call) queues at most.
BATCH_LIMIT = 50

_STATUS_KEY = 'localization:drafts:{kind}:{language}'
_JSON_RE = re.compile(r'\{.*\}', re.S)


class DraftError(Exception):
    """A draft could not be made; the message is fit to show the merchant."""


def last_run(kind: str, language: str) -> dict | None:
    """What the last drafting run for a kind and language did, for the page."""
    return cache.get(_STATUS_KEY.format(kind=kind, language=language))


def _remember(kind: str, language: str, **status) -> None:
    status['at'] = timezone.now().isoformat()
    cache.set(_STATUS_KEY.format(kind=kind, language=language), status, None)


def missing_ids(spec: dict, language: str, *, limit: int = BATCH_LIMIT) -> list[str]:
    """The objects with neither a reviewed translation nor a draft in `language`."""
    from core.i18n.services import STATUS_MISSING, object_statuses

    ids = [pk for pk, status in object_statuses(spec, language).items() if status == STATUS_MISSING]
    return ids[:limit]


def queue_drafts(kind: str, language: str, object_ids=None) -> dict:
    """Queue drafts for the given objects, else for up to 50 missing ones."""
    from core.i18n.services import spec_by_key, target_languages

    spec = spec_by_key(kind)
    if spec is None:
        raise DraftError('This kind of content cannot be translated.')
    if language not in target_languages():
        raise DraftError('The store is not offered in that language.')
    ids = [str(pk) for pk in (object_ids or [])][:BATCH_LIMIT] or missing_ids(spec, language)
    if not ids:
        return {'queued': 0, 'object_ids': []}
    _remember(kind, language, state='queued', queued=len(ids), drafted=0, message='')
    from plugins.installed.localization.tasks import draft_translations

    draft_translations.delay(kind, language, ids)
    return {'queued': len(ids), 'object_ids': ids}


def _prompt(source_language: str, target_language: str, target_code: str) -> str:
    script = (
        ' Write Serbian in the Latin script, never Cyrillic.'
        if target_code.split('-', 1)[0] == 'sr'
        else ''
    )
    return (
        f"You translate an online store's text from {source_language} into "
        f'{target_language}. You get a JSON object of fields; answer with a JSON object '
        'with the same keys, each value translated, and nothing else. Keep every HTML '
        'tag and attribute exactly as it is and translate only the text between them. '
        'Keep the names of places, hotels, businesses and brands as people there write '
        f'them. Do not add or leave out information.{script}'
    )


def _parse(text: str, fields) -> dict[str, str]:
    match = _JSON_RE.search(text or '')
    if not match:
        raise DraftError('The model did not answer with the translated fields.')
    try:
        data = json.loads(match.group(0))
    except ValueError as e:
        raise DraftError('The model did not answer with the translated fields.') from e
    if not isinstance(data, dict):
        raise DraftError('The model did not answer with the translated fields.')
    return {f: data[f].strip() for f in fields if isinstance(data.get(f), str) and data[f].strip()}


def draft_object(spec: dict, obj, language: str) -> int:
    """Draft the fields of `obj` with no reviewed translation in `language`; the count written.

    Raises `DraftError` on a provider error and lets `AIPaused` through; either way
    nothing is written for the object.
    """
    from core.agents.llm import LLMMessage, get_llm_provider, is_degraded_response
    from core.i18n.services import (
        default_language,
        language_name,
        reviewed_values,
        set_translation,
        source_values,
    )

    source = {f: v for f, v in source_values(obj, spec).items() if v.strip()}
    reviewed = reviewed_values(obj, language).get(str(obj.pk), {})
    todo = {f: v for f, v in source.items() if f not in reviewed}
    if not todo:
        return 0
    provider = get_llm_provider()
    if getattr(provider, 'name', '') == 'unconfigured':
        raise DraftError('No AI provider is set up for this store.')
    try:
        response = provider.respond(
            messages=[
                LLMMessage(
                    role='system',
                    content=_prompt(
                        language_name(default_language()), language_name(language), language
                    ),
                ),
                LLMMessage(role='user', content=json.dumps(todo, ensure_ascii=False)),
            ],
            tools=None,
            temperature=0.2,
            max_tokens=4000,
        )
    except Exception as e:  # noqa: BLE001 — AIPaused is re-raised below
        from core.agents.guardrails import AIPaused

        if isinstance(e, AIPaused):
            raise
        logger.warning('localization: draft failed for %s %s', spec['key'], obj.pk, exc_info=True)
        raise DraftError('The AI provider did not answer. Try again later.') from e
    if is_degraded_response(response.text):
        raise DraftError('The AI provider is unavailable. Try again later.')
    values = _parse(response.text, todo)
    for field, value in values.items():
        set_translation(obj, field, language, value, machine_translated=True, reviewed=False)
    return len(values)


def run_drafts(kind: str, language: str, object_ids) -> dict:
    """Draft each object in turn; stop at the first refusal or provider error and say why."""
    from celery.exceptions import SoftTimeLimitExceeded

    from core.agents.guardrails import AIPaused
    from core.i18n.services import spec_by_key

    spec = spec_by_key(kind)
    if spec is None:
        _remember(kind, language, state='stopped', drafted=0, message='This content kind is off.')
        return {'drafted': 0}
    objs = {str(o.pk): o for o in spec['model']._base_manager.filter(pk__in=list(object_ids))}
    drafted = objects = 0
    _remember(kind, language, state='running', queued=len(objs), drafted=0, message='')
    try:
        for pk in object_ids:
            obj = objs.get(str(pk))
            if obj is None:
                continue
            try:
                written = draft_object(spec, obj, language)
            except (AIPaused, DraftError) as e:
                _remember(
                    kind, language, state='stopped', drafted=objects, fields=drafted, message=str(e)
                )
                return {'drafted': objects, 'message': str(e)}
            drafted += written
            objects += 1 if written else 0
    except SoftTimeLimitExceeded:
        _remember(
            kind,
            language,
            state='stopped',
            drafted=objects,
            fields=drafted,
            message='Drafting took too long and stopped; start it again for the rest.',
        )
        return {'drafted': objects}
    _remember(kind, language, state='done', drafted=objects, fields=drafted, message='')
    return {'drafted': objects}
