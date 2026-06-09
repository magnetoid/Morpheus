"""Audiobooks plugin manifest.

Adds an audiobook EDITION to a book as a real, purchasable digital
``catalog.ProductVariant``, attaches the narration audio + a modal player to it,
and (next step) generates the narration with ElevenLabs. Requires book_product;
disable it and the player + generation + settings vanish while the variant stays
a plain digital edition. See docs/plans/audiobooks-2026-06.md.
"""

from __future__ import annotations

from morpheus import Plugin


class AudiobooksPlugin(Plugin):
    name = 'audiobooks'
    label = 'Audiobooks'
    version = '0.1.0'
    description = (
        'Audiobook editions for books — a priced digital variant with a modal '
        'player on the product page, plus ElevenLabs narration. Requires '
        'book_product.'
    )
    requires = ['book_product']
    has_models = True

    def ready(self) -> None:
        # Storefront PDP player block + ElevenLabs settings panel are wired in
        # the next phases (docs/plans/audiobooks-2026-06.md).
        pass
