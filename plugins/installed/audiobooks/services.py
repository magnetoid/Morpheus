"""ElevenLabs narration generation for audiobook editions (Phase 4).

``generate(audiobook)``: gather the book text → chunked ElevenLabs TTS →
concatenate the mp3 segments → store on ``audiobook.audio_file`` → status='ready'.
Driven by a Celery task; NEVER raises (sets status='failed' + logs on error).
Config (API key, voice, model) lives in the audiobooks plugin settings panel.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import logging
import re

logger = logging.getLogger('morpheus.audiobooks')

_TTS_URL = 'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
_MAX_CHARS = 2500  # per-request chunk — ElevenLabs takes long text; stay conservative.


def _config() -> dict:
    from plugins.registry import plugin_registry

    plugin = plugin_registry.get('audiobooks')
    if plugin is None:
        return {}
    return {
        'api_key': plugin.get_config_value('elevenlabs_api_key', ''),
        'voice_id': plugin.get_config_value('elevenlabs_voice_id', ''),
        'model': plugin.get_config_value('elevenlabs_model', 'eleven_multilingual_v2'),
    }


def _strip_html(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text or '')).strip()


def source_text(audiobook) -> str:
    """The narration script: title + author + synopsis + long description."""
    product = audiobook.variant.product
    parts = [product.name or '']
    book = getattr(product, 'book', None)
    if book is not None:
        if getattr(book, 'author', ''):
            parts.append(f'by {book.author}')
        if getattr(book, 'synopsis', ''):
            parts.append(_strip_html(book.synopsis))
    if getattr(product, 'description', ''):
        parts.append(_strip_html(product.description))
    return '. '.join(p for p in parts if p).strip()


def _chunks(text: str, size: int = _MAX_CHARS):
    """Split into <=size pieces at sentence boundaries."""
    buf = ''
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if buf and len(buf) + len(sentence) + 1 > size:
            yield buf.strip()
            buf = sentence
        else:
            buf = f'{buf} {sentence}'.strip()
    if buf.strip():
        yield buf.strip()


def _tts(text: str, *, api_key: str, voice_id: str, model: str, timeout: int = 60) -> bytes:
    import requests

    resp = requests.post(
        _TTS_URL.format(voice_id=voice_id),
        headers={
            'xi-api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'audio/mpeg',
        },
        json={'text': text, 'model_id': model},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.content


def generate(audiobook) -> dict:
    """Generate narration via ElevenLabs. Never raises — returns a result dict and
    sets ``audiobook.status`` accordingly."""
    from django.core.files.base import ContentFile

    cfg = _config()
    if not cfg.get('api_key') or not cfg.get('voice_id'):
        audiobook.status = 'failed'
        audiobook.save(update_fields=['status', 'updated_at'])
        return {
            'ok': False,
            'reason': 'ElevenLabs API key + voice required (Settings → Product Types → Audiobooks).',
        }

    text = source_text(audiobook)
    if not text:
        audiobook.status = 'failed'
        audiobook.save(update_fields=['status', 'updated_at'])
        return {'ok': False, 'reason': 'No book text to narrate — add a synopsis or description.'}

    audiobook.status = 'generating'
    audiobook.save(update_fields=['status', 'updated_at'])
    try:
        audio = bytearray()
        for chunk in _chunks(text):
            audio.extend(
                _tts(chunk, api_key=cfg['api_key'], voice_id=cfg['voice_id'], model=cfg['model'])
            )
        if not audio:
            raise RuntimeError('ElevenLabs returned no audio')
        audiobook.audio_file.save(
            f'audiobooks/{audiobook.variant_id}.mp3', ContentFile(bytes(audio)), save=False
        )
        audiobook.source = 'elevenlabs'
        audiobook.status = 'ready'
        audiobook.save(update_fields=['audio_file', 'source', 'status', 'updated_at'])
        return {'ok': True, 'bytes': len(audio)}
    except Exception as e:  # noqa: BLE001 — generation must not crash the worker
        logger.warning('audiobook generate failed (%s): %s', audiobook.id, e, exc_info=True)
        audiobook.status = 'failed'
        audiobook.save(update_fields=['status', 'updated_at'])
        return {'ok': False, 'reason': str(e)[:200]}
