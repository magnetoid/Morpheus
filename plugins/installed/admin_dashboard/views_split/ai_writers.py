"""AI-assisted writing endpoints for the dashboard.

JSON endpoints called from forms via fetch():
  * /dashboard/ai/draft-description/  — given a product name + category,
    produce a marketing description.
  * /dashboard/ai/rewrite-email/      — given a key + an instruction +
    the current text, return a rewritten version.

Both reuse the LLM gateway already configured in
``plugins.installed.ai_assistant.services.llm`` (which itself uses the
ai_assistant plugin's provider config — OpenAI / Anthropic / Gemini /
OpenRouter / Ollama).
"""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from core.authz import require_capability
from morpheus.app.views import staff_member_required
from plugins.installed.admin_dashboard.views_split._shared import call_llm, logger


def _json_body(request: HttpRequest) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return {}
    # Fall back to form-encoded POST.
    return {k: v for k, v in request.POST.items()}


@staff_member_required
@require_capability('catalog.write')
@require_POST
def ai_draft_description(request: HttpRequest) -> HttpResponse:
    """Draft a product description from a name + optional category + style."""
    body = _json_body(request)
    name = (body.get('name') or '').strip()
    category = (body.get('category') or '').strip()
    short = (body.get('short') or '').strip()
    if not name:
        return JsonResponse({'error': 'Product name is required.'}, status=400)

    system = (
        'You are a marketing copy writer for a small ecommerce store. '
        'Write product descriptions that are concrete, specific, and '
        'short. Three or four sentences max. Do not use exclamation '
        'marks or all-caps. Lead with what the product is, not what '
        'the customer will feel.'
    )
    prompt_parts = [f'Product name: {name}']
    if category:
        prompt_parts.append(f'Category: {category}')
    if short:
        prompt_parts.append(f'Short note from the merchant: {short}')
    prompt_parts.append('\nDraft a 3-4 sentence product description.')
    prompt = '\n'.join(prompt_parts)

    text, error = call_llm(prompt=prompt, system=system, max_tokens=400)
    if error:
        logger.warning('ai_draft_description: %s', error)
        return JsonResponse({'error': error}, status=502)
    return JsonResponse({'text': text})


@staff_member_required
@require_capability('catalog.write')
@require_POST
def ai_rewrite_description(request: HttpRequest) -> HttpResponse:
    """Rewrite an existing product description — clearer, more concrete, concise —
    keeping every fact from the original. Returns {text}."""
    body = _json_body(request)
    existing = (body.get('existing') or '').strip()
    name = (body.get('name') or '').strip()
    if not existing:
        return JsonResponse({'error': 'Nothing to rewrite yet.'}, status=400)

    system = (
        'You rewrite ecommerce product descriptions to be clearer, more '
        'concrete and concise. Keep every fact and claim from the original; '
        'never invent features. Three or four sentences. No exclamation marks '
        'or all-caps. Return only the rewritten description, no preamble.'
    )
    prompt = (f'Product name: {name}\n\n' if name else '') + (
        'Rewrite and improve this product description:\n\n' + existing
    )
    text, error = call_llm(prompt=prompt, system=system, max_tokens=400)
    if error:
        logger.warning('ai_rewrite_description: %s', error)
        return JsonResponse({'error': error}, status=502)
    return JsonResponse({'text': text})


@staff_member_required
@require_capability('marketing.write')
@require_POST
def ai_rewrite_email(request: HttpRequest) -> HttpResponse:
    """Rewrite an email subject + body in a target tone, preserving any
    Django template placeholders (``{{ order.* }}`` etc.) verbatim."""
    body = _json_body(request)
    subject = (body.get('subject') or '').strip()
    body_text = (body.get('body_text') or '').strip()
    tone = (body.get('tone') or 'friendly').strip()
    if not body_text:
        return JsonResponse({'error': 'Body text is required.'}, status=400)

    system = (
        'You rewrite transactional emails for a small ecommerce store. '
        'IMPORTANT: any Django template placeholder like {{ order.order_number }} '
        'or {% for item in order.items.all %} must be preserved EXACTLY. '
        'Do not rephrase variable names. Do not invent placeholders that '
        'were not in the input. Keep the rewrite roughly the same length.'
    )
    prompt = (
        f'Rewrite the following email in a {tone} tone.\n\n'
        f'--- SUBJECT ---\n{subject}\n\n'
        f'--- BODY ---\n{body_text}\n\n'
        f'Respond with two sections: first "SUBJECT:" then the new subject, '
        f'then "BODY:" then the new body. Nothing else.'
    )
    text, error = call_llm(prompt=prompt, system=system, max_tokens=900)
    if error:
        logger.warning('ai_rewrite_email: %s', error)
        return JsonResponse({'error': error}, status=502)

    new_subject = subject
    new_body = body_text
    # Parse the SUBJECT: / BODY: split. Be lenient — model may reorder
    # or drop the SUBJECT: header if subject was empty.
    sub_idx = text.upper().find('SUBJECT:')
    body_idx = text.upper().find('BODY:')
    if body_idx >= 0:
        if sub_idx >= 0 and sub_idx < body_idx:
            new_subject = text[sub_idx + len('SUBJECT:') : body_idx].strip()
        new_body = text[body_idx + len('BODY:') :].strip()
    else:
        # No structured response — treat the whole thing as the body.
        new_body = text.strip()
    return JsonResponse({'subject': new_subject, 'body_text': new_body})
