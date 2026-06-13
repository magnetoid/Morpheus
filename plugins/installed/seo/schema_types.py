"""Declarative schema.org type registry for the visual structured-data editor.

The editor renders a form from ``SCHEMA_TYPES`` (no JSON typing) and posts back a
list of ``{type, data}`` entries; :func:`build_block` turns each into a
ready-to-emit JSON-LD dict. The dashboard JS consumes :func:`registry_json`.

Adding a type = add an entry to ``SCHEMA_TYPES`` + a builder in ``_BUILDERS``.
Keep it to types with real Google rich-result / AEO value — this is a friendly
front end, not all of schema.org.
"""

from __future__ import annotations

from typing import Any

SCHEMA_CONTEXT = 'https://schema.org'

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
        'key': 'HowTo',
        'type': 'HowTo',
        'label': 'How-to',
        'icon': 'list-ordered',
        'help': 'Step-by-step instructions.',
        'fields': [
            {'name': 'name', 'label': 'Title', 'kind': 'text', 'required': True},
            {'name': 'total_time_min', 'label': 'Total time (minutes)', 'kind': 'duration_min'},
            {
                'name': 'steps',
                'label': 'Steps',
                'kind': 'group',
                'min': 1,
                'subfields': [
                    {'name': 'name', 'label': 'Step title', 'kind': 'text'},
                    {'name': 'text', 'label': 'Instruction', 'kind': 'textarea', 'required': True},
                ],
            },
            {
                'name': 'tools',
                'label': 'Tools',
                'kind': 'group',
                'subfields': [{'name': 'name', 'label': 'Tool', 'kind': 'text'}],
            },
            {
                'name': 'supplies',
                'label': 'Supplies',
                'kind': 'group',
                'subfields': [{'name': 'name', 'label': 'Supply', 'kind': 'text'}],
            },
        ],
    },
    {
        'key': 'Event',
        'type': 'Event',
        'label': 'Event',
        'icon': 'calendar',
        'help': 'A scheduled event — launch, signing, workshop.',
        'fields': [
            {'name': 'name', 'label': 'Event name', 'kind': 'text', 'required': True},
            {'name': 'start_date', 'label': 'Starts', 'kind': 'datetime', 'required': True},
            {'name': 'end_date', 'label': 'Ends', 'kind': 'datetime'},
            {'name': 'location_name', 'label': 'Location name', 'kind': 'text'},
            {'name': 'location_address', 'label': 'Address', 'kind': 'text'},
            {'name': 'url', 'label': 'Event URL', 'kind': 'url'},
            {'name': 'offer_price', 'label': 'Ticket price', 'kind': 'number'},
            {'name': 'offer_currency', 'label': 'Currency (e.g. USD)', 'kind': 'text'},
            {'name': 'offer_url', 'label': 'Tickets URL', 'kind': 'url'},
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
        'key': 'Article',
        'type': 'Article',
        'label': 'Article',
        'icon': 'file-text',
        'help': 'Editorial article / blog post (beyond the auto Article schema).',
        'fields': [
            {'name': 'headline', 'label': 'Headline', 'kind': 'text', 'required': True},
            {'name': 'author', 'label': 'Author name', 'kind': 'text'},
            {'name': 'date_published', 'label': 'Published', 'kind': 'date'},
            {'name': 'image', 'label': 'Image URL', 'kind': 'url'},
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
        'help': 'Any other schema.org type as labeled property/value rows — still no JSON.',
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


def _build_howto(d: dict) -> dict:
    return {
        '@type': 'HowTo',
        'name': _s(d, 'name'),
        'totalTime': _iso_duration(d.get('total_time_min')),
        'step': [
            {'@type': 'HowToStep', 'name': _s(r, 'name'), 'text': _s(r, 'text')}
            for r in _rows(d, 'steps')
            if _s(r, 'text')
        ],
        'tool': [
            {'@type': 'HowToTool', 'name': _s(r, 'name')}
            for r in _rows(d, 'tools')
            if _s(r, 'name')
        ],
        'supply': [
            {'@type': 'HowToSupply', 'name': _s(r, 'name')}
            for r in _rows(d, 'supplies')
            if _s(r, 'name')
        ],
    }


def _build_event(d: dict) -> dict:
    return {
        '@type': 'Event',
        'name': _s(d, 'name'),
        'startDate': _s(d, 'start_date'),
        'endDate': _s(d, 'end_date'),
        'url': _s(d, 'url'),
        'location': {
            '@type': 'Place',
            'name': _s(d, 'location_name'),
            'address': _s(d, 'location_address'),
        },
        'offers': {
            '@type': 'Offer',
            'price': _s(d, 'offer_price'),
            'priceCurrency': _s(d, 'offer_currency'),
            'url': _s(d, 'offer_url'),
        },
    }


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


def _build_article(d: dict) -> dict:
    author = _s(d, 'author')
    return {
        '@type': 'Article',
        'headline': _s(d, 'headline'),
        'author': {'@type': 'Person', 'name': author} if author else '',
        'datePublished': _s(d, 'date_published'),
        'image': _s(d, 'image'),
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
        if prop and val:
            block[prop] = val
    return block


_BUILDERS = {
    'FAQPage': _build_faq,
    'HowTo': _build_howto,
    'Event': _build_event,
    'Recipe': _build_recipe,
    'Article': _build_article,
    'VideoObject': _build_video,
    'Course': _build_course,
    'Custom': _build_custom,
}


def build_block(type_key: str, data: dict) -> dict | None:
    """Turn one editor entry into a JSON-LD block (with @context), or None if the
    type is unknown or the block has no meaningful content."""
    builder = _BUILDERS.get(type_key)
    if builder is None or not isinstance(data, dict):
        return None
    block = _clean(builder(data))
    # A block is meaningful only if it has at least one property beyond @type.
    if len(block) <= 1:
        return None
    return {'@context': SCHEMA_CONTEXT, **block}


def build_blocks(entries: list[dict]) -> list[dict]:
    """Map a posted ``[{type, data}, …]`` list to clean JSON-LD blocks."""
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        block = build_block(entry.get('type', ''), entry.get('data') or {})
        if block:
            out.append(block)
    return out
