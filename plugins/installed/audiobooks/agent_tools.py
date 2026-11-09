"""Linda's tools for audiobook narration: see where a book's narration stands, and
start a sample or the whole book. Starting spends the store's ElevenLabs or Qwen
credit, so it waits for the merchant's yes."""

# ruff: noqa: PLC0415
from __future__ import annotations

import uuid

from morpheus.core import ToolError, ToolResult, tool

_PRODUCT = {
    'type': 'string',
    'description': "The book's product id, slug or SKU.",
}


def _audiobook(product: str):
    from plugins.installed.audiobooks.models import Audiobook
    from plugins.installed.catalog.models import Product

    ref = (product or '').strip()
    found = None
    try:
        found = Product.objects.filter(pk=uuid.UUID(ref)).first()
    except ValueError:
        found = Product.objects.filter(slug=ref).first() or Product.objects.filter(sku=ref).first()
    if found is None:
        raise ToolError(f'No product {ref!r}')
    audiobook = Audiobook.for_product(found)
    if audiobook is None:
        raise ToolError(
            f'{found.name} has no audiobook edition. Turn it on in the product editor first.'
        )
    return audiobook


@tool(
    name='audiobooks.status',
    description=(
        "Where a book's audiobook narration stands: ready or not, a sample or the "
        'full book being made, how far it has got, the service and voice, and the last error.'
    ),
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {'product': _PRODUCT}, 'required': ['product']},
)
def audiobooks_status_tool(*, product: str) -> ToolResult:
    from plugins.installed.audiobooks.services import status

    state = status(_audiobook(product))
    return ToolResult(output=state, display=f'{state["status_label"]} · {state["percent"]}%')


@tool(
    name='audiobooks.generate',
    description=(
        "Narrate a book from its PDF: job 'sample' makes a short preview, 'full' the whole "
        "audiobook. provider is 'elevenlabs', 'studio' (an ElevenLabs Studio project the "
        "merchant can publish to ElevenReader) or 'qwen'; leave it out for the store default. "
        'Spends narration credit.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'product': _PRODUCT,
            'job': {'type': 'string', 'enum': ['sample', 'full'], 'default': 'sample'},
            'provider': {'type': 'string', 'enum': ['elevenlabs', 'studio', 'qwen']},
            'voice': {
                'type': 'string',
                'description': 'An ElevenLabs voice id or a Qwen voice name; leave out for the default.',
            },
        },
        'required': ['product'],
    },
    requires_approval=True,
)
def audiobooks_generate_tool(
    *, product: str, job: str = 'sample', provider: str | None = None, voice: str | None = None
) -> ToolResult:
    from plugins.installed.audiobooks.services import start

    result = start(_audiobook(product), job=job, provider=provider, voice=voice)
    if not result['ok']:
        raise ToolError(result['reason'])
    label = 'a sample' if job == 'sample' else 'the full narration'
    return ToolResult(output=result, display=f'Started {label} with {result["provider"]}')
