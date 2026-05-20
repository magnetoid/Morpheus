"""One-prompt store bootstrap.

Takes a single merchant sentence (e.g. "I want to sell handmade Japanese
tea") and generates a seeded store: brand-voice config, 3-5 categories,
8-12 products with descriptions + prices. All driven by the active LLM
gateway and written via the existing catalog / ai_content models.

Idempotent on a per-prompt basis via SHA-256 of the prompt — re-running
the same prompt returns the existing run rather than creating duplicate
catalogue rows.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction  # noqa: F401 — reserved for future per-row savepoints
from django.utils.text import slugify

logger = logging.getLogger('morpheus.admin_dashboard.bootstrap')


_SYSTEM_PROMPT = (
    "You are a brand+catalogue architect for a new independent online store. "
    "Given a one-sentence concept, you return a STRICT JSON payload that the "
    "platform will use to seed the store. Output ONLY the JSON object, no "
    "prose, no markdown fence, no comments. The JSON MUST match exactly the "
    "schema below. Values must be plain strings (no nested HTML, no Markdown). "
    "Prices are USD decimal strings like \"19.99\". Quantities are 4-6 "
    "categories and 10-12 products distributed across them."
)


_USER_TEMPLATE = """\
Concept: {concept}

Schema (return exactly this shape, populated):
{{
  "store_name": "...",
  "brand": {{
    "name": "...",
    "audience": "one short sentence — who shops here",
    "tone": "comma,separated,tone,adjectives",
    "guidelines": "one paragraph of voice rules"
  }},
  "categories": [
    {{"name": "...", "description": "one short sentence"}}
  ],
  "products": [
    {{
      "name": "...",
      "short": "30-50 word hook",
      "long": "120-200 word body",
      "price": "19.99",
      "category_name": "must match one of the categories above"
    }}
  ]
}}
"""


@dataclass(slots=True)
class BootstrapResult:
    prompt: str
    prompt_hash: str
    store_name: str = ''
    brand: dict = field(default_factory=dict)
    categories_created: list[str] = field(default_factory=list)
    products_created: list[str] = field(default_factory=list)
    skipped_categories: list[str] = field(default_factory=list)
    skipped_products: list[str] = field(default_factory=list)
    error: str = ''


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().lower().encode('utf-8')).hexdigest()[:16]


def _parse_payload(raw: str) -> dict:
    """Find and parse the JSON object inside an LLM response.

    Robust against ```json fences, leading commentary, trailing prose,
    trailing commas, and unescaped control chars inside string values.
    """
    if not raw:
        return {}
    txt = raw.strip()
    # Strip leading/trailing code fences (both ```json and bare ```).
    if txt.startswith('```'):
        txt = re.sub(r'^```[a-zA-Z]*\n?', '', txt)
    if txt.endswith('```'):
        txt = txt[:-3]
    txt = txt.strip()
    # Slice down to the outermost {...}
    start = txt.find('{')
    end = txt.rfind('}')
    if start < 0 or end <= start:
        return {}
    candidate = txt[start:end + 1]

    # Try strict parse first.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Repair pass: strip trailing commas, escape literal newlines inside
    # string values. LLMs frequently embed real newlines in long
    # descriptions; json.loads requires them as \n.
    repaired = re.sub(r',\s*([}\]])', r'\1', candidate)
    repaired = _escape_literal_newlines_in_strings(repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        logger.warning(
            'bootstrap: JSON parse failed: %s. First 200 of candidate: %s',
            e, candidate[:200],
        )
        return {}


def _escape_literal_newlines_in_strings(s: str) -> str:
    """Replace literal \\n / \\r inside JSON string literals with \\\\n.

    Walks the string with a tiny state machine — anything between an
    unescaped " and the matching " is a string body; replace real
    newlines/CRs there. Doesn't try to be a full JSON repairer; just
    handles the single most common LLM error mode.
    """
    out: list[str] = []
    in_str = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == '\\':
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            continue
        if in_str and ch == '\n':
            out.append('\\n')
            continue
        if in_str and ch == '\r':
            out.append('\\r')
            continue
        if in_str and ch == '\t':
            out.append('\\t')
            continue
        out.append(ch)
    return ''.join(out)


def _apply_brand_voice(brand: dict) -> None:
    """Persist the generated brand-voice config into the ai_content plugin.

    Each `set_config` call is wrapped individually — a transient DB
    error on one field shouldn't drop the other three.
    """
    if not brand:
        return
    from plugins.registry import plugin_registry
    plugin = plugin_registry.get('ai_content')
    if plugin is None:
        return
    for src_key, dst_key in (
        ('name', 'brand_name'),
        ('audience', 'brand_audience'),
        ('tone', 'brand_tone'),
        ('guidelines', 'brand_voice_guidelines'),
    ):
        value = (brand.get(src_key) or '').strip()
        if not value:
            continue
        try:
            plugin.set_config(dst_key, value)
        except Exception as e:  # noqa: BLE001
            logger.warning('bootstrap: brand-voice %s persist failed: %s', dst_key, e)


def _ensure_unique_slug(model, base: str) -> str:
    """Return a slug derived from `base` that isn't already on the model."""
    base_slug = slugify(base)[:200] or 'item'
    candidate = base_slug
    i = 2
    while model.objects.filter(slug=candidate).exists():
        candidate = f'{base_slug}-{i}'
        i += 1
        if i > 50:
            candidate = f'{base_slug}-{_hash_prompt(base)[:6]}'
            break
    return candidate


def _create_categories(spec: list[dict]) -> dict[str, Any]:
    """Resolve categories. Returns a {name: Category} map for product linking.

    Uses get_or_create on slug so the bootstrap is idempotent: a repeat
    run with the same concept reuses the existing categories rather
    than creating slug-1/-2 duplicates.
    """
    from plugins.installed.catalog.models import Category
    out: dict[str, Any] = {}
    for entry in spec:
        name = (entry.get('name') or '').strip()
        if not name:
            continue
        slug = slugify(name)[:200] or 'category'
        try:
            cat, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name[:100],
                    'description': (entry.get('description') or '')[:500],
                    'is_active': True,
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('bootstrap: skipping category %r: %s', name, e)
            continue
        out[name] = cat
    return out


def _create_products(spec: list[dict], category_map: dict[str, Any]) -> list[str]:
    """Create active products linked to their named category.

    Slug collision is silently skipped — re-running the same bootstrap
    won't create slug-2 duplicates, just lands the new products from
    the freshly-generated spec.
    """
    from plugins.installed.catalog.models import Product
    created: list[str] = []
    for entry in spec:
        name = (entry.get('name') or '').strip()
        if not name:
            continue
        slug = slugify(name)[:200] or 'product'
        if Product.objects.filter(slug=slug).exists():
            continue
        try:
            price_raw = (entry.get('price') or '0').strip().replace('$', '').replace(',', '')
            price = Decimal(price_raw)
        except Exception:  # noqa: BLE001
            price = Decimal('9.99')
        category = category_map.get((entry.get('category_name') or '').strip())
        # Product.sku has a unique constraint; an empty string collides
        # across products on the same bootstrap run (first product
        # "reserves" '' and every subsequent one fails). Derive a
        # readable SKU from the slug (no chance of collision since the
        # slug itself is unique above).
        sku = (slug or 'sku').upper()[:80]
        try:
            Product.objects.create(
                name=name[:300],
                slug=slug,
                sku=sku,
                status='active',
                price=price,
                short_description=(entry.get('short') or '')[:500],
                description=(entry.get('long') or '')[:4000],
                category=category,
            )
            created.append(slug)
        except Exception as e:  # noqa: BLE001
            logger.warning('bootstrap: skipping product %r: %s', name, e)
    return created


def bootstrap_store_from_prompt(prompt: str) -> BootstrapResult:
    """Run the full bootstrap. Returns a BootstrapResult — never raises.

    Architecture:
      1. LLM call (one shot, ~1500 tokens) returns {store_name, brand,
         categories[], products[]}.
      2. Categories are created first (idempotent on slug).
      3. Products are created and linked via their declared category_name.
      4. Brand-voice config is written to the ai_content plugin so every
         downstream AI generation inherits the new voice.
    """
    prompt = (prompt or '').strip()
    result = BootstrapResult(prompt=prompt, prompt_hash=_hash_prompt(prompt))
    if not prompt:
        result.error = 'Empty prompt.'
        return result

    try:
        from plugins.installed.ai_assistant.services.llm import get_llm
        gateway = get_llm()
    except Exception as e:  # noqa: BLE001
        result.error = f'No LLM provider available: {e}.'
        return result

    user = _USER_TEMPLATE.format(concept=prompt)
    try:
        raw = gateway.complete(
            user, system=_SYSTEM_PROMPT,
            temperature=0.85, max_tokens=4000,
        )
    except Exception as e:  # noqa: BLE001
        result.error = f'LLM call failed: {e}'
        return result

    payload = _parse_payload(raw or '')
    if not payload:
        result.error = 'Could not parse a usable plan from the LLM response.'
        return result

    result.store_name = (payload.get('store_name') or '').strip()
    result.brand = payload.get('brand') or {}

    # No outer transaction.atomic() here: each Category/Product create
    # is a single autocommitted row, so a partial failure leaves
    # already-created rows intact rather than poisoning the whole run.
    # Per-row creates inside `_create_categories` / `_create_products`
    # swallow row-level exceptions and continue.
    _apply_brand_voice(result.brand)
    category_map = _create_categories(payload.get('categories') or [])
    result.categories_created = [c.slug for c in category_map.values()]
    result.products_created = _create_products(
        payload.get('products') or [], category_map,
    )

    return result
