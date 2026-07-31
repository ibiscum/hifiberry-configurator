#!/usr/bin/env python3
"""Regression tests for hostname_utils module."""

import unittest
from unittest.mock import MagicMock, patch

from configurator.hostname_utils import (
    get_hostnames,
    get_hostnames_with_fallback,
    sanitize_hostname,
    set_hostname,
    set_pretty_hostname,
    validate_hostname,
    validate_pretty_hostname,
)


class TestGetHostnames(unittest.TestCase):
    """Tests for hostname retrieval helpers."""

    @patch('configurator.hostname_utils.subprocess.run')
    def test_get_hostnames_success(self, mock_run):
        """Returns hostname and pretty hostname when both commands succeed."""
        hostname_result = MagicMock(returncode=0, stdout='hifiberry\n')
        pretty_result = MagicMock(returncode=0, stdout='HiFiBerry Device\n')
        mock_run.side_effect = [hostname_result, pretty_result]

        hostname, pretty = get_hostnames()

        self.assertEqual(hostname, 'hifiberry')
        self.assertEqual(pretty, 'HiFiBerry Device')
        self.assertEqual(mock_run.call_count, 2)

    @patch('configurator.hostname_utils.subprocess.run')
    def test_get_hostnames_pretty_empty_becomes_none(self, mock_run):
        """Empty pretty hostname output is normalized to None."""
        hostname_result = MagicMock(returncode=0, stdout='hifiberry\n')
        pretty_result = MagicMock(returncode=0, stdout='\n')
        mock_run.side_effect = [hostname_result, pretty_result]

        hostname, pretty = get_hostnames()

        self.assertEqual(hostname, 'hifiberry')
        self.assertIsNone(pretty)

    @patch('configurator.hostname_utils.subprocess.run')
    def test_get_hostnames_failure_for_hostname(self, mock_run):
        """Hostname command failure returns None for hostname."""
        hostname_result = MagicMock(returncode=1, stdout='', stderr='failed')
        pretty_result = MagicMock(returncode=0, stdout='Pretty Name\n')
        mock_run.side_effect = [hostname_result, pretty_result]

        hostname, pretty = get_hostnames()

        self.assertIsNone(hostname)
        self.assertEqual(pretty, 'Pretty Name')

    @patch('configurator.hostname_utils.subprocess.run', side_effect=Exception('boom'))
    def test_get_hostnames_exception(self, _mock_run):
        """Unexpected subprocess errors return (None, None)."""
        hostname, pretty = get_hostnames()
        self.assertIsNone(hostname)
        self.assertIsNone(pretty)


class TestValidationAndSanitization(unittest.TestCase):
    """Tests for validation/sanitization wrappers."""

    @patch('configurator.hostname_utils.sanitize_hostname_format', return_value='my-device')
    def test_sanitize_hostname_delegates_max_length_64(self, mock_sanitize):
        """sanitize_hostname always delegates with max_length=64."""
        result = sanitize_hostname('My Device')
        self.assertEqual(result, 'my-device')
        mock_sanitize.assert_called_once_with('My Device', max_length=64)

    @patch('configurator.hostname_utils.validate_hostname_format', return_value=True)
    def test_validate_hostname_delegates(self, mock_validate):
        """validate_hostname delegates to hostconfig validator."""
        self.assertTrue(validate_hostname('host-1'))
        mock_validate.assert_called_once_with('host-1')

    def test_validate_pretty_hostname_valid(self):
        """Printable ASCII pretty hostname is accepted."""
        self.assertTrue(validate_pretty_hostname('HiFiBerry Device'))

    def test_validate_pretty_hostname_empty(self):
        """Empty pretty hostname is rejected."""
        self.assertFalse(validate_pretty_hostname(''))

    def test_validate_pretty_hostname_whitespace_only(self):
        """Whitespace-only pretty hostname is rejected."""
        self.assertFalse(validate_pretty_hostname('   '))

    def test_validate_pretty_hostname_too_long(self):
        """Pretty hostname over 64 chars is rejected."""
        self.assertFalse(validate_pretty_hostname('A' * 65))

    def test_validate_pretty_hostname_non_ascii(self):
        """Non-ASCII pretty hostname is rejected."""
        self.assertFalse(validate_pretty_hostname('HiFi-音声'))

    def test_validate_pretty_hostname_non_printable(self):
        """Non-printable ASCII characters are rejected."""
        self.assertFalse(validate_pretty_hostname('HiFi\nBerry'))


class TestSetHostnameHelpers(unittest.TestCase):
    """Tests for hostname update helpers."""

    @patch('configurator.hostname_utils.set_hostname_with_hosts_update', return_value=True)
    def test_set_hostname_delegates(self, mock_set):
        """set_hostname delegates to hostconfig helper."""
        self.assertTrue(set_hostname('new-host'))
        mock_set.assert_called_once_with('new-host')

    @patch('configurator.hostname_utils.subprocess.run')
    def test_set_pretty_hostname_success(self, mock_run):
        """set_pretty_hostname returns True on command success."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        self.assertTrue(set_pretty_hostname('My Device'))
        mock_run.assert_called_once_with(
            ['hostnamectl', 'set-hostname', '--pretty', 'My Device'],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    @patch('configurator.hostname_utils.subprocess.run')
    def test_set_pretty_hostname_failure(self, mock_run):
        """set_pretty_hostname returns False on non-zero exit code."""
        mock_run.return_value = MagicMock(returncode=1, stderr='failed')
        self.assertFalse(set_pretty_hostname('My Device'))

    @patch('configurator.hostname_utils.subprocess.run', side_effect=Exception('boom'))
    def test_set_pretty_hostname_exception(self, _mock_run):
        """set_pretty_hostname returns False on exception."""
        self.assertFalse(set_pretty_hostname('My Device'))


class TestFallbackHelper(unittest.TestCase):
    """Tests for hostname fallback behavior."""

    @patch('configurator.hostname_utils.get_hostnames', return_value=('hifiberry', None))
    def test_get_hostnames_with_fallback_uses_hostname(self, mock_get):
        """When pretty hostname is missing, hostname is reused."""
        hostname, pretty = get_hostnames_with_fallback()
        self.assertEqual(hostname, 'hifiberry')
        self.assertEqual(pretty, 'hifiberry')
        mock_get.assert_called_once()

    @patch('configurator.hostname_utils.get_hostnames', return_value=('hifiberry', 'HiFiBerry'))
    def test_get_hostnames_with_fallback_preserves_pretty(self, mock_get):
        """When pretty hostname exists, fallback does not alter it."""
        hostname, pretty = get_hostnames_with_fallback()
        self.assertEqual(hostname, 'hifiberry')
        self.assertEqual(pretty, 'HiFiBerry')
        mock_get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
