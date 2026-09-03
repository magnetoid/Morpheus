"""Outbound SSRF gate (core/net.py).

Morpheus makes server-side fetches on behalf of untrusted input — a merchant's
webhook URL, an agent's `pdf_url`. Without a gate, an attacker who controls the
URL reaches whatever the SERVER can reach: cloud metadata (instance
credentials), internal admin ports, localhost. These lock the refusals.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from core.net import (
    UnsafeUrlError,
    check_outbound_url,
    is_public_ip,
    is_safe_outbound_url,
    is_safe_remote_host,
)


def _resolves_to(addr: str):
    """Patch getaddrinfo so a hostname resolves to `addr`."""
    return patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', (addr, 0))])


class PublicIpTests(SimpleTestCase):
    def test_public_addresses_pass(self):
        import ipaddress

        for good in ('8.8.8.8', '1.1.1.1', '2606:4700::1111'):
            self.assertTrue(is_public_ip(ipaddress.ip_address(good)), good)

    def test_internal_ranges_are_refused(self):
        import ipaddress

        for bad in (
            '127.0.0.1',  # loopback
            '::1',  # loopback v6
            '10.0.0.5',  # private
            '172.16.0.1',  # private
            '192.168.1.1',  # private
            '169.254.169.254',  # cloud metadata — the one that leaks credentials
            '0.0.0.0',  # unspecified
            '224.0.0.1',  # multicast
        ):
            self.assertFalse(is_public_ip(ipaddress.ip_address(bad)), bad)


class HostResolutionTests(SimpleTestCase):
    def test_literal_internal_ip_refused_without_dns(self):
        self.assertFalse(is_safe_remote_host('169.254.169.254'))
        self.assertFalse(is_safe_remote_host('127.0.0.1'))

    def test_hostname_resolving_internally_is_refused(self):
        # The attack: a public-looking name whose DNS answers 127.0.0.1.
        with _resolves_to('127.0.0.1'):
            self.assertFalse(is_safe_remote_host('evil.example.com'))

    def test_hostname_resolving_publicly_passes(self):
        with _resolves_to('93.184.216.34'):
            self.assertTrue(is_safe_remote_host('example.com'))

    def test_every_returned_address_must_be_public(self):
        # One internal answer among several must refuse the whole host.
        mixed = [(2, 1, 6, '', ('93.184.216.34', 0)), (2, 1, 6, '', ('10.0.0.1', 0))]
        with patch('socket.getaddrinfo', return_value=mixed):
            self.assertFalse(is_safe_remote_host('mixed.example.com'))

    def test_resolution_failure_is_TRANSIENT_not_permanent(self):
        """A DNS blip must be distinguishable from a genuinely unsafe host.

        Conflating them let a brief resolver outage permanently fail every
        queued webhook. Allowing a retry concedes nothing: an unresolvable host
        cannot be connected to, and the full check reruns if it starts
        resolving.
        """
        import socket as _s

        from core.net import UnresolvableHostError, resolves_safely

        with patch('socket.getaddrinfo', side_effect=_s.gaierror):
            with self.assertRaises(UnresolvableHostError):
                is_safe_remote_host('nope.example.com')
            # the non-raising wrapper still reads it as unsafe (one-shot fetches)
            self.assertFalse(resolves_safely('nope.example.com'))

    def test_unresolvable_is_a_subclass_so_base_catches_still_work(self):
        from core.net import UnresolvableHostError, UnsafeUrlError

        self.assertTrue(issubclass(UnresolvableHostError, UnsafeUrlError))

    def test_empty_host_refused(self):
        self.assertFalse(is_safe_remote_host(''))


class CheckOutboundUrlTests(SimpleTestCase):
    def test_scheme_enforced(self):
        with _resolves_to('93.184.216.34'):
            with self.assertRaises(UnsafeUrlError):
                check_outbound_url('http://example.com/x')  # https required
            with self.assertRaises(UnsafeUrlError):
                check_outbound_url('file:///etc/passwd')
            # ...but http is allowed when the caller opts in (legacy webhooks)
            self.assertEqual(
                check_outbound_url('http://example.com/x', require_https=False), 'example.com'
            )

    def test_metadata_endpoint_refused(self):
        with self.assertRaises(UnsafeUrlError):
            check_outbound_url('http://169.254.169.254/latest/meta-data/', require_https=False)

    def test_ipv6_brackets_are_stripped_before_the_check(self):
        # urlparse().hostname strips [] — if a caller used netloc instead, '[::1]'
        # would not parse as an IP and loopback would slip through.
        with self.assertRaises(UnsafeUrlError):
            check_outbound_url('http://[::1]:8000/x', require_https=False)

    def test_non_raising_helper(self):
        self.assertFalse(is_safe_outbound_url('http://127.0.0.1/', require_https=False))
        with _resolves_to('93.184.216.34'):
            self.assertTrue(is_safe_outbound_url('https://example.com/'))
