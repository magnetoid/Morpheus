"""Narration jobs (services.py, narrators.py) with every service faked.

A job runs in slices, keeps each narrated piece, resumes after a failure, never
takes a ready recording away, and ends with the file in private storage.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import io
import shutil
import tempfile
import wave
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from djmoney.money import Money

MEDIA = tempfile.mkdtemp()
CONFIG = {
    'provider': 'elevenlabs',
    'elevenlabs_api_key': 'k',
    'elevenlabs_voice_id': 'voice-1',
    'elevenlabs_model': 'eleven_multilingual_v2',
    'qwen_voice': 'Jennifer',
    'qwen_model': 'qwen3-tts-flash',
}
BOOK = ' '.join(f'Sentence number {n} of the book is here.' for n in range(1, 41))


class FakeNarrator:
    max_chars = 400
    kbps = 128
    voice = 'voice-1'
    model = 'm'

    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def narrate(self, text, *, previous_text='', next_text=''):
        from plugins.installed.audiobooks.narrators import NarrationError

        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise NarrationError('quota exceeded')
        self.calls.append(text)
        return f'[{len(self.calls)}]'.encode()


@override_settings(MEDIA_ROOT=MEDIA)
class NarrationTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, MEDIA, ignore_errors=True)

    def setUp(self):
        from plugins.installed.audiobooks.services import get_or_create_audiobook_edition
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product

        cache.clear()
        self.product = Product.objects.create(
            name='The Long Road',
            slug='ab-long-road',
            sku='ABLR-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        BookProduct.objects.create(product=self.product, author='An Author', language='en')
        self.audiobook = get_or_create_audiobook_edition(self.product, sku='ABLR-1-A')
        self.audiobook.source_pdf.save('book.pdf', ContentFile(b'%PDF-1.4'), save=True)
        patches = (
            mock.patch('plugins.installed.audiobooks.services._config', return_value=CONFIG),
            mock.patch('plugins.installed.audiobooks.services.source_text', return_value=BOOK),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _start(self, job='full', **kwargs):
        from plugins.installed.audiobooks.services import start

        with (
            mock.patch('plugins.installed.audiobooks.tasks.generate_audiobook.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            result = start(self.audiobook, job=job, **kwargs)
        return result, delay

    def _run_all(self, narrator, limit=50):
        from plugins.installed.audiobooks.services import run

        with mock.patch(
            'plugins.installed.audiobooks.services.narrator_for', return_value=narrator
        ):
            for _ in range(limit):
                result = run(self.audiobook.id)
                if result.get('again') is None:
                    break
        self.audiobook.refresh_from_db()
        return result


class TextTests(TestCase):
    def test_chunks_stay_under_the_limit_and_keep_every_word(self):
        from plugins.installed.audiobooks.services import chunks

        text = BOOK + ' ' + 'x' * 900
        pieces = chunks(text, 300)
        self.assertTrue(all(len(piece) <= 300 for piece in pieces))
        self.assertEqual(''.join(pieces).replace(' ', ''), text.replace(' ', ''))

    def test_clean_text_joins_broken_words_and_drops_page_numbers(self):
        from plugins.installed.audiobooks.services import clean_text

        raw = 'The jour-\nney began.\n12\nPage 13\nIt was   long.'
        self.assertEqual(clean_text(raw), 'The journey began. It was long.')

    def test_sample_ends_at_a_sentence(self):
        from plugins.installed.audiobooks.services import sample_text

        sample = sample_text(BOOK, limit=200)
        self.assertLessEqual(len(sample), 200)
        self.assertTrue(sample.endswith('here.'))

    def test_qwen_native_api_root(self):
        from plugins.installed.audiobooks.narrators import native_base

        self.assertEqual(
            native_base('https://dashscope-intl.aliyuncs.com/compatible-mode/v1'),
            'https://dashscope-intl.aliyuncs.com/api/v1',
        )
        self.assertEqual(native_base(''), 'https://dashscope-intl.aliyuncs.com/api/v1')


class StartTests(NarrationTestCase):
    def test_queues_a_job_after_commit(self):
        from core.agents.provider_registry import ProviderConfig

        qwen = ProviderConfig(
            provider='qwen', api_key='q', base_url='', model='', embedding_model=''
        )
        with mock.patch('core.agents.provider_registry.get_provider_config', return_value=qwen):
            result, delay = self._start(provider='qwen', voice='Ryan')
        self.assertTrue(result['ok'], result)
        delay.assert_called_once_with(str(self.audiobook.id))
        self.audiobook.refresh_from_db()
        self.assertEqual(
            (self.audiobook.job, self.audiobook.status, self.audiobook.provider),
            ('full', 'generating', 'qwen'),
        )
        self.assertEqual(self.audiobook.voice, 'Ryan')

    def test_refuses_without_a_pdf(self):
        from plugins.installed.audiobooks.services import NO_DOCUMENT

        self.audiobook.source_pdf = None
        self.audiobook.save()
        result, delay = self._start()
        self.assertEqual(result, {'ok': False, 'reason': NO_DOCUMENT})
        delay.assert_not_called()

    def test_refuses_without_a_key(self):
        with mock.patch(
            'plugins.installed.audiobooks.services._config',
            return_value={**CONFIG, 'elevenlabs_api_key': ''},
        ):
            result, _ = self._start()
        self.assertFalse(result['ok'])
        self.assertIn('ElevenLabs API key', result['reason'])

    def test_refuses_a_second_job_while_one_runs(self):
        self._start()
        result, delay = self._start(job='sample')
        self.assertFalse(result['ok'])
        delay.assert_not_called()


class RunTests(NarrationTestCase):
    def test_whole_book_in_slices(self):
        self._start()
        narrator = FakeNarrator()
        with mock.patch('plugins.installed.audiobooks.services.SLICE_SECONDS', -1):
            result = self._run_all(narrator)
        self.assertTrue(result['ok'], result)
        ab = self.audiobook
        self.assertEqual((ab.status, ab.job, ab.source), ('ready', '', 'elevenlabs'))
        self.assertTrue(ab.audio_file.name.startswith('digital/audiobooks/'))
        self.assertEqual(ab.progress_percent, 100)
        with ab.audio_file.open('rb') as fh:
            self.assertEqual(
                fh.read(), b''.join(f'[{n}]'.encode() for n in range(1, len(narrator.calls) + 1))
            )
        self.assertGreater(len(narrator.calls), 2)

    def test_failure_is_shown_and_a_restart_resumes(self):
        self._start()
        self._run_all(FakeNarrator(fail_at=2))
        ab = self.audiobook
        self.assertEqual((ab.status, ab.job, ab.last_error), ('failed', '', 'quota exceeded'))
        self._start()
        narrator = FakeNarrator()
        self._run_all(narrator)
        self.assertEqual(self.audiobook.status, 'ready')
        from plugins.installed.audiobooks.services import chunks

        self.assertEqual(len(narrator.calls), len(chunks(BOOK, FakeNarrator.max_chars)) - 2)

    def test_ready_edition_keeps_its_recording_when_a_new_one_fails(self):
        self.audiobook.audio_file.save('old.mp3', ContentFile(b'old'), save=False)
        self.audiobook.status = 'ready'
        self.audiobook.save()
        self._start()
        self.audiobook.refresh_from_db()
        self.assertEqual(self.audiobook.status, 'ready')
        self._run_all(FakeNarrator(fail_at=0))
        self.assertEqual(self.audiobook.status, 'ready')
        self.assertTrue(self.audiobook.audio_file)

    def test_sample_becomes_the_preview(self):
        self._start(job='sample')
        self._run_all(FakeNarrator())
        ab = self.audiobook
        self.assertEqual((ab.status, ab.job), ('none', ''))
        self.assertTrue(ab.sample_file)
        self.assertFalse(ab.audio_file)


class QwenTests(TestCase):
    def _wav(self):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b'\x00\x00' * 24000)
        return buf.getvalue()

    def test_qwen_audio_is_encoded_to_mp3(self):
        from plugins.installed.audiobooks.narrators import QwenNarrator

        answer = mock.Mock(status_code=200)
        answer.json.return_value = {'output': {'audio': {'url': 'https://oss.example.com/a.wav'}}}
        audio = mock.Mock(status_code=200, content=self._wav())
        narrator = QwenNarrator(api_key='k', base_url='', voice='Jennifer', model='qwen3-tts-flash')
        with (
            mock.patch('requests.post', return_value=answer) as post,
            mock.patch('core.net.outbound_request', return_value=audio),
        ):
            mp3 = narrator.narrate('Hello there.')
        body = post.call_args.kwargs['json']
        self.assertEqual(body['input']['voice'], 'Jennifer')
        self.assertTrue(
            post.call_args.args[0].endswith(
                '/api/v1/services/aigc/multimodal-generation/generation'
            )
        )
        self.assertTrue(mp3[:3] == b'ID3' or mp3[0] == 0xFF, mp3[:4])


class StudioTests(NarrationTestCase):
    def test_project_then_wait_then_download(self):
        from plugins.installed.audiobooks.services import run

        self._start(provider='studio')
        client = mock.Mock()
        client.create_project.return_value = 'proj-1'
        with mock.patch('plugins.installed.audiobooks.narrators.StudioClient', return_value=client):
            first = run(self.audiobook.id)
            self.assertEqual(first['again'], 60)
            client.project.return_value = {
                'chapters': [
                    {'statistics': {'characters_converted': 50, 'characters_unconverted': 50}}
                ]
            }
            self.assertEqual(run(self.audiobook.id)['again'], 60)
            client.project.return_value = {
                'chapters': [
                    {'statistics': {'characters_converted': 100, 'characters_unconverted': 0}}
                ]
            }
            client.snapshots.return_value = [
                {'project_snapshot_id': 'snap-1', 'created_at_unix': 4102444800}
            ]
            client.download.side_effect = lambda pid, sid, fh: fh.write(b'MP3') or 3
            done = run(self.audiobook.id)
        self.assertIsNone(done['again'])
        meta = client.create_project.call_args.kwargs['meta']
        self.assertEqual(meta['create_publishing_read'], 'true')
        self.assertEqual(meta['author'], 'An Author')
        self.audiobook.refresh_from_db()
        self.assertEqual(
            (self.audiobook.status, self.audiobook.source, self.audiobook.studio_project_id),
            ('ready', 'studio', 'proj-1'),
        )


class DashboardAndToolTests(NarrationTestCase):
    def test_card_actions_are_staff_only(self):
        url = f'/dashboard/audiobooks/{self.audiobook.id}/status/'
        self.assertNotEqual(self.client.get(url).status_code, 200)
        staff = get_user_model().objects.create_user(
            username='staff@example.com',
            email='staff@example.com',
            password='pw-1234!',
            is_staff=True,
        )
        self.client.force_login(staff)
        state = self.client.get(url).json()['state']
        self.assertEqual(state['status'], 'none')
        with mock.patch('plugins.installed.audiobooks.tasks.generate_audiobook.delay'):
            response = self.client.post(
                f'/dashboard/audiobooks/{self.audiobook.id}/generate/',
                {'job': 'sample', 'provider': 'elevenlabs', 'voice': ''},
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['state']['job'], 'sample')

    def test_tools(self):
        from core.agents.registry import agent_registry

        status_tool = agent_registry.get_tool('audiobooks.status')
        generate_tool = agent_registry.get_tool('audiobooks.generate')
        self.assertFalse(status_tool.requires_approval)
        self.assertTrue(generate_tool.requires_approval)
        out = status_tool.invoke({'product': self.product.slug}).output
        self.assertEqual(out['provider'], 'elevenlabs')
        self.assertTrue(out['has_document'])
