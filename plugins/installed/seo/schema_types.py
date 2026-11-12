"""Declarative schema.org type registry for the visual structured-data editor.

The editor renders a form from ``SCHEMA_TYPES`` (no JSON typing) and posts back a
list of ``{type, data}`` entries; :func:`build_block` turns each into a
ready-to-emit JSON-LD dict. The dashboard JS consumes :func:`registry_json`.
The page's graph (``seo/schema/graph.py``) adds the blocks to the object's page
(v0.163.0): until then they reached no page, because only the legacy
``{% seo_meta %}`` tag rendered them and the head contract silences it.

Adding a type = add an entry to ``SCHEMA_TYPES`` + a builder in ``_BUILDERS``.
Keep it to types Google's Search Gallery lists or answer engines read
(https://developers.google.com/search/docs/appearance/structured-data/search-gallery),
and never a type one of the store's apps writes itself (``OWNED_TYPES``): a second
Product or Event node on a page contradicts the first.
"""

from __future__ import annotations

import re
from typing import Any

SCHEMA_CONTEXT = 'https://schema.org'

# Types the store's own apps build into a page's graph (catalog and seo: Product,
# ProductGroup, Book; seo: Organization, WebSite, WebPage, BreadcrumbList, the
# listing's ItemList; cms: BlogPosting; booking_marketplace: Event, Hotel). The
# editor refuses them when it saves and the graph skips them when it renders.
OWNED_TYPES = frozenset(
    {
        'Product',
        'ProductGroup',
        'Book',
        'Organization',
        'OnlineStore',
        'Store',
        'WebSite',
        'WebPage',
        'CollectionPage',
        'ItemList',
        'BreadcrumbList',
        'Article',
        'BlogPosting',
        'NewsArticle',
        'Event',
        'Hotel',
        'LodgingBusiness',
    }
)

# Types the editor offered before v0.163.0. A stored block of one renders nowhere;
# the editor lists it with this reason and a button that deletes it.
_NOT_USED_BY_GOOGLE = 'No longer used by Google.'
_WRITTEN_BY_THE_STORE = 'The store writes this itself, so a second one would contradict it.'
RETIRED_TYPES = {
    'HowTo': _NOT_USED_BY_GOOGLE,
    'Book': _NOT_USED_BY_GOOGLE,
    'Event': _WRITTEN_BY_THE_STORE,
    'Article': _WRITTEN_BY_THE_STORE,
}

_TYPE_NAME = re.compile(r'^[A-Z][A-Za-z0-9]{1,63}$')

# Field ``kind`` vocabulary the editor JS understands:
#   text | textarea | url | date | datetime | number | duration_min | group
# A ``group`` field is a repeatable list of rows, each built from ``subfields``.

# Curated, ordered list of supported types. ``label``/``help`` are merchant-facing.
SCHEMA_TYPES: list[dict[str, Any]] = [
    {
        'key': 'FAQPage',
        'type': 'FAQPage',
        'label': 'FAQ',
        'icon': 'help-circle',
        'help': 'Questions & answers. Can show as an expandable FAQ rich result.',
        'fields': [
            {
                'name': 'items',
                'label': 'Questions',
                'kind': 'group',
                'min': 1,
                'subfields': [
                    {'name': 'question', 'label': 'Question', 'kind': 'text', 'required': True},
                    {'name': 'answer', 'label': 'Answer', 'kind': 'textarea', 'required': True},
                ],
            },
        ],
    },
    {
        'key': 'Recipe',
        'type': 'Recipe',
        'label': 'Recipe',
        'icon': 'utensils',
        'help': 'A cooking recipe.',
        'fields': [
            {'name': 'name', 'label': 'Recipe name', 'kind': 'text', 'required': True},
            {'name': 'image', 'label': 'Image URL', 'kind': 'url'},
            {'name': 'prep_time_min', 'label': 'Prep time (minutes)', 'kind': 'duration_min'},
            {'name': 'cook_time_min', 'label': 'Cook time (minutes)', 'kind': 'duration_min'},
            {'name': 'recipe_yield', 'label': 'Yield (e.g. 4 servings)', 'kind': 'text'},
            {
                'name': 'ingredients',
                'label': 'Ingredients',
                'kind': 'group',
                'min': 1,
                'subfields': [{'name': 'item', 'label': 'Ingredient', 'kind': 'text'}],
            },
            {
                'name': 'steps',
                'label': 'Steps',
                'kind': 'group',
                'min': 1,
                'subfields': [{'name': 'text', 'label': 'Instruction', 'kind': 'textarea'}],
            },
        ],
    },
    {
        'key': 'VideoObject',
        'type': 'VideoObject',
        'label': 'Video',
        'icon': 'video',
        'help': 'An embedded or hosted video.',
        'fields': [
            {'name': 'name', 'label': 'Title', 'kind': 'text', 'required': True},
            {'name': 'description', 'label': 'Description', 'kind': 'textarea'},
            {'name': 'thumbnail_url', 'label': 'Thumbnail URL', 'kind': 'url', 'required': True},
            {'name': 'upload_date', 'label': 'Upload date', 'kind': 'date', 'required': True},
            {'name': 'content_url', 'label': 'Video file URL', 'kind': 'url'},
            {'name': 'embed_url', 'label': 'Embed URL', 'kind': 'url'},
        ],
    },
    {
        'key': 'Course',
        'type': 'Course',
        'label': 'Course',
        'icon': 'graduation-cap',
        'help': 'An educational course.',
        'fields': [
            {'name': 'name', 'label': 'Course name', 'kind': 'text', 'required': True},
            {'name': 'description', 'label': 'Description', 'kind': 'textarea', 'required': True},
            {'name': 'provider', 'label': 'Provider name', 'kind': 'text'},
        ],
    },
    {
        'key': 'Custom',
        'type': 'Custom',
        'label': 'Custom type',
        'icon': 'braces',
        'help': 'Any other schema.org type as labeled property/value rows — still no JSON. '
        'Not a type the store writes itself (Product, Organization, Article, Event, …).',
        'fields': [
            {'name': 'custom_type', 'label': 'schema.org @type', 'kind': 'text', 'required': True},
            {
                'name': 'props',
                'label': 'Properties',
                'kind': 'group',
                'min': 1,
                'subfields': [
                    {'name': 'property', 'label': 'Property', 'kind': 'text'},
                    {'name': 'value', 'label': 'Value', 'kind': 'text'},
                ],
            },
        ],
    },
]

_TYPES_BY_KEY = {t['key']: t for t in SCHEMA_TYPES}


def registry_json() -> list[dict[str, Any]]:
    """The type spec the editor JS renders forms from (safe to JSON-encode)."""
    return SCHEMA_TYPES


# --- value coercion --------------------------------------------------------


def _s(data: dict, key: str) -> str:
    return str(data.get(key) or '').strip()


def _rows(data: dict, key: str) -> list[dict]:
    val = data.get(key)
    return [r for r in val if isinstance(r, dict)] if isinstance(val, list) else []


def _iso_duration(minutes: Any) -> str:
    """Whole minutes → ISO-8601 duration (PT1H30M). Empty/invalid → ''."""
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return ''
    if m <= 0:
        return ''
    h, mm = divmod(m, 60)
    return 'PT' + (f'{h}H' if h else '') + (f'{mm}M' if mm else '')


def _clean(value: Any) -> Any:
    """Drop empty strings / empty lists / empty dicts recursively."""
    if isinstance(value, dict):
        out = {k: _clean(v) for k, v in value.items()}
        return {k: v for k, v in out.items() if v not in ('', None, [], {})}
    if isinstance(value, list):
        out = [_clean(v) for v in value]
        return [v for v in out if v not in ('', None, [], {})]
    return value


# --- per-type builders -----------------------------------------------------


def _build_faq(d: dict) -> dict:
    entities = [
        {
            '@type': 'Question',
            'name': _s(r, 'question'),
            'acceptedAnswer': {'@type': 'Answer', 'text': _s(r, 'answer')},
        }
        for r in _rows(d, 'items')
        if _s(r, 'question') and _s(r, 'answer')
    ]
    return {'@type': 'FAQPage', 'mainEntity': entities}


def _build_recipe(d: dict) -> dict:
    return {
        '@type': 'Recipe',
        'name': _s(d, 'name'),
        'image': _s(d, 'image'),
        'prepTime': _iso_duration(d.get('prep_time_min')),
        'cookTime': _iso_duration(d.get('cook_time_min')),
        'recipeYield': _s(d, 'recipe_yield'),
        'recipeIngredient': [_s(r, 'item') for r in _rows(d, 'ingredients') if _s(r, 'item')],
        'recipeInstructions': [
            {'@type': 'HowToStep', 'text': _s(r, 'text')}
            for r in _rows(d, 'steps')
            if _s(r, 'text')
        ],
    }


def _build_video(d: dict) -> dict:
    return {
        '@type': 'VideoObject',
        'name': _s(d, 'name'),
        'description': _s(d, 'description'),
        'thumbnailUrl': _s(d, 'thumbnail_url'),
        'uploadDate': _s(d, 'upload_date'),
        'contentUrl': _s(d, 'content_url'),
        'embedUrl': _s(d, 'embed_url'),
    }


def _build_course(d: dict) -> dict:
    provider = _s(d, 'provider')
    return {
        '@type': 'Course',
        'name': _s(d, 'name'),
        'description': _s(d, 'description'),
        'provider': {'@type': 'Organization', 'name': provider} if provider else '',
    }


def _build_custom(d: dict) -> dict:
    block = {'@type': _s(d, 'custom_type') or 'Thing'}
    for r in _rows(d, 'props'):
        prop, val = _s(r, 'property'), _s(r, 'value')
        # '@id', '@type' and '@context' are the graph's, never a row's.
        if prop and val and not prop.startswith('@'):
            block[prop] = val
    return block


_BUILDERS = {
    'FAQPage': _build_faq,
    'Recipe': _build_recipe,
    'VideoObject': _build_video,
    'Course': _build_course,
    'Custom': _build_custom,
}


def block_type(entry: dict) -> str:
    """The schema.org type a stored entry would publish (a custom block's own)."""
    if not isinstance(entry, dict):
        return ''
    kind = str(entry.get('type') or '')
    if kind == 'Custom':
        return _s(entry.get('data') or {}, 'custom_type') or 'Thing'
    return kind


def refusal(entry: dict) -> str:
    """Why a stored entry may not render, or '' when it may."""
    kind = str(entry.get('type') or '') if isinstance(entry, dict) else ''
    if kind in RETIRED_TYPES:
        return RETIRED_TYPES[kind]
    if kind not in _BUILDERS:
        return _NOT_USED_BY_GOOGLE
    published = block_type(entry)
    if published in OWNED_TYPES:
        return _WRITTEN_BY_THE_STORE
    if not _TYPE_NAME.match(published):
        return 'Not a schema.org type name.'
    return ''


def build_block(type_key: str, data: dict) -> dict | None:
    """Turn one editor entry into a JSON-LD block (with @context), or None if the
    type is unknown or refused, or the block has no meaningful content."""
    builder = _BUILDERS.get(type_key)
    if builder is None or not isinstance(data, dict):
        return None
    if refusal({'type': type_key, 'data': data}):
        return None
    block = _clean(builder(data))
    # A block is meaningful only if it has at least one property beyond @type.
    if len(block) <= 1:
        return None
    return {'@context': SCHEMA_CONTEXT, **block}


def build_blocks(entries: list[dict]) -> list[dict]:
    """The JSON-LD blocks of the stored entries that may render, in order."""
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        block = build_block(entry.get('type', ''), entry.get('data') or {})
        if block:
            out.append(block)
    return out


def retired_entries(entries: list[dict]) -> list[dict]:
    """The stored entries that render nowhere, each with its place and the reason."""
    out = []
    for index, entry in enumerate(entries or []):
        reason = refusal(entry)
        if reason:
            out.append({'index': index, 'type': block_type(entry), 'reason': reason})
    return out
