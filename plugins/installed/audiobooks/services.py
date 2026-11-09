"""Narration jobs for audiobook editions: a sample, or the whole book.

``start(audiobook, job=...)`` checks the setup and queues the job; the Celery task
calls ``run(audiobook_id)`` once per slice. A book takes an hour or more to narrate
and a task is killed after five minutes, so a job works in slices of about
``SLICE_SECONDS``: every narrated piece is saved as it arrives (under
``digital/audiobooks/parts/<id>/``, private like the finished file) and the next
slice carries on after the last saved piece. A job that fails or is restarted with
the same service, voice, model and PDF resumes where it stopped; changing any of
them starts the pieces again.

The text is the book itself: the PDF on the card, else the product's or the
e-book's PDF. Nothing else is narrated: a buyer who pays for an audiobook must
never get a recording of the product description.

ElevenLabs Studio narrates the whole PDF on ElevenLabs' side instead (a Studio
project with a draft ElevenReader read), and the task waits for it and downloads
the result. A sample for Studio uses ordinary ElevenLabs text-to-speech.

A job never takes a ready audiobook away: while a new narration is made, and if
it fails, the edition keeps selling the file it has.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
import logging
import posixpath
import re
import secrets
import tempfile
import time
from datetime import timedelta

logger = logging.getLogger('morpheus.audiobooks')

PROVIDERS = ('elevenlabs', 'studio', 'qwen')
JOBS = ('sample', 'full')
SLICE_SECONDS = 100  # a task's soft limit is 240 s; one request may still run 120 s
SAMPLE_CHARS = 1200  # about a minute and a half of speech
STALE = timedelta(minutes=10)
STUDIO_POLL_SECONDS = 60
STUDIO_MAX = timedelta(hours=6)
STUDIO_KBPS = 128
LOCK_SECONDS = 290
PARTS_DIR = 'digital/audiobooks/parts'

NO_DOCUMENT = (
    "Add the book's PDF first: upload it as the source PDF on this card, "
    "or as the e-book edition's file."
)
ELEVENLABS_SETUP = 'Add your ElevenLabs API key and a voice in Settings → Audiobooks first.'
QWEN_SETUP = 'Add your Qwen (Alibaba Model Studio) API key in Settings → AI first.'

_PAGE_NUMBER = re.compile(r'(?:page\s+)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?', re.IGNORECASE)
_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+')


# ── settings ──────────────────────────────────────────────────────────────


def _config() -> dict:
    from plugins.registry import app_registry

    plugin = app_registry.get('audiobooks')

    def get(key: str, default: str) -> str:
        if plugin is None:
            return default
        return str(plugin.get_config_value(key, default) or default)

    provider = get('narration_provider', 'elevenlabs')
    return {
        'provider': provider if provider in PROVIDERS else 'elevenlabs',
        'elevenlabs_api_key': get('elevenlabs_api_key', ''),
        'elevenlabs_voice_id': get('elevenlabs_voice_id', ''),
        'elevenlabs_model': get('elevenlabs_model', 'eleven_multilingual_v2'),
        'qwen_voice': get('qwen_voice', 'Jennifer'),
        'qwen_model': get('qwen_model', 'qwen3-tts-flash'),
    }


def provider_for(audiobook, cfg: dict | None = None) -> str:
    cfg = cfg or _config()
    return audiobook.provider or cfg['provider']


def voice_for(audiobook, provider: str, cfg: dict) -> str:
    if audiobook.voice:
        return audiobook.voice
    return cfg['qwen_voice'] if provider == 'qwen' else cfg['elevenlabs_voice_id']


def _book(product):
    try:
        return product.book
    except Exception:  # noqa: BLE001 — not a book, or the book app is off
        return None


def _language_code(product) -> str:
    book = _book(product)
    code = (getattr(book, 'language', '') or '').strip().lower()
    return re.split(r'[-_]', code)[0][:3] if code else ''


def narrator_for(audiobook, provider: str, cfg: dict):
    """The chunk narrator for a job, or NarrationError naming what is missing."""
    from plugins.installed.audiobooks.narrators import (
        QWEN_LANGUAGES,
        ElevenLabsNarrator,
        NarrationError,
        QwenNarrator,
    )

    voice = voice_for(audiobook, provider, cfg)
    if provider == 'qwen':
        from core.agents.provider_registry import get_provider_config

        qwen = get_provider_config('qwen')
        if not getattr(qwen, 'api_key', ''):
            raise NarrationError(QWEN_SETUP)
        language = QWEN_LANGUAGES.get(_language_code(audiobook.variant.product), 'Auto')
        return QwenNarrator(
            api_key=qwen.api_key,
            base_url=qwen.base_url,
            voice=voice or 'Jennifer',
            model=cfg['qwen_model'],
            language=language,
        )
    if not cfg['elevenlabs_api_key'] or not voice:
        raise NarrationError(ELEVENLABS_SETUP)
    return ElevenLabsNarrator(
        api_key=cfg['elevenlabs_api_key'], voice=voice, model=cfg['elevenlabs_model']
    )


# ── the text ──────────────────────────────────────────────────────────────


def _is_pdf(file_field) -> bool:
    return bool(file_field) and str(file_field.name).lower().endswith('.pdf')


def source_document(audiobook):
    """The PDF to narrate: the card's, else the product's, else the e-book's."""
    product = audiobook.variant.product
    for candidate in (audiobook.source_pdf, getattr(product, 'digital_file', None)):
        if _is_pdf(candidate):
            return candidate
    for variant in product.variants.filter(variant_type='digital').exclude(digital_file=''):
        if _is_pdf(variant.digital_file):
            return variant.digital_file
    return None


def clean_text(raw: str) -> str:
    """PDF text as one flow of sentences: words broken over a line joined, page
    numbers dropped, lines and spacing collapsed."""
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', raw or '')
    lines = (line.strip() for line in text.splitlines())
    kept = [line for line in lines if line and not _PAGE_NUMBER.fullmatch(line)]
    return re.sub(r'\s+', ' ', ' '.join(kept)).strip()


def source_text(audiobook) -> str:
    """The book's text, read from its PDF; '' when there is no readable PDF."""
    document = source_document(audiobook)
    if document is None:
        return ''
    from plugins.installed.audiobooks.pdf_text import extract_pdf_text

    return clean_text(extract_pdf_text(document))


def sample_text(text: str, limit: int = SAMPLE_CHARS) -> str:
    """The opening of the book, ended at a sentence (else a word) within ``limit``."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    ends = [m.start() for m in _SENTENCE_END.finditer(head)]
    if ends and ends[-1] > limit // 3:
        return head[: ends[-1]].strip()
    return head.rsplit(' ', 1)[0].strip()


def chunks(text: str, size: int) -> list[str]:
    """Pieces of at most ``size`` characters, cut between sentences; a sentence
    longer than that is cut between words, and a word longer than that anywhere."""
    pieces: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        pieces.extend(_fit(sentence.strip(), size))
    out: list[str] = []
    buf = ''
    for piece in pieces:
        if buf and len(buf) + 1 + len(piece) > size:
            out.append(buf)
            buf = piece
        else:
            buf = f'{buf} {piece}' if buf else piece
    if buf:
        out.append(buf)
    return out


def _fit(sentence: str, size: int) -> list[str]:
    if len(sentence) <= size:
        return [sentence] if sentence else []
    out: list[str] = []
    buf = ''
    for whole in sentence.split(' '):
        word = whole
        while len(word) > size:
            if buf:
                out.append(buf)
                buf = ''
            out.append(word[:size])
            word = word[size:]
        if buf and len(buf) + 1 + len(word) > size:
            out.append(buf)
            buf = word
        else:
            buf = f'{buf} {word}' if buf else word
    if buf:
        out.append(buf)
    return out


# ── the editions ──────────────────────────────────────────────────────────


def get_or_create_audiobook_edition(product, *, sku: str):
    """Return the product's Audiobook edition, creating its digital
    ``ProductVariant`` + ``Audiobook`` row when absent. Callers compute the SKU."""
    from plugins.installed.audiobooks.models import Audiobook
    from plugins.installed.catalog.models import ProductVariant

    ab = Audiobook.for_product(product)
    if ab is None:
        variant = ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku=sku[:100],
            variant_type='audiobook',
            requires_shipping=False,
        )
        ab = Audiobook.objects.create(variant=variant)
    return ab


# ── the saved pieces ──────────────────────────────────────────────────────


class _Parts:
    """A job's narrated pieces in storage, kept while their signature holds."""

    def __init__(self, audiobook):
        from django.core.files.storage import default_storage

        self.storage = default_storage
        self.root = f'{PARTS_DIR}/{audiobook.id}'

    def _path(self, name: str) -> str:
        return posixpath.join(self.root, name)

    def _read(self, name: str) -> str | None:
        path = self._path(name)
        if not self.storage.exists(path):
            return None
        with self.storage.open(path, 'rb') as fh:
            return fh.read().decode('utf-8')

    def _write(self, name: str, data: bytes) -> None:
        from django.core.files.base import ContentFile

        path = self._path(name)
        if self.storage.exists(path):
            self.storage.delete(path)
        self.storage.save(path, ContentFile(data))

    def prepare(self, signature: dict) -> None:
        stored = self._read('meta.json')
        if stored is not None and json.loads(stored) == signature:
            return
        self.clear()
        self._write('meta.json', json.dumps(signature, sort_keys=True).encode())

    def text(self) -> str | None:
        return self._read('text.txt')

    def save_text(self, text: str) -> None:
        self._write('text.txt', text.encode('utf-8'))

    def has(self, index: int) -> bool:
        return self.storage.exists(self._path(f'part-{index:05d}.mp3'))

    def save(self, index: int, audio: bytes) -> None:
        self._write(f'part-{index:05d}.mp3', audio)

    def join(self, count: int, fileobj) -> int:
        size = 0
        for index in range(count):
            with self.storage.open(self._path(f'part-{index:05d}.mp3'), 'rb') as fh:
                while block := fh.read(1024 * 1024):
                    fileobj.write(block)
                    size += len(block)
        return size

    def clear(self) -> None:
        try:
            _dirs, files = self.storage.listdir(self.root)
        except (FileNotFoundError, NotImplementedError, OSError):
            return
        for name in files:
            self.storage.delete(self._path(name))


# ── jobs ──────────────────────────────────────────────────────────────────


def is_running(audiobook) -> bool:
    from django.utils import timezone

    return bool(audiobook.job) and audiobook.updated_at > timezone.now() - STALE


def start(audiobook, *, job: str = 'full', provider: str | None = None, voice: str | None = None):
    """Check the setup and queue a narration job. Never raises; returns
    ``{'ok': True, ...}`` or ``{'ok': False, 'reason': <for the merchant>}``."""
    from django.db import transaction
    from django.utils import timezone

    from plugins.installed.audiobooks.narrators import NarrationError

    if job not in JOBS:
        return {'ok': False, 'reason': 'Choose a sample or the full narration.'}
    if provider is not None and provider and provider not in PROVIDERS:
        return {'ok': False, 'reason': f'Unknown narration service: {provider}'}
    if is_running(audiobook):
        return {'ok': False, 'reason': 'A narration is already running for this book.'}
    if provider is not None:
        audiobook.provider = provider
    if voice is not None:
        audiobook.voice = voice.strip()[:80]
    cfg = _config()
    service = provider_for(audiobook, cfg)
    try:
        if service == 'studio' and job == 'full':
            if not cfg['elevenlabs_api_key'] or not voice_for(audiobook, service, cfg):
                raise NarrationError(ELEVENLABS_SETUP)
        else:
            narrator_for(audiobook, service, cfg)
    except NarrationError as exc:
        audiobook.save(update_fields=['provider', 'voice', 'updated_at'])
        return {'ok': False, 'reason': str(exc)}
    if source_document(audiobook) is None:
        audiobook.save(update_fields=['provider', 'voice', 'updated_at'])
        return {'ok': False, 'reason': NO_DOCUMENT}

    audiobook.job = job
    audiobook.job_started_at = timezone.now()
    audiobook.progress_done = audiobook.progress_total = 0
    audiobook.last_error = ''
    if service == 'studio' and job == 'full':
        audiobook.studio_project_id = ''  # a new Studio project for a new narration
    if job == 'full' and not audiobook.audio_file:
        audiobook.status = 'generating'
    audiobook.save()

    from plugins.installed.audiobooks.tasks import generate_audiobook

    audiobook_id = str(audiobook.id)
    transaction.on_commit(lambda: generate_audiobook.delay(audiobook_id))
    return {'ok': True, 'job': job, 'provider': service}


def run(audiobook_id) -> dict:  # noqa: PLR0911 — one answer per way a slice ends
    """One slice of the audiobook's job. ``again`` is the delay in seconds before
    the next slice, or None when the job has ended."""
    from celery.exceptions import SoftTimeLimitExceeded
    from django.core.cache import cache

    from core.agents.guardrails import AIPaused
    from plugins.installed.audiobooks.models import Audiobook
    from plugins.installed.audiobooks.narrators import NarrationError

    lock = f'audiobooks:job:{audiobook_id}'
    if not cache.add(lock, 1, timeout=LOCK_SECONDS):
        return {'ok': True, 'again': STUDIO_POLL_SECONDS, 'reason': 'busy'}
    audiobook = None
    try:
        audiobook = (
            Audiobook.objects.filter(id=audiobook_id).select_related('variant__product').first()
        )
        if audiobook is None or not audiobook.job:
            return {'ok': False, 'again': None, 'reason': 'no narration to run'}
        cfg = _config()
        service = provider_for(audiobook, cfg)
        if service == 'studio' and audiobook.job == 'full':
            return _run_studio(audiobook, cfg)
        return _run_pieces(audiobook, service, cfg)
    except SoftTimeLimitExceeded:
        return {'ok': True, 'again': 1}
    except (NarrationError, AIPaused) as exc:
        _fail(audiobook, str(exc))
        return {'ok': False, 'again': None, 'reason': str(exc)}
    except Exception as exc:  # noqa: BLE001 — a job must end, never loop on a bug
        logger.exception('audiobook narration failed (%s)', audiobook_id)
        _fail(audiobook, f'Narration failed: {exc}')
        return {'ok': False, 'again': None, 'reason': str(exc)[:200]}
    finally:
        cache.delete(lock)


def _run_pieces(audiobook, service: str, cfg: dict) -> dict:
    from plugins.installed.audiobooks.narrators import NarrationError

    narrator = narrator_for(audiobook, service, cfg)
    document = source_document(audiobook)
    if document is None:
        raise NarrationError(NO_DOCUMENT)
    parts = _Parts(audiobook)
    parts.prepare(
        {
            'service': type(narrator).__name__,
            'voice': narrator.voice,
            'model': narrator.model,
            'job': audiobook.job,
            'source': document.name,
        }
    )
    text = parts.text()
    if text is None:
        text = source_text(audiobook)
        if audiobook.job == 'sample':
            text = sample_text(text)
        if not text:
            raise NarrationError(
                'No text could be read from the PDF. A scanned book has none; '
                'upload a PDF with selectable text.'
            )
        parts.save_text(text)
    pieces = chunks(text, narrator.max_chars)
    total = sum(len(piece) for piece in pieces)
    done = sum(len(piece) for index, piece in enumerate(pieces) if parts.has(index))
    _progress(audiobook, done, total)
    deadline = time.monotonic() + SLICE_SECONDS
    narrated = 0
    for index, piece in enumerate(pieces):
        if parts.has(index):
            continue
        if narrated and time.monotonic() > deadline:  # every slice moves on by one piece
            return {'ok': True, 'again': 1, 'done': done, 'total': total}
        audio = narrator.narrate(
            piece,
            previous_text=pieces[index - 1] if index else '',
            next_text=pieces[index + 1] if index + 1 < len(pieces) else '',
        )
        if not audio:
            raise NarrationError('The narration service returned no audio.')
        parts.save(index, audio)
        narrated += 1
        done += len(piece)
        _progress(audiobook, done, total)
    with tempfile.TemporaryFile() as tmp:
        size = parts.join(len(pieces), tmp)
        tmp.seek(0)
        source = 'qwen' if service == 'qwen' else 'elevenlabs'  # a Studio sample is plain TTS
        _store(audiobook, tmp, size=size, kbps=narrator.kbps, source=source)
    parts.clear()
    return {'ok': True, 'again': None, 'bytes': size}


def _run_studio(audiobook, cfg: dict) -> dict:
    from django.utils import timezone

    from plugins.installed.audiobooks.narrators import (
        NarrationError,
        StudioClient,
        studio_progress,
    )

    voice = voice_for(audiobook, 'studio', cfg)
    if not cfg['elevenlabs_api_key'] or not voice:
        raise NarrationError(ELEVENLABS_SETUP)
    if audiobook.job_started_at and timezone.now() - audiobook.job_started_at > STUDIO_MAX:
        raise NarrationError(
            'ElevenLabs Studio did not finish within 6 hours. Check the project in '
            'ElevenLabs, then start again.'
        )
    client = StudioClient(cfg['elevenlabs_api_key'])
    if not audiobook.studio_project_id:
        document = source_document(audiobook)
        if document is None:
            raise NarrationError(NO_DOCUMENT)
        document.open('rb')
        try:
            project_id = client.create_project(
                document=document,
                filename=posixpath.basename(document.name),
                meta=_studio_meta(audiobook, voice, cfg['elevenlabs_model']),
            )
        finally:
            document.close()
        audiobook.studio_project_id = project_id
        audiobook.save(update_fields=['studio_project_id', 'updated_at'])
        return {'ok': True, 'again': STUDIO_POLL_SECONDS}

    project_id = audiobook.studio_project_id
    done, total, error = studio_progress(client.project(project_id))
    if error:
        raise NarrationError(f'ElevenLabs Studio: {error}')
    _progress(audiobook, done, total)
    if not total or done < total:
        return {'ok': True, 'again': STUDIO_POLL_SECONDS, 'done': done, 'total': total}
    started = audiobook.job_started_at.timestamp() - 60 if audiobook.job_started_at else 0
    snapshots = [
        snap
        for snap in client.snapshots(project_id)
        if (snap.get('created_at_unix') or 0) >= started and snap.get('project_snapshot_id')
    ]
    if not snapshots:
        return {'ok': True, 'again': STUDIO_POLL_SECONDS, 'reason': 'waiting for the audio'}
    snapshot = max(snapshots, key=lambda snap: snap.get('created_at_unix') or 0)
    with tempfile.TemporaryFile() as tmp:
        try:
            size = client.download(project_id, snapshot['project_snapshot_id'], tmp)
        except Exception as exc:  # noqa: BLE001 — a dropped download is tried again
            audiobook.last_error = f'Download from ElevenLabs Studio failed, retrying: {exc}'[:300]
            audiobook.save(update_fields=['last_error', 'updated_at'])
            return {'ok': True, 'again': STUDIO_POLL_SECONDS}
        if not size:
            return {'ok': True, 'again': STUDIO_POLL_SECONDS}
        tmp.seek(0)
        _store(audiobook, tmp, size=size, kbps=STUDIO_KBPS, source='studio')
    return {'ok': True, 'again': None, 'bytes': size}


def _studio_meta(audiobook, voice: str, model: str) -> dict:
    from django.utils.html import strip_tags

    product = audiobook.variant.product
    book = _book(product)
    description = strip_tags(getattr(book, 'synopsis', '') or product.description or '')
    return {
        'name': (product.name or 'Audiobook')[:200],
        'title': (product.name or '')[:200],
        'author': (getattr(book, 'author', '') or '')[:200],
        'description': re.sub(r'\s+', ' ', description).strip()[:1000],
        'language': _language_code(product),
        'default_title_voice_id': voice,
        'default_paragraph_voice_id': voice,
        'default_model_id': model,
        'volume_normalization': 'true',
        'auto_convert': 'true',
        'create_publishing_read': 'true',
    }


def _progress(audiobook, done: int, total: int) -> None:
    from django.utils import timezone

    from plugins.installed.audiobooks.models import Audiobook

    now = timezone.now()
    audiobook.progress_done, audiobook.progress_total, audiobook.updated_at = done, total, now
    Audiobook.objects.filter(pk=audiobook.pk).update(
        progress_done=done, progress_total=total, updated_at=now
    )


def _store(audiobook, fileobj, *, size: int, kbps: int, source: str) -> None:
    """Save the finished recording as the sample or the full narration."""
    from django.core.files import File
    from django.utils.text import slugify

    product = audiobook.variant.product
    name = f'{slugify(product.name)[:60] or "audiobook"}-{secrets.token_hex(4)}.mp3'
    target = audiobook.sample_file if audiobook.job == 'sample' else audiobook.audio_file
    old = target.name if target else ''
    target.save(name, File(fileobj), save=False)
    if audiobook.job == 'full':
        audiobook.source = source
        audiobook.status = 'ready'
        audiobook.duration_seconds = round(size * 8 / (kbps * 1000)) if kbps else None
    audiobook.job = ''
    audiobook.last_error = ''
    audiobook.progress_done = audiobook.progress_total
    audiobook.save()
    if old and old != target.name:
        try:
            target.storage.delete(old)
        except Exception:  # noqa: BLE001 — a leftover file is harmless
            logger.warning('could not delete the old narration %s', old, exc_info=True)


def _fail(audiobook, reason: str) -> None:
    if audiobook is None:
        return
    if audiobook.job == 'full':
        audiobook.status = 'ready' if audiobook.audio_file else 'failed'
    audiobook.job = ''
    audiobook.last_error = reason[:300]
    audiobook.save()


def status(audiobook) -> dict:
    """The edition's narration state, for the product card and Linda."""
    cfg = _config()
    return {
        'id': str(audiobook.id),
        'status': audiobook.status,
        'status_label': audiobook.get_status_display(),
        'job': audiobook.job,
        'running': is_running(audiobook),
        'stalled': bool(audiobook.job) and not is_running(audiobook),
        'provider': provider_for(audiobook, cfg),
        'voice': voice_for(audiobook, provider_for(audiobook, cfg), cfg),
        'done': audiobook.progress_done,
        'total': audiobook.progress_total,
        'percent': audiobook.progress_percent,
        'last_error': audiobook.last_error,
        'has_audio': bool(audiobook.audio_file),
        'has_sample': bool(audiobook.sample_file),
        'sample_url': audiobook.sample_file.url if audiobook.sample_file else '',
        'duration_seconds': audiobook.duration_seconds,
        'studio_project_id': audiobook.studio_project_id,
        'has_document': source_document(audiobook) is not None,
    }
