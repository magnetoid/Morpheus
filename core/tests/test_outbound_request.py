"""Server-initiated requests to staff-entered URLs: public hosts only, no redirects.

The two guarded webhook posts followed redirects, so a public URL answering 302
to 169.254.169.254 bypassed the check; the workflow action, the OpenAI feed push
and the importers had no check at all.
"""

from __future__ import annotations

from unittest.mock import patch

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
