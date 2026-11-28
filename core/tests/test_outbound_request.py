"""Server-initiated requests to staff-entered URLs: public hosts only, no redirects.

The two guarded webhook posts followed redirects, so a public URL answering 302
to 169.254.169.254 bypassed the check; the workflow action, the OpenAI feed push
and the importers had no check at all.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core.net import UnsafeUrlError, outbound_request


class OutboundRequestTests(SimpleTestCase):
    def test_a_private_address_is_refused_before_any_request(self):
        with patch('requests.post') as post, self.assertRaises(UnsafeUrlError):
            outbound_request('POST', 'http://10.0.0.5/hook', require_https=False)
        post.assert_not_called()

    def test_a_backslash_authority_never_reaches_requests(self):
        with (
            patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]),
            patch('requests.get') as get,
            self.assertRaises(UnsafeUrlError),
        ):
            outbound_request('GET', 'http://127.0.0.1:6379\\@example.com/', require_https=False)
        get.assert_not_called()

    def test_https_is_required_unless_waived(self):
        with self.assertRaises(UnsafeUrlError):
            outbound_request('POST', 'http://example.com/x')

    def test_redirects_are_never_followed(self):
        with (
            patch('core.net.is_safe_remote_host', return_value=True),
            patch('requests.post') as post,
        ):
            outbound_request('POST', 'https://example.com/x', data=b'{}', timeout=5)
        self.assertIs(post.call_args.kwargs['allow_redirects'], False)
        self.assertEqual(post.call_args.args, ('https://example.com/x',))

    def test_get_uses_requests_get(self):
        with (
            patch('core.net.is_safe_remote_host', return_value=True),
            patch('requests.get') as get,
        ):
            outbound_request('GET', 'https://example.com/x', params={'a': 1})
        self.assertIs(get.call_args.kwargs['allow_redirects'], False)


class RedirectReplyTests(SimpleTestCase):
    """A refused redirect is a failure that names the target, never a success.

    Without this a WooCommerce store entered as http:// (which 301s to https)
    failed with a JSON decode error, and a webhook answering 301 was logged as
    delivered.
    """

    def test_a_redirect_reply_is_an_error_naming_its_target(self):
        reply = Mock(status_code=301, headers={'Location': 'https://shop.example.com/'})
        with (
            patch('core.net.is_safe_remote_host', return_value=True),
            patch('requests.get', return_value=reply),
            self.assertRaises(UnsafeUrlError) as cm,
        ):
            outbound_request('GET', 'http://shop.example.com/', require_https=False)
        self.assertIn('https://shop.example.com/', str(cm.exception))

    def test_a_plain_reply_is_returned(self):
        reply = Mock(status_code=200, headers={})
        with (
            patch('core.net.is_safe_remote_host', return_value=True),
            patch('requests.post', return_value=reply),
        ):
            self.assertIs(outbound_request('POST', 'https://example.com/x'), reply)


class CheckedRedirectTests(SimpleTestCase):
    """A download may follow redirects (`max_redirects`): each hop is checked
    like the first address, so a public URL cannot lead to a private one."""

    @staticmethod
    def _public(host):
        return not host.startswith(('10.', '127.', '169.254.'))

    def test_a_redirect_to_a_public_address_is_followed(self):
        first = Mock(status_code=302, headers={'Location': 'https://cdn.example.com/b.pdf'})
        last = Mock(status_code=200, headers={})
        with (
            patch('core.net.is_safe_remote_host', side_effect=self._public),
            patch('requests.get', side_effect=[first, last]) as get,
        ):
            reply = outbound_request('GET', 'https://example.com/a.pdf', max_redirects=3)
        self.assertIs(reply, last)
        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            ['https://example.com/a.pdf', 'https://cdn.example.com/b.pdf'],
        )
        first.close.assert_called_once()

    def test_a_relative_redirect_stays_on_the_host(self):
        first = Mock(status_code=301, headers={'Location': '/files/b.pdf'})
        last = Mock(status_code=200, headers={})
        with (
            patch('core.net.is_safe_remote_host', side_effect=self._public),
            patch('requests.get', side_effect=[first, last]) as get,
        ):
            outbound_request('GET', 'https://example.com/a.pdf', max_redirects=3)
        self.assertEqual(get.call_args_list[1].args[0], 'https://example.com/files/b.pdf')

    def test_a_redirect_to_a_private_address_is_refused_before_it_is_fetched(self):
        first = Mock(status_code=302, headers={'Location': 'https://169.254.169.254/latest/'})
        with (
            patch('core.net.is_safe_remote_host', side_effect=self._public),
            patch('requests.get', side_effect=[first]) as get,
            self.assertRaises(UnsafeUrlError),
        ):
            outbound_request('GET', 'https://example.com/a.pdf', max_redirects=3)
        self.assertEqual(get.call_count, 1)

    def test_a_redirect_down_to_http_is_refused(self):
        first = Mock(status_code=302, headers={'Location': 'http://example.com/a.pdf'})
        with (
            patch('core.net.is_safe_remote_host', side_effect=self._public),
            patch('requests.get', side_effect=[first]) as get,
            self.assertRaises(UnsafeUrlError),
        ):
            outbound_request('GET', 'https://example.com/a.pdf', max_redirects=3)
        self.assertEqual(get.call_count, 1)

    def test_more_redirects_than_allowed_is_an_error(self):
        hop = Mock(status_code=302, headers={'Location': 'https://example.com/again'})
        with (
            patch('core.net.is_safe_remote_host', side_effect=self._public),
            patch('requests.get', return_value=hop) as get,
            self.assertRaises(UnsafeUrlError),
        ):
            outbound_request('GET', 'https://example.com/a.pdf', max_redirects=2)
        self.assertEqual(get.call_count, 3)

    def test_a_refused_redirect_is_closed(self):
        hop = Mock(status_code=302, headers={'Location': 'https://example.com/b'})
        with (
            patch('core.net.is_safe_remote_host', side_effect=self._public),
            patch('requests.get', return_value=hop),
            self.assertRaises(UnsafeUrlError),
        ):
            outbound_request('GET', 'https://example.com/a')
        hop.close.assert_called_once()

    def test_only_a_plain_get_follows_redirects(self):
        # Whatever is sent goes to every hop, which may be another host.
        for method, extra in (
            ('POST', {}),
            ('GET', {'headers': {'Authorization': 'Bearer x'}}),
            ('GET', {'auth': ('u', 'p')}),
        ):
            with (
                self.subTest(method=method, extra=extra),
                patch('requests.get') as get,
                patch('requests.post') as post,
                self.assertRaises(ValueError),
            ):
                outbound_request(method, 'https://example.com/a', max_redirects=2, **extra)
            get.assert_not_called()
            post.assert_not_called()
