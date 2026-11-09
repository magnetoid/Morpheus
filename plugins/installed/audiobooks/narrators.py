"""The narration services: ElevenLabs, ElevenLabs Studio and Qwen TTS.

Each chunk narrator turns one piece of text into MP3 bytes; services.py splits the
book, saves every piece as it arrives and joins them when the last one is in.

- ElevenLabs text-to-speech: MP3 at 128 kbps, up to ``ELEVENLABS_MAX_CHARS`` per
  request, with the neighbouring text sent along so the voice carries over.
- Qwen TTS (``qwen3-tts-flash``, Alibaba Model Studio): at most 600 characters per
  request, answered with a link to a WAV file valid for a day. The WAV is encoded to
  MP3 here (``lameenc``), since a book read as WAV is about 1.7 GB for ten hours.
  The key and region are the Qwen ones in Settings → AI (core's provider registry).
- ElevenLabs Studio: the whole book PDF goes up as a Studio project with its title,
  author and language, converts on ElevenLabs' side and comes back as one MP3. The
  project is created with a draft ElevenReader read (``create_publishing_read``); the
  merchant publishes it to ElevenReader from ElevenLabs, which offers no API for that.

Every call checks the AI kill switch first, as text-to-speech always has.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import io
import logging
import wave
from dataclasses import dataclass

logger = logging.getLogger('morpheus.audiobooks')

ELEVENLABS_API = 'https://api.elevenlabs.io/v1'
ELEVENLABS_MAX_CHARS = 2500
ELEVENLABS_KBPS = 128
QWEN_MAX_CHARS = 580  # the service refuses more than 600
QWEN_KBPS = 64
QWEN_MAX_WAV_BYTES = 64 * 1024 * 1024

# The qwen3-tts-flash voices that read English well, for the product card's list.
QWEN_VOICES = (
    'Jennifer',
    'Ryan',
    'Cherry',
    'Ethan',
    'Serena',
    'Chelsie',
    'Katerina',
    'Aiden',
    'Elias',
    'Neil',
    'Arthur',
    'Vincent',
)

# Qwen's language_type takes a language's English name.
QWEN_LANGUAGES = {
    'en': 'English',
    'de': 'German',
    'fr': 'French',
    'es': 'Spanish',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
}


class NarrationError(Exception):
    """A service refused or failed; the message is fit for the merchant."""


def _guard() -> None:
    from core.agents.guardrails import PAUSED_MESSAGE, AIPaused, agents_paused

    if agents_paused():
        raise AIPaused(PAUSED_MESSAGE)


def _detail(response) -> str:
    """The service's own reason, short and without anything secret-shaped."""
    try:
        body = response.json()
    except ValueError:
        return f'HTTP {response.status_code}'
    detail = body.get('detail') if isinstance(body, dict) else None
    if isinstance(detail, dict):
        detail = detail.get('message') or detail.get('status')
    message = detail or (body.get('message') if isinstance(body, dict) else None) or ''
    return f'HTTP {response.status_code}: {str(message)[:160]}'.rstrip(': ')


@dataclass
class ElevenLabsNarrator:
    api_key: str
    voice: str
    model: str
    max_chars: int = ELEVENLABS_MAX_CHARS
    kbps: int = ELEVENLABS_KBPS

    def narrate(self, text: str, *, previous_text: str = '', next_text: str = '') -> bytes:
        _guard()
        import requests

        body = {'text': text, 'model_id': self.model}
        if previous_text:
            body['previous_text'] = previous_text[-500:]
        if next_text:
            body['next_text'] = next_text[:500]
        response = requests.post(
            f'{ELEVENLABS_API}/text-to-speech/{self.voice}',
            params={'output_format': 'mp3_44100_128'},
            headers={'xi-api-key': self.api_key, 'Accept': 'audio/mpeg'},
            json=body,
            timeout=90,
        )
        if response.status_code != 200:
            raise NarrationError(f'ElevenLabs refused the text ({_detail(response)})')
        return response.content


@dataclass
class QwenNarrator:
    api_key: str
    base_url: str
    voice: str
    model: str
    language: str = 'Auto'
    max_chars: int = QWEN_MAX_CHARS
    kbps: int = QWEN_KBPS

    @property
    def endpoint(self) -> str:
        return f'{native_base(self.base_url)}/services/aigc/multimodal-generation/generation'

    def narrate(self, text: str, *, previous_text: str = '', next_text: str = '') -> bytes:
        _guard()
        import requests

        from core.net import outbound_request

        response = requests.post(
            self.endpoint,
            headers={'Authorization': f'Bearer {self.api_key}'},
            json={
                'model': self.model,
                'input': {'text': text, 'voice': self.voice, 'language_type': self.language},
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise NarrationError(f'Qwen TTS refused the text ({_detail(response)})')
        url = ((response.json().get('output') or {}).get('audio') or {}).get('url') or ''
        if not url.startswith('https://'):
            raise NarrationError('Qwen TTS answered without an audio file')
        # The link points at Alibaba's storage; fetched like any address a service names.
        audio = outbound_request('get', url, timeout=60, field='Qwen audio')
        if audio.status_code != 200 or len(audio.content) > QWEN_MAX_WAV_BYTES:
            raise NarrationError(f'Could not fetch the Qwen audio (HTTP {audio.status_code})')
        return wav_to_mp3(audio.content, kbps=self.kbps)


def native_base(base_url: str) -> str:
    """Model Studio's native API root from the OpenAI-compatible base URL in Settings → AI."""
    base = (base_url or 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1').rstrip('/')
    if '/compatible-mode' in base:
        base = base.split('/compatible-mode', 1)[0]
    elif base.endswith('/v1'):
        base = base[: -len('/v1')]
    if base.endswith('/api'):
        base = base[: -len('/api')]
    return f'{base}/api/v1'


def wav_to_mp3(data: bytes, *, kbps: int) -> bytes:
    """Encode a 16-bit PCM WAV file as constant-bitrate MP3."""
    import lameenc

    try:
        with wave.open(io.BytesIO(data)) as wav:
            channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise NarrationError(f'Qwen TTS sent audio that is not a WAV file ({exc})') from exc
    if width != 2:
        raise NarrationError(f'Qwen TTS sent {8 * width}-bit audio; 16-bit is expected')
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(kbps)
    encoder.set_in_sample_rate(rate)
    encoder.set_channels(channels)
    encoder.set_quality(2)
    return bytes(encoder.encode(frames) + encoder.flush())


class StudioClient:
    """ElevenLabs Studio: a whole book as one project, converted on their side."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {'xi-api-key': self.api_key}

    def create_project(self, *, document, filename: str, meta: dict) -> str:
        _guard()
        import requests

        response = requests.post(
            f'{ELEVENLABS_API}/studio/projects',
            headers=self._headers(),
            data={key: value for key, value in meta.items() if value not in ('', None)},
            files={'from_document': (filename, document, 'application/pdf')},
            timeout=300,
        )
        if response.status_code != 200:
            raise NarrationError(f'ElevenLabs Studio refused the book ({_detail(response)})')
        project_id = (response.json().get('project') or {}).get('project_id') or ''
        if not project_id:
            raise NarrationError('ElevenLabs Studio answered without a project')
        return project_id

    def project(self, project_id: str) -> dict:
        import requests

        response = requests.get(
            f'{ELEVENLABS_API}/studio/projects/{project_id}', headers=self._headers(), timeout=60
        )
        if response.status_code != 200:
            raise NarrationError(f'ElevenLabs Studio: {_detail(response)}')
        return response.json()

    def snapshots(self, project_id: str) -> list[dict]:
        import requests

        response = requests.get(
            f'{ELEVENLABS_API}/studio/projects/{project_id}/snapshots',
            headers=self._headers(),
            timeout=60,
        )
        if response.status_code != 200:
            raise NarrationError(f'ElevenLabs Studio: {_detail(response)}')
        return response.json().get('snapshots') or []

    def download(self, project_id: str, snapshot_id: str, fileobj) -> int:
        """Stream a snapshot's audio as MP3 into ``fileobj``; return the byte count."""
        import requests

        response = requests.post(
            f'{ELEVENLABS_API}/studio/projects/{project_id}/snapshots/{snapshot_id}/stream',
            headers=self._headers(),
            json={'convert_to_mpeg': True},
            stream=True,
            timeout=300,
        )
        if response.status_code != 200:
            raise NarrationError(f'ElevenLabs Studio: {_detail(response)}')
        size = 0
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            fileobj.write(chunk)
            size += len(chunk)
        return size


def studio_progress(project: dict) -> tuple[int, int, str]:
    """(characters converted, characters in all, the first chapter error) of a project."""
    done = total = 0
    error = ''
    for chapter in project.get('chapters') or []:
        stats = chapter.get('statistics') or {}
        converted = int(stats.get('characters_converted') or 0)
        done += converted
        total += converted + int(stats.get('characters_unconverted') or 0)
        error = error or (chapter.get('last_conversion_error') or '')
    return done, total, error
