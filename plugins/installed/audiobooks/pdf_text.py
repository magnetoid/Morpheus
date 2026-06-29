"""Extract narratable text from a book PDF for ElevenLabs narration.

Best-effort and fail-soft: returns ``''`` on any problem (no file, encrypted,
image-only scan, parse error, or ``pypdf`` missing) so ``services.source_text``
cleanly falls back to the title/synopsis blurb instead of crashing the worker.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.audiobooks')


def extract_pdf_text(file_field) -> str:
    """Return the concatenated text of a PDF ``FileField``, or ``''`` if unreadable.

    Never raises — the audiobook generation pipeline must degrade gracefully.
    """
    if not file_field:
        return ''
    try:
        from pypdf import PdfReader
    except Exception:  # noqa: BLE001 — dependency missing → fall back to the blurb
        logger.warning('pypdf unavailable; audiobook narration falls back to the blurb')
        return ''
    try:
        file_field.open('rb')
        try:
            reader = PdfReader(file_field)
            pages = [(page.extract_text() or '') for page in reader.pages]
        finally:
            file_field.close()
    except Exception as exc:  # noqa: BLE001 — encrypted / scanned / corrupt → fall back
        logger.warning('PDF text extraction failed: %s', exc, exc_info=True)
        return ''
    return '\n'.join(p.strip() for p in pages if p.strip()).strip()
