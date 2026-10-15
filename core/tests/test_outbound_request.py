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
