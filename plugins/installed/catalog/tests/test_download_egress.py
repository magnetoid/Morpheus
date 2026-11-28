"""A file the catalog downloads from a URL goes out through core's egress gate.

`_download` (a product's PDF, cover or image named by URL, over the API or by
Linda) checked only the first host, by name, and let `requests` follow redirects
on its own. So an address that redirects to a private one was fetched, and so
was one whose host part hides a second host behind a backslash (v0.200.0).
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from plugins.installed.catalog.services._helpers import PublishError, _download


def _public(host):
    return not host.startswith(('10.', '127.', '169.254.'))


def _reply(status=200, body=b'%PDF-1.4', headers=None):
    reply = Mock(status_code=status, headers=headers or {'Content-Type': 'application/pdf'})
    reply.iter_content.return_value = [body]
    reply.__enter__ = lambda self: self
    reply.__exit__ = lambda self, *a: False
    return reply


class DownloadEgressTests(SimpleTestCase):
    def test_a_redirect_to_a_private_address_is_never_fetched(self):
        hop = _reply(302, headers={'Location': 'https://169.254.169.254/latest/meta-data/'})
        with (
            patch('core.net.is_safe_remote_host', side_effect=_public),
            patch('requests.get', side_effect=[hop]) as get,
            self.assertRaises(PublishError) as cm,
        ):
            _download('https://files.example.com/book.pdf', max_bytes=1024, field='pdf_url')
        self.assertEqual(get.call_count, 1)
        self.assertIn('pdf_url', str(cm.exception))

    def test_a_second_host_behind_a_backslash_is_refused_before_any_request(self):
        with (
            patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]),
            patch('requests.get') as get,
            self.assertRaises(PublishError),
        ):
            _download('https://127.0.0.1:8000\\@example.com/x.pdf', max_bytes=1024, field='pdf_url')
        get.assert_not_called()

    def test_a_redirect_to_a_public_address_still_downloads(self):
        hop = _reply(302, headers={'Location': 'https://cdn.example.com/book.pdf'})
        with (
            patch('core.net.is_safe_remote_host', side_effect=_public),
            patch('requests.get', side_effect=[hop, _reply()]) as get,
        ):
            body, content_type, name = _download(
                'https://files.example.com/book.pdf', max_bytes=1024, field='pdf_url'
            )
        self.assertEqual((body, content_type, name), (b'%PDF-1.4', 'application/pdf', 'book.pdf'))
        self.assertIs(get.call_args.kwargs['allow_redirects'], False)

    def test_a_private_first_address_is_refused(self):
        with (
            patch('core.net.is_safe_remote_host', side_effect=_public),
            patch('requests.get') as get,
            self.assertRaises(PublishError),
        ):
            _download('https://10.0.0.5/book.pdf', max_bytes=1024, field='pdf_url')
        get.assert_not_called()
