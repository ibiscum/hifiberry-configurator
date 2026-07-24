#!/usr/bin/env python3
"""Regression tests for wifi module."""

from argparse import Namespace
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import unittest

from configurator import wifi


def _cp(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Create a minimal subprocess result object for tests."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class TestNmcliParsingRegression(unittest.TestCase):
    """Regression tests for robust nmcli parsing."""

    def test_split_nmcli_terse_line_with_escaped_colons(self):
        fields = wifi._split_nmcli_terse_line(
            "My\\:SSID:70:WPA2:11:AA\\:BB\\:CC\\:DD\\:EE\\:FF:▂▄▆_"
        )
        self.assertEqual(fields[0], "My:SSID")
        self.assertEqual(fields[1], "70")
        self.assertEqual(fields[4], "AA:BB:CC:DD:EE:FF")

    @patch("configurator.wifi.time.sleep", return_value=None)
    @patch("configurator.wifi.subprocess.run")
    def test_scan_with_networkmanager_parses_escaped_fields(self, mock_run, _mock_sleep):
        mock_run.side_effect = [
            _cp(0, "", ""),
            _cp(
                0,
                "My\\:SSID:70:WPA2:11:AA\\:BB\\:CC\\:DD\\:EE\\:FF:▂▄▆_\n",
                "",
            ),
        ]

        networks = wifi.scan_with_networkmanager("wlan0", timeout=1)

        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0]["ssid"], "My:SSID")
        self.assertEqual(networks[0]["bssid"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(networks[0]["signal"], 70)


class TestWifiMainRegression(unittest.TestCase):
    """Regression tests for main() exit codes and quiet mode output."""

    @patch("configurator.wifi.scan_wifi_networks")
    @patch("configurator.wifi.parse_arguments")
    def test_main_list_networks_quiet_suppresses_stdout(self, mock_parse, mock_scan):
        mock_parse.return_value = Namespace(
            list_networks=True,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=True,
        )
        mock_scan.return_value = [{"ssid": "A", "signal": 50, "security": "Open"}]

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()

        self.assertEqual(code, 0)
        self.assertEqual(fake_stdout.getvalue(), "")

    @patch("configurator.wifi.scan_wifi_networks", return_value=[])
    @patch("configurator.wifi.parse_arguments")
    def test_main_list_networks_empty_returns_failure(self, mock_parse, _mock_scan):
        mock_parse.return_value = Namespace(
            list_networks=True,
            connect=None,
            show_current=False,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )

        code = wifi.main()

        self.assertEqual(code, 1)

    @patch("configurator.wifi.get_current_connection")
    @patch("configurator.wifi.parse_arguments")
    def test_main_show_current_quiet_suppresses_stdout(self, mock_parse, mock_current):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect=None,
            show_current=True,
            timeout=10,
            passphrase=None,
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=True,
        )
        mock_current.return_value = {
            "ssid": "MyNet",
            "device": "wlan0",
            "ip": "192.168.1.2",
            "security": "wpa-psk",
        }

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            code = wifi.main()

        self.assertEqual(code, 0)
        self.assertEqual(fake_stdout.getvalue(), "")

    @patch("configurator.wifi.connect_to_wifi", return_value=True)
    @patch("configurator.wifi.parse_arguments")
    def test_main_connect_success_returns_zero(self, mock_parse, _mock_connect):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect="MyNet",
            show_current=False,
            timeout=10,
            passphrase="secret",
            revert_when_fail=True,
            long=False,
            verbose=False,
            quiet=False,
        )

        code = wifi.main()

        self.assertEqual(code, 0)

    @patch("configurator.wifi.connect_to_wifi", return_value=False)
    @patch("configurator.wifi.parse_arguments")
    def test_main_connect_failure_returns_one(self, mock_parse, _mock_connect):
        mock_parse.return_value = Namespace(
            list_networks=False,
            connect="MyNet",
            show_current=False,
            timeout=10,
            passphrase="secret",
            revert_when_fail=False,
            long=False,
            verbose=False,
            quiet=False,
        )

        code = wifi.main()

        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
