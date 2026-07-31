#!/usr/bin/env python3
"""Regression tests for network module."""

import unittest
from unittest.mock import MagicMock, mock_open, patch

from configurator import network


class TestNetworkInterfaceDiscovery(unittest.TestCase):
    """Tests for physical interface discovery behavior."""

    @patch('configurator.network.is_physical_interface', return_value=True)
    @patch('configurator.network.netifaces')
    def test_list_physical_interfaces_skips_interface_address_errors(self, mock_netifaces, _mock_physical):
        """A single ifaddresses failure should not abort the entire interface list."""
        mock_netifaces.interfaces.return_value = ['eth0', 'eth1']
        mock_netifaces.AF_LINK = 1
        mock_netifaces.AF_INET = 2

        def ifaddresses_side_effect(iface):
            if iface == 'eth0':
                raise OSError('transient failure')
            return {
                1: [{'addr': 'aa:bb:cc:dd:ee:ff'}],
                2: [{'addr': '192.168.1.10', 'netmask': '255.255.255.0'}],
            }

        mock_netifaces.ifaddresses.side_effect = ifaddresses_side_effect

        with patch('builtins.open', mock_open(read_data='up\n')):
            result = network.list_physical_interfaces()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'eth1')

    def test_list_physical_interfaces_handles_missing_netifaces(self):
        """Missing netifaces should degrade to empty list, not exception."""
        with patch('configurator.network.netifaces', None):
            self.assertEqual(network.list_physical_interfaces(), [])


class TestNetworkValidation(unittest.TestCase):
    """Tests for static IP validation and DHCP/static behavior."""

    @patch('configurator.network.subprocess.run')
    @patch('configurator.network.is_physical_interface', return_value=True)
    def test_configure_fixed_ip_rejects_semantically_invalid_ipv4(self, _mock_physical, mock_run):
        """Invalid IPv4 values that match old regex should be rejected early."""
        mock_run.return_value = MagicMock(returncode=0, stdout='active\n', stderr='')

        self.assertFalse(network.configure_fixed_ip('eth0', '999.1.1.1/24', '192.168.1.1'))
        self.assertFalse(network.configure_fixed_ip('eth0', '192.168.1.10/24', '300.1.1.1'))

    @patch('configurator.network.subprocess.run')
    @patch('configurator.network.is_physical_interface', return_value=True)
    def test_configure_dhcp_wireless_without_active_connection_fails_cleanly(self, _mock_physical, mock_run):
        """Wireless interfaces should not be auto-created as ethernet profiles."""
        # First call: systemctl is-active NetworkManager
        # Second call: nmcli active connection lookup (no active mapping)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='active\n', stderr=''),
            MagicMock(returncode=0, stdout='', stderr=''),
        ]

        result = network.configure_dhcp('wlan0')
        self.assertFalse(result)

    @patch('configurator.network.subprocess.run')
    @patch('configurator.network.is_physical_interface', return_value=True)
    def test_configure_fixed_ip_wireless_without_active_connection_fails_cleanly(self, _mock_physical, mock_run):
        """Static configuration should also avoid creating ethernet profile for wireless."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='active\n', stderr=''),
            MagicMock(returncode=0, stdout='', stderr=''),
        ]

        result = network.configure_fixed_ip('wlan0', '192.168.1.10/24', '192.168.1.1')
        self.assertFalse(result)


class TestNetworkConfigRead(unittest.TestCase):
    """Tests for get_network_config read behavior."""

    @patch('configurator.network.list_physical_interfaces', return_value=[])
    def test_get_network_config_without_netifaces(self, mock_list):
        """Read path should still work when netifaces is unavailable."""
        with patch('configurator.network.netifaces', None):
            with patch('builtins.open', mock_open(read_data='nameserver 1.1.1.1\n')):
                result = network.get_network_config()

        self.assertIn('hostname', result)
        self.assertIsNone(result['default_gateway'])
        self.assertEqual(result['dns_servers'], ['1.1.1.1'])
        mock_list.assert_called_once()


if __name__ == '__main__':
    unittest.main()
